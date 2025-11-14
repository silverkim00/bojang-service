# ---- Backend only image (no frontend stage) ----
    FROM python:3.11-slim

    ENV PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1 \
        DJANGO_SETTINGS_MODULE=bojang_api.settings \
        PYTHONPATH=/app \
        # 하위호환 기본값(A4): 기존 코드가 TEMPLATE_FILE만 읽어도 안전
        TEMPLATE_FILE=/app/templates/base_template2.xlsx \
        TEMPLATE_FILE_A3=/app/templates/base_template.xlsx \
        TEMPLATE_FILE_A4=/app/templates/base_template2.xlsx \
        PORT=8080
    
    WORKDIR /app
    
    # OS deps
    RUN apt-get update && \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
          build-essential tzdata && \
        ln -snf /usr/share/zoneinfo/Asia/Seoul /etc/localtime && \
        echo Asia/Seoul > /etc/timezone && \
        apt-get clean && rm -rf /var/lib/apt/lists/*
    
    # Python deps
    COPY requirements.txt .
    RUN pip install --no-cache-dir --upgrade pip && \
        pip install --no-cache-dir -r requirements.txt && \
        pip install --no-cache-dir gunicorn whitenoise
    
    # 앱 유저
    RUN useradd -m -u 10001 appuser
    
    # 템플릿
    RUN mkdir -p /app/templates
    COPY pdf_xlsx/static/templates/base_template.xlsx  /app/templates/base_template.xlsx
    COPY pdf_xlsx/static/templates/base_template2.xlsx /app/templates/base_template2.xlsx
    
    # 소스
    COPY . .
    
    # 로그 디렉터리 권한
    RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs
    
    # 정적파일 수집 (실패해도 계속)
    RUN python manage.py collectstatic --noinput || true
    
    EXPOSE 8080
    USER appuser
    
    # gunicorn
    CMD ["gunicorn", "bojang_api.wsgi:application", "-b", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "120"]
    