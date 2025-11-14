# -*- coding: utf-8 -*-
# bojang_api/views.py
# 안정 로그인 + A3/A4 템플릿 선택 분석 + records 로깅

# --- 1) 기본 & 외부 라이브러리 ---
import logging
import os
import uuid
import zipfile
from datetime import timedelta
from io import BytesIO
from pathlib import Path
import tempfile
import subprocess

# --- 2) Django & DRF ---
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, User
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.utils.timezone import now
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage

# --- 3) 내부 모듈 ---
from .auth import create_jwt_for_user
from .models import PasswordResetCode, Profile, Notice  # Serializer가 Profile을 사용
from .serializers import SignupSerializer

# --- 4) records 앱 임포트 (최종) ---
from records.models import ProcessedPDF, LoginLog
_RECORDS_OK = True

# --- 5) PDF → 엑셀 파이프라인 ---
from pdf_xlsx import config, excel_handler
from pdf_xlsx.pdf_processor import extract_data_from_pdf

# --- 로거 ---
logger = logging.getLogger(__name__)


# ===================================================================
# 헬퍼
# ===================================================================
def _make_code() -> str:
    import random, string
    return "".join(random.choices(string.digits, k=6))


def _hash(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _make_reset_token(user_id: int) -> str:
    signer = signing.TimestampSigner(salt="pwreset")
    return signer.sign(str(user_id))


def _verify_reset_token(token: str, max_age_seconds: int = 300) -> int:
    signer = signing.TimestampSigner(salt="pwreset")
    uid_str = signer.unsign(token, max_age=max_age_seconds)
    return int(uid_str)


def get_client_ip(request) -> str:
    """Cloud Run 등 프록시 환경을 고려하여 IP 주소 반환."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip or "0.0.0.0"


# ===================================================================
# I. 인증
# ===================================================================
@method_decorator(csrf_exempt, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""

        if not username or not password:
            return Response({"detail": "아이디/비밀번호를 입력하세요."}, status=status.HTTP_400_BAD_REQUEST)

        # Django 인증기 사용(500 방지)
        user = authenticate(request, username=username, password=password)
        if user is None:
            # 존재하지 않음/비밀번호 오류/비활성 동일 처리(보안상)
            return Response(
                {"detail": "아이디 또는 비밀번호가 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {"detail": "관리자의 승인이 필요한 계정입니다."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 로그인 IP 로깅 (실패해도 진행)
        try:
            LoginLog.objects.create(user=user, ip_address=get_client_ip(request))
        except Exception as e:
            logger.error("LoginLog 기록 실패 (User: %s): %s", username, e)

        token, expires = create_jwt_for_user(user)
        groups = list(user.groups.values_list("name", flat=True))

        user_payload = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "name": user.first_name or user.username,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "groups": groups,
        }

        return Response(
            {
                "token": token,
                "expires_in": expires,
                "user": user_payload,
            },
            status=status.HTTP_200_OK,
        )


class SignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.is_active = False  # 관리자 승인 대기
        user.save()
        return Response(
            {"detail": "가입 신청이 완료되었습니다. 관리자 승인 후 로그인 가능합니다."},
            status=status.HTTP_201_CREATED,
        )


class GroupListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        groups = Group.objects.all().order_by("id")
        return Response(
            [{"id": g.id, "name": g.name} for g in groups],
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """
    로그인한 사용자 정보 조회용 엔드포인트 (/api/me).
    Dashboard.tsx에서 관리자 여부 판단 등에 사용.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        groups = list(user.groups.values_list("name", flat=True))

        profile = Profile.objects.filter(user=user).first()
        # 필요한 최소 정보 + 선택적 프로필 정보
        payload = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "name": user.first_name or user.username,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "groups": groups,
        }
        if profile:
            payload["phone"] = getattr(profile, "phone", "") or ""
            payload["company"] = getattr(profile, "company", "") or ""

        return Response(payload, status=status.HTTP_200_OK)


# ===================================================================
# II. PDF 분석 & 결과 응답
# ===================================================================
class AnalyzeView(APIView):
    """PDF 파일을 분석하고 엑셀을 반환. records.ProcessedPDF에 기록."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @transaction.atomic
    def post(self, request):
        files = request.FILES.getlist("files")
        if not files:
            return Response(
                {"detail": "PDF 파일을 'files' 필드에 첨부하세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 업로드 제한
        if hasattr(settings, "MAX_FILES_PER_REQ") and len(files) > settings.MAX_FILES_PER_REQ:
            return Response(
                {"detail": f"최대 {settings.MAX_FILES_PER_REQ}개까지 업로드 가능합니다."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        if hasattr(settings, "MAX_FILE_BYTES"):
            overs = [f.name for f in files if getattr(f, "size", 0) and f.size > settings.MAX_FILE_BYTES]
            if overs:
                mb = settings.MAX_FILE_BYTES // (1024 * 1024)
                return Response(
                    {"detail": f"파일당 {mb}MB를 초과할 수 없습니다.", "oversize": overs},
                    status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )

        # 🔽 템플릿 선택 (쿼리/폼 둘 다 허용, 기본값 a4)
        tpl_key = (
            (request.query_params.get("template_size") or "").strip().lower()
            or (request.data.get("template_size") or "").strip().lower()
            or "a4"
        )
        template_path = config.TEMPLATE_FILES.get(tpl_key, config.TEMPLATE_FILE_A4)

        try:
            output_paths = self._process_files_and_log(files, request.user, template_path)

            if not output_paths:
                return Response(
                    {"detail": "처리된 파일이 없거나 유효한 상품 정보를 찾을 수 없습니다."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if len(output_paths) == 1:
                return self._create_single_file_response(output_paths[0])
            return self._create_zip_file_response(output_paths)

        except Exception as e:
            logger.exception("PDF 분석 중 치명적 오류 발생")
            return Response(
                {"detail": "파일 분석 중 서버 오류가 발생했습니다.", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _process_files_and_log(self, files, user, template_path: str):
        session_id = uuid.uuid4().hex[:8]
        output_gcs_paths = []
        temp_dir = str(getattr(settings, "FILE_UPLOAD_TEMP_DIR", tempfile.gettempdir()))

        for f in files:
            # 1) 원본 PDF 저장
            gcs_pdf_path = f"uploads/{user.username}/{session_id}/{f.name}"
            actual_pdf_path = default_storage.save(gcs_pdf_path, f)

            temp_pdf_path = None
            temp_xlsx_path = None

            try:
                # 2) 임시 PDF로 다운로드 후 파이프라인 실행
                tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=temp_dir)
                temp_pdf_path = tmp_pdf.name
                with default_storage.open(actual_pdf_path, "rb") as gcs_file:
                    tmp_pdf.write(gcs_file.read())
                tmp_pdf.close()

                extracted = extract_data_from_pdf(temp_pdf_path)
                if not extracted or not extracted.get("products"):
                    logger.warning("'%s'에서 상품 정보를 추출하지 못했습니다. 건너뜀.", f.name)
                    try:
                        if default_storage.exists(actual_pdf_path):
                            default_storage.delete(actual_pdf_path)
                    except Exception:
                        pass
                    continue

                customer_name = extracted.get("customer_name", Path(f.name).stem)
                xlsx_name = f"{customer_name}_보장분석_결과.xlsx"
                gcs_xlsx_path = f"results/{user.username}/{session_id}/{xlsx_name}"

                # 3) 엑셀 생성 → 업로드 (템플릿 경로 전달)
                tmp_xlsx = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx", dir=temp_dir)
                temp_xlsx_path = tmp_xlsx.name
                tmp_xlsx.close()

                try:
                    # 권장 시그니처
                    unmapped_items, excluded_words = excel_handler.create_analysis_report(
                        extracted, temp_xlsx_path, base_template_path=template_path
                    )
                except TypeError:
                    # 구버전 폴백(위치 인수)
                    unmapped_items, excluded_words = excel_handler.create_analysis_report(
                        extracted, temp_xlsx_path, template_path
                    )

                with open(temp_xlsx_path, "rb") as xfp:
                    default_storage.save(gcs_xlsx_path, xfp)

                # 4) 처리 기록
                if _RECORDS_OK:
                    try:
                        ProcessedPDF.objects.create(
                            user=user,
                            original_filename=f.name,
                            file_size=getattr(f, "size", 0) or 0,
                            saved_path=actual_pdf_path,  # 업로드 저장 경로
                            unmapped_items=list(unmapped_items or []),
                            excluded_words=list(excluded_words or []),
                        )
                    except Exception as e:
                        logger.error("ProcessedPDF 기록 실패: %s", e)

                logger.info(
                    "'%s' 처리 완료 (사용자: %s, 템플릿: %s)",
                    f.name,
                    getattr(user, "username", "anon"),
                    template_path,
                )

                # 5) 응답용 결과 목록
                output_gcs_paths.append(gcs_xlsx_path)

            except Exception as e:
                logger.error("파일 처리 중 오류: %s (파일: %s)", e, f.name)
                # 트랜잭션 롤백 유도
                raise

            finally:
                # 임시 파일 정리
                try:
                    if temp_pdf_path and os.path.exists(temp_pdf_path):
                        os.remove(temp_pdf_path)
                except Exception:
                    pass
                try:
                    if temp_xlsx_path and os.path.exists(temp_xlsx_path):
                        os.remove(temp_xlsx_path)
                except Exception:
                    pass

        return output_gcs_paths

    def _create_single_file_response(self, gcs_path: str):
        try:
            gcs_file = default_storage.open(gcs_path, "rb")
            file_name = Path(gcs_path).name
            resp = FileResponse(
                gcs_file,
                as_attachment=True,
                filename=file_name,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            resp["Access-Control-Expose-Headers"] = "Content-Disposition"
            return resp
        except Exception as e:
            logger.error("결과 파일 응답 생성 중 오류: %s", e)
            return Response(
                {"detail": "결과 파일을 가져오는 중 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _create_zip_file_response(self, gcs_paths: list[str]):
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in gcs_paths:
                try:
                    with default_storage.open(p, "rb") as fp:
                        zf.writestr(Path(p).name, fp.read())
                except Exception as e:
                    logger.warning("ZIP 추가 중 오류(건너뜀): %s (%s)", p, e)
        buf.seek(0)
        resp = HttpResponse(buf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = 'attachment; filename="result.zip"'
        resp["Access-Control-Expose-Headers"] = "Content-Disposition"
        return resp


# ===================================================================
# III. 비밀번호 재설정
# ===================================================================
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user_id = (request.data.get("id") or "").strip()
        user = (
            User.objects.filter(email__iexact=user_id).first()
            or User.objects.filter(username=user_id).first()
        )

        code = None
        if user and user.email:
            code = _make_code()
            PasswordResetCode.objects.create(
                user=user,
                code_hash=_hash(code),
                expires_at=now() + timedelta(minutes=10),
            )
            try:
                send_mail(
                    "[보장분석] 비밀번호 재설정 인증코드",
                    f"인증코드: {code}\n이 코드는 10분간 유효합니다.",
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True,
                )
            except Exception:
                pass

        # 개발 편의: DEBUG일 때만 코드 회신
        if settings.DEBUG and user and code:
            logger.info("[DEBUG] PW-Reset Code for %s: %s", user.username, code)
            return Response(
                {"detail": "인증코드가 발송되었습니다.", "dev_code": code},
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "detail": "요청이 접수되었습니다. 계정이 존재하고 이메일이 등록된 경우, 인증코드가 발송됩니다."
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        code = (request.data.get("code") or "").strip()

        user = User.objects.filter(username=username).first()
        if not user:
            return Response({"detail": "코드가 유효하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)

        reset_code = (
            PasswordResetCode.objects.filter(
                user=user, used_at__isnull=True, expires_at__gte=now()
            )
            .order_by("-created_at")
            .first()
        )
        if not reset_code:
            return Response(
                {"detail": "코드가 만료되었거나 유효하지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if reset_code.attempts >= 5:
            return Response(
                {"detail": "시도 횟수를 초과했습니다. 다시 요청해주세요."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if _hash(code) != reset_code.code_hash:
            reset_code.attempts += 1
            reset_code.save(update_fields=["attempts"])
            return Response(
                {"detail": "코드가 유효하지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reset_code.used_at = now()
        reset_code.save(update_fields=["used_at"])
        return Response({"reset_token": _make_reset_token(user.id)}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = (request.data.get("reset_token") or "").strip()
        new_pw = (request.data.get("new_password") or "")

        if len(new_pw) < 8 or " " in new_pw:
            return Response(
                {"detail": "비밀번호는 공백 없이 8자 이상이어야 합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_id = _verify_reset_token(token)
            user = User.objects.get(id=user_id)
        except (signing.SignatureExpired, signing.BadSignature, User.DoesNotExist):
            return Response(
                {"detail": "토큰이 유효하지 않거나 만료되었습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_pw)
        user.save()
        return Response(
            {"detail": "비밀번호가 성공적으로 변경되었습니다."},
            status=status.HTTP_200_OK,
        )


# ===================================================================
# IV. 정리 작업(Cloud Scheduler 호출용)
# ===================================================================
class MaintenanceCleanupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.headers.get("X-Cleanup-Token", "")
        expected = os.environ.get("CLEANUP_TOKEN", "")
        if not expected or token != expected:
            return Response({"detail": "Forbidden"}, status=403)

        # 보존기간: 헤더/쿼리/ENV 우선순위
        days = (
            request.query_params.get("days")
            or request.headers.get("X-Cleanup-Days")
            or os.environ.get("CLEANUP_RETENTION_DAYS", "14")
        )

        # 1) DB 정리
        try:
            subprocess.run(
                ["python", "manage.py", "cleanup_old_records", "--days", str(days)],
                check=True,
            )
        except Exception as e:
            return Response({"detail": f"DB cleanup failed: {e}"}, status=500)

        # 2) 파일 로그 정리
        try:
            subprocess.run(["python", "cleanup_logs.py"], check=True)
        except Exception as e:
            return Response({"detail": f"Log cleanup failed: {e}"}, status=500)

        return Response({"detail": "cleanup OK", "days": int(days)}, status=200)

class NoticeGetView(APIView):
    """
    대시보드 상단 공지 로드용 (/api/notice/get)
    누구나 읽기 가능.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        notice, _ = Notice.objects.get_or_create(key="main", defaults={"text": ""})
        return Response({"notice": notice.text}, status=status.HTTP_200_OK)


class NoticeUpdateView(APIView):
    """
    공지 수정용 (/api/notice/update)
    staff / superuser만 수정 가능.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not (user.is_staff or user.is_superuser):
            return Response({"detail": "공지 수정 권한이 없습니다."},
                            status=status.HTTP_403_FORBIDDEN)

        text = (request.data.get("text") or "").strip()
        notice, _ = Notice.objects.get_or_create(key="main", defaults={"text": ""})
        notice.text = text
        notice.save(update_fields=["text", "updated_at"])
        return Response({"notice": notice.text}, status=status.HTTP_200_OK)
