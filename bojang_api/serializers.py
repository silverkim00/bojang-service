# bojang_api/serializers.py
import re
from django.db import transaction
from django.contrib.auth.models import User, Group
from rest_framework import serializers
from .models import Profile

# --- 유효성 검사 로직 ---
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{3,19}$")

def _normalize_birthdate(raw: str) -> str:
    s = (raw or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s
    # Serializer에서는 ValueError 대신 ValidationError를 발생시킵니다.
    raise serializers.ValidationError("생년월일은 8자리 숫자(YYYYMMDD) 또는 YYYY-MM-DD 형식이어야 합니다.")


# --- 회원가입 Serializer ---
class SignupSerializer(serializers.Serializer):
    # 프론트엔드로부터 받을 필드를 정의합니다.
    username = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True) # 비밀번호는 응답에 포함되지 않도록 설정
    full_name = serializers.CharField(max_length=50)
    birthdate = serializers.CharField(max_length=10)
    email = serializers.EmailField() # DRF의 내장 이메일 검증 기능을 사용
    group_id = serializers.IntegerField()

    # username 필드에 대한 추가 검증
    def validate_username(self, value):
        if not USERNAME_RE.match(value):
            raise serializers.ValidationError("아이디는 영문 시작, 영문/숫자 4~20자입니다.")
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("이미 사용 중인 아이디입니다.")
        return value

    # password 필드에 대한 추가 검증
    def validate_password(self, value):
        if len(value) < 8 or " " in value:
            raise serializers.ValidationError("비밀번호는 공백 없이 8자 이상이어야 합니다.")
        return value

    # group_id 필드에 대한 추가 검증
    def validate_group_id(self, value):
        if not Group.objects.filter(id=value).exists():
            raise serializers.ValidationError("유효한 소속(지점)을 선택하세요.")
        return value

    # 모든 필드의 유효성 검사가 통과된 후 호출되는 메소드
    def create(self, validated_data):
        group = Group.objects.get(id=validated_data['group_id'])
        
        try:
            # transaction.atomic으로 User와 Profile 생성을 묶어서 처리 (안전성)
            with transaction.atomic():
                # (★ 수정된 부분 ★) full_name을 User.last_name에 복사
                user = User.objects.create(
                    username=validated_data['username'],
                    email=validated_data['email'],
                    last_name=validated_data['full_name'] # 전체 이름을 last_name에 저장
                )
                user.set_password(validated_data['password'])
                user.save()

                Profile.objects.create(
                    user=user,
                    full_name=validated_data['full_name'],
                    birthdate=_normalize_birthdate(validated_data['birthdate']),
                    affiliation=group.name
                )
                
                user.groups.add(group)
                return user
        except Exception as e:
            # 데이터베이스 생성 중 에러가 발생하면 상세 에러를 반환
            raise serializers.ValidationError(f"서버 오류로 가입에 실패했습니다: {e}")