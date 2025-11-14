# bojang_api/management_views.py

# --- 1) 표준/장고/DRF 임포트 ---
import logging
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import validate_ipv46_address
from django.db.models import Count
from django.http import FileResponse
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# --- 2) records 앱 임포트 (★수정★) -----------------------------------------
# try...except 가드 블록 전체 삭제
from records.models import ProcessedPDF, LoginLog, CompanyIP
# _LOGS_OK 변수 및 더미 클래스(_NoQS, _NoModel) 전체 삭제
# ------------------------------------------------------------------------


# ===================================================================
# I. 대시보드 API
# ===================================================================
class DashboardStatsView(APIView):
    """
    관리자 대시보드 통계:
    - 오늘 처리된 총 PDF 개수
    - 사용자별 오늘 작업량
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        today_start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)

        today_pdfs = ProcessedPDF.objects.filter(
            processed_at__gte=today_start, processed_at__lt=today_end
        )
        
        # (★수정★) getattr 및 _LOGS_OK 체크 제거
        total_today = today_pdfs.count()

        user_stats_qs = (
            today_pdfs.values("user__username")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        stats = {
            "total_processed_today": total_today,
            "user_activity_today": list(user_stats_qs), # (★수정★) _LOGS_OK 체크 제거
        }
        return Response(stats, status=status.HTTP_200_OK)


# ===================================================================
# II. 회원 관리 API
# ===================================================================
class UserListView(APIView):
    """모든 사용자 목록 조회"""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Group 정보까지 함께 효율적으로 가져옵니다.
        users = User.objects.select_related("profile").prefetch_related("groups").all().order_by("-date_joined")

        data = []
        for u in users:
            profile = getattr(u, "profile", None)
            
            # 1. 그룹 연동 수정: 실제 그룹 목록을 가져옵니다.
            current_groups = ", ".join([g.name for g in u.groups.all()])
            
            # 2. 이름 필드 불일치 해결:
            # - Profile.full_name(가입 시점의 전체 이름)을 기본으로 사용합니다.
            display_name = getattr(profile, "full_name", "")
            
            # - Profile.full_name이 없거나 비어 있다면, Admin에서 수정한 성/이름을 합쳐서 사용합니다.
            if not display_name:
                # User 모델의 last_name(성)과 first_name(이름)을 합칩니다.
                user_name_parts = [u.last_name, u.first_name]
                # 공백이 아닌 이름만 결합 (예: '홍' + '길동' = '홍길동')
                display_name = "".join([n.strip() for n in user_name_parts if n.strip()])

            data.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                # 통합된 display_name 사용
                "full_name": display_name or "", 
                # 현재 그룹 이름 사용
                "affiliation": current_groups or "", 
                "is_active": u.is_active,
                "date_joined": timezone.localtime(u.date_joined).strftime("%Y-%m-%d %H:%M"),
            })
        return Response(data, status=status.HTTP_200_OK)

class UserActivationView(APIView):
    """특정 사용자의 활성/비활성 전환"""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "사용자를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        if user == request.user:
            return Response({"detail": "자기 자신의 계정은 비활성화할 수 없습니다."}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return Response(
            {"detail": "사용자 상태가 성공적으로 변경되었습니다.", "is_active": user.is_active},
            status=status.HTTP_200_OK
        )


# ===================================================================
# III. 파일 관리 API
# ===================================================================
class ProcessedPDFListView(APIView):
    """처리된 PDF 기록 목록"""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # (★수정★) _NoQS 걱정 없이 바로 쿼리
        qs = ProcessedPDF.objects.select_related("user").all().order_by("-processed_at")
        
        data = []
        for r in qs: # (★수정★) getattr 제거
            data.append({
                "id": r.id,
                "username": r.user.username if r.user else "알 수 없음",
                "original_filename": r.original_filename,
                "file_size": r.file_size,
                "processed_at": (
                    timezone.localtime(r.processed_at).strftime("%Y-%m-%d %H:%M")
                    if r.processed_at else ""
                ),
            })
        return Response(data, status=status.HTTP_200_OK)


class ProcessedPDFDetailView(APIView):
    """특정 PDF의 상세 로그(매핑 실패, 제외 단어)"""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, pdf_id):
        try:
            pdf_record = ProcessedPDF.objects.get(id=pdf_id)
        except ProcessedPDF.DoesNotExist:
            return Response({"detail": "해당 기록을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        # (★수정★) getattr 제거
        data = {
            "id": pdf_record.id,
            "original_filename": pdf_record.original_filename,
            "unmapped_items": pdf_record.unmapped_items or [],
            "excluded_words": pdf_record.excluded_words or [],
        }
        return Response(data, status=status.HTTP_200_OK)


class ProcessedPDFDownloadView(APIView):
    """특정 PDF 원본 파일 다운로드"""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, pdf_id):
        try:
            pdf_record = ProcessedPDF.objects.get(id=pdf_id)
        except ProcessedPDF.DoesNotExist:
            return Response({"detail": "해당 기록을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        file_path = pdf_record.saved_path # (★수정★) getattr 제거
        if not file_path:
            return Response({"detail": "저장 경로가 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        try:
            f = default_storage.open(file_path, "rb")
            return FileResponse(f, as_attachment=True, filename=pdf_record.original_filename)
        except Exception as e:
            logger.error(f"파일 여는 중 오류 ({file_path}): {e}")
            return Response({"detail": "서버에서 원본 파일을 찾거나 열 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)


class ProcessedPDFDeleteView(APIView):
    """특정 PDF 기록 + 실제 파일 삭제"""
    permission_classes = [permissions.IsAdminUser]

    def delete(self, request, pdf_id):
        try:
            pdf_record = ProcessedPDF.objects.get(id=pdf_id)
        except ProcessedPDF.DoesNotExist:
            return Response({"detail": "해당 기록을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        file_path = pdf_record.saved_path # (★수정★) getattr 제거
        try:
            if file_path and default_storage.exists(file_path):
                default_storage.delete(file_path)
                logger.info(f"파일 삭제 성공: {file_path}")
            else:
                logger.warning(f"삭제 대상 파일 없음 또는 경로 비어있음: {file_path}")
        except Exception as e:
            logger.error(f"파일 삭제 실패 ({file_path}): {e}")

        pdf_record.delete() # (★수정★) try/except 제거
        return Response(status=status.HTTP_204_NO_CONTENT)


# ===================================================================
# IV. IP 추적 및 관리 API
# ===================================================================
class UserLoginLogView(APIView):
    """특정 사용자의 로그인 기록"""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "사용자를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        # (★수정★) _LOGS_OK 체크 제거
        company_ips = set(CompanyIP.objects.values_list("ip_address", flat=True))
        logs_qs = LoginLog.objects.filter(user=user).order_by("-timestamp")
        logs = list(logs_qs)

        external_ip_counts = (
            LoginLog.objects.exclude(ip_address__in=company_ips)
            .values("ip_address").annotate(count=Count("ip_address"))
        )
        suspicious_ips = {row["ip_address"] for row in external_ip_counts}

        data = [ # (★수정★) getattr 제거
            {
                "id": log.id,
                "ip_address": log.ip_address,
                "timestamp": (
                    timezone.localtime(log.timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    if log.timestamp else ""
                ),
                "is_company_ip": log.ip_address in company_ips,
                "is_suspicious": log.ip_address in suspicious_ips,
            }
            for log in logs
        ]
        return Response({"username": user.username, "logs": data}, status=status.HTTP_200_OK)


class CompanyIPView(APIView):
    """회사 IP 목록 조회/추가/삭제"""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        ips = CompanyIP.objects.all().order_by("ip_address")
        data = [ # (★수정★) getattr 제거
            {
                "id": ip.id,
                "ip_address": ip.ip_address,
                "description": ip.description or "",
            }
            for ip in ips
        ]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        ip_address = (request.data.get("ip_address") or "").strip()
        description = (request.data.get("description") or "").strip()

        if not ip_address:
            return Response({"detail": "IP 주소를 입력해주세요."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_ipv46_address(ip_address)
        except ValidationError:
            return Response({"detail": "유효하지 않은 IP 주소 형식입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # (★수정★) getattr 제거
        if CompanyIP.objects.filter(ip_address=ip_address).exists():
            return Response({"detail": "이미 등록된 IP 주소입니다."}, status=status.HTTP_400_BAD_REQUEST)

        created = CompanyIP.objects.create(ip_address=ip_address, description=description)
        return Response( # (★수정★) getattr 제거
            {
                "id": created.id,
                "ip_address": created.ip_address,
                "description": created.description,
            },
            status=status.HTTP_201_CREATED
        )

    def delete(self, request):
        ip_id = request.data.get("id")
        if not ip_id:
            return Response({"detail": "삭제할 IP의 ID를 제공해야 합니다."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ip_record = CompanyIP.objects.get(id=ip_id)
        except CompanyIP.DoesNotExist:
            return Response({"detail": "해당 IP를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        ip_record.delete() # (★수정★) try/except 제거
        return Response(status=status.HTTP_204_NO_CONTENT)