# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
from pathlib import Path
from .core import analyze_pdf_file, analyze_many

def main() -> None:
    ap = argparse.ArgumentParser(description="보장분석 PDF→XLSX 배치 실행")
    ap.add_argument(
        "--input", "-i",
        nargs="*",
        help="분석할 경로(파일/폴더/글롭). 미지정 시 config.INPUT_DIR의 모든 PDF 처리",
    )
    ap.add_argument(
        "--output", "-o",
        help="결과 저장 폴더. 미지정 시 환경변수/플랫폼 기본값 사용",
    )
    ap.add_argument(
        "--template", "-t",
        help="엑셀 템플릿 파일 경로. 미지정 시 config.TEMPLATE_FILE",
    )
    ap.add_argument(
        "--single",
        action="store_true",
        help="단일 파일 모드(첫 입력만 처리)",
    )
    args = ap.parse_args()

    if args.single and args.input:
        # 첫 번째 입력만 단건 처리
        p = Path(args.input[0])
        res = analyze_pdf_file(p, out_dir=args.output, template_file=args.template)
        print(res)
        return

    # 기본: 일괄 처리
    results = analyze_many(args.input, out_dir=args.output, template_file=args.template)
    for r in results:
        print(r)

if __name__ == "__main__":
    main()
