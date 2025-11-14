# records/apps.py
from django.apps import AppConfig

class RecordsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'records'
    verbose_name = '활동 기록 관리' # Django Admin에서 보일 이름