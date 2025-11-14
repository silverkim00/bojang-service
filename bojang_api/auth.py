# bojang_api/auth.py

from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import AccessToken

def create_jwt_for_user(user: User) -> tuple[str, float]:
    """
    주어진 사용자에 대해 JWT Access Token을 생성합니다.
    
    이 함수는 settings.py의 SIMPLE_JWT 설정을 자동으로 가져와 사용하므로,
    토큰의 비밀 키, 유효 시간, 알고리즘이 항상 프로젝트 전체 설정과 일치합니다.
    """
    
    # 1. simple-jwt의 표준 방식을 사용하여 토큰 객체를 생성합니다.
    #    이렇게 하면 settings.py의 SIGNING_KEY와 항상 동일한 키로 서명됩니다.
    token = AccessToken.for_user(user)
    
    # 2. 토큰의 유효 시간을 settings.py 설정에서 직접 가져옵니다.
    #    기본값이 없을 경우를 대비해 12시간으로 설정합니다.
    lifetime = settings.SIMPLE_JWT.get("ACCESS_TOKEN_LIFETIME", timedelta(hours=12))
    
    # 3. 문자열 형태의 토큰과, 유효 시간(초 단위)을 함께 반환합니다.
    return str(token), lifetime.total_seconds()