# records/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class ProcessedPDF(models.Model):
    """
    PDF 변환 처리 기록.
    bojang_api/views.py의 AnalyzeView가 생성합니다.
    """
    # 1. 누가 (User)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL, # 유저가 탈퇴해도 로그는 남김
        null=True,
        blank=True,
        related_name="processed_pdfs"
    )
    
    # 2. 언제 (Timestamp)
    processed_at = models.DateTimeField(default=timezone.now, db_index=True)
    
    # 3. 무엇을 (File Info)
    original_filename = models.CharField(max_length=512, help_text="업로드 시 원본 파일명")
    file_size = models.BigIntegerField(default=0, help_text="파일 크기 (bytes)")
    
    # 4. 어디에 (Storage Path)
    saved_path = models.CharField(max_length=1024, help_text="GCS 등 스토리지에 저장된 실제 경로")
    
    # 5. 분석 결과 (pdf_xlsx에서 반환된 값)
    unmapped_items = models.JSONField(default=list, help_text="매핑에 실패한 항목 리스트")
    excluded_words = models.JSONField(default=list, help_text="분석에서 제외된 단어 리스트")

    class Meta:
        ordering = ["-processed_at"]
        verbose_name = "PDF 처리 기록"
        verbose_name_plural = "PDF 처리 기록 목록"

    def __str__(self):
        username = self.user.username if self.user else "N/A"
        return f"[{username}] {self.original_filename} ({self.file_size} bytes)"


class CompanyIP(models.Model):
    """
    관리자가 등록하는 회사/사무실의 고정 IP.
    management_views.py의 CompanyIPView가 관리합니다.
    """
    ip_address = models.GenericIPAddressField(unique=True, help_text="회사/지점의 IP 주소 (IPv4 또는 IPv6)")
    description = models.CharField(max_length=255, blank=True, help_text="설명 (예: 본사, 강남지점)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ip_address"]
        verbose_name = "회사 IP"
        verbose_name_plural = "회사 IP 목록"

    def __str__(self):
        return f"{self.ip_address} ({self.description})"


class LoginLog(models.Model):
    """
    사용자 로그인 기록 (IP 추적용).
    """
    # 1. 누가 (User)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE, # 유저 탈퇴 시 같이 삭제
        related_name="login_logs"
    )
    
    # 2. 언제 (Timestamp)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    # 3. 어디서 (IP)
    ip_address = models.GenericIPAddressField(help_text="로그인한 사용자의 IP 주소")

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "로그인 기록"
        verbose_name_plural = "로그인 기록 목록"

    def __str__(self):
        return f"[{self.user.username}] logged in from {self.ip_address} at {self.timestamp}"