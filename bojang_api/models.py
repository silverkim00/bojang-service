from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=50)
    birthdate = models.DateField()
    affiliation = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # 배포 중 질의 없이 마이그 적용되도록 default로 설정(naive datetime, USE_TZ=False와 일관)
    password_changed_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"{self.full_name} ({self.user.username})"


class PasswordResetCode(models.Model):
    # 비밀번호 재설정 6자리 코드의 해시를 저장
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_codes")
    code_hash = models.CharField(max_length=64)  # sha256 hex(64자)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)  # 사용 처리 시각(미사용=None)
    requested_ip = models.CharField(max_length=45, blank=True, default="")
    requested_ua = models.CharField(max_length=500, blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["user", "code_hash"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"ResetCode(uid={self.user_id}, exp={self.expires_at:%Y-%m-%d %H:%M:%S})"

class Notice(models.Model):
    key = models.CharField(max_length=50, unique=True, default="main")
    text = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"[{self.key}] {self.text[:20]}"