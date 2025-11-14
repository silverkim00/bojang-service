# -*- coding: utf-8 -*-
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils.timezone import now

from records.models import ProcessedPDF


class Command(BaseCommand):
    help = "records.ProcessedPDF 중 오래된 기록을 삭제합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="보존 일수(미지정 시 환경변수 CLEANUP_RETENTION_DAYS 또는 기본 14일)",
        )

    def handle(self, *args, **opts):
        # 우선순위: CLI 인자 > 환경변수 > 기본값
        import os
        retention_days = (
            opts.get("days")
            if opts.get("days") is not None
            else int(os.environ.get("CLEANUP_RETENTION_DAYS", "14"))
        )

        cutoff = now() - timedelta(days=retention_days)
        qs = ProcessedPDF.objects.filter(created_at__lt=cutoff)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING(f"삭제할 항목이 없습니다. (보존 {retention_days}일)"))
            return

        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"{total}건 삭제 완료 (보존 {retention_days}일)"))
