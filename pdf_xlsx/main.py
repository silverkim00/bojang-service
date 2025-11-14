# pdf_xlsx/main.py (로컬 실행용 - 로그 경로 고정 & 구(옛) 로그 비활성)

import sys
import argparse
import time
from pathlib import Path
from typing import Iterable, List, Optional, Union

# 내부 모듈
import config
from excel_handler import create_analysis_report
from pdf_processor import extract_data_from_pdf
from logger_setup import logger

# ------------------------------------

def _coerce_paths(arg: Union[str, Path, Iterable[Union[str, Path]]]) -> List[Path]:
    paths: List[Path] = []
    def _push(p: Union[str, Path]):
        if p is None: return
        s = str(p).strip()
        if not s: return
        if (";" in s) or ("|" in s):
            for token in s.replace("|", ";").split(";"):
                token = token.strip()
                if token: paths.append(Path(token))
        else:
            paths.append(Path(s))
    if isinstance(arg, (list, tuple, set)):
        for x in arg: _push(x)
    else:
        _push(arg)
    uniq = []
    seen = set()
    for p in paths:
        try:
            q = p.resolve()
        except FileNotFoundError:
            q = Path(p).absolute()
        if q not in seen:
            uniq.append(q)
            seen.add(q)
    return uniq

def _expand_inputs(paths: List[Path]) -> List[Path]:
    files: List[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(list(p.glob("*.pdf"))))
        else:
            files.append(p)
    files = [f for f in files if f.exists() and f.suffix.lower() == ".pdf"]
    return files

# 구(옛) 집계 로그는 더 이상 사용하지 않음(호출 제거)
# def _write_agg_logs(output_dir: Path, all_unmapped, all_excluded):
#     ...

def _anchor_logs_to_output(out: Path):
    """
    새 형식 로그를 결과 XLSX와 같은 폴더에 생성되도록 강제.
    coverage_processor가 모듈 전역에 캐시한 경로도 함께 갱신.
    """
    # 파일명 기본값 보장
    unm_name = getattr(config, "UNMAPPED_LOG_FILE", "unmapped_log.txt")
    exc_name = getattr(config, "EXCLUDED_LOG_FILE", "excluded_log.txt")

    # 절대경로로 고정
    config.UNMAPPED_LOG = str(out / unm_name)
    config.EXCLUDED_LOG = str(out / exc_name)

    # 이미 import된 coverage_processor의 캐시 변수도 업데이트
    try:
        import coverage_processor as CP  # 이미 로드되어 있어도 재바인딩만 수행
        CP._UNMAPPED_LOG = config.UNMAPPED_LOG
        CP._EXCLUDED_LOG = config.EXCLUDED_LOG
    except Exception:
        # 실패해도 치명적이지 않음(coverage_processor가 다음 접근 시 config를 재조회하지 않는 구현이라 갱신 시도만 함)
        pass

def _process_files(pdf_files: List[Path], output_dir: Path) -> None:
    for pdf_path in pdf_files:
        try:
            logger.info(f"--- '{pdf_path.name}' 처리 시작 ---")
            extracted_data = extract_data_from_pdf(pdf_path)
            if not extracted_data or not extracted_data.get("products"):
                logger.warning(f"'{pdf_path.name}'에서 상품 정보를 추출하지 못했습니다.")
                continue
            customer_name = extracted_data.get("customer_name", pdf_path.stem)
            output_path = output_dir / f"{customer_name}_보장분석_결과.xlsx"
            # create_analysis_report 내부에서 coverage_processor가 새 형식 로그를 출력 폴더로 기록
            create_analysis_report(extracted_data, str(output_path))
        except Exception as e:
            logger.error(f"'{pdf_path.name}' 처리 중 심각한 오류 발생: {e}", exc_info=True)

def run_from_ui(
    input_path: Union[str, Path, Iterable[Union[str, Path]]],
    output_dir: Union[str, Path],
    template_file: Optional[Union[str, Path]] = None,
):
    start_time = time.time()
    logger.info("보험 증권 분석 자동화 시스템(UI) 시작")
    orig_template = getattr(config, "TEMPLATE_FILE", None)
    try:
        if template_file:
            config.TEMPLATE_FILE = str(Path(template_file).resolve())
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)

        # ★ 새 로그 경로를 결과 폴더로 앵커링
        _anchor_logs_to_output(out)

        inputs = _expand_inputs(_coerce_paths(input_path))
        if not inputs:
            logger.warning("처리할 PDF가 없습니다.")
            return
        _process_files(inputs, out)

        logger.info("=" * 50)
        logger.info(f"모든 작업 완료(UI). 소요: {time.time() - start_time:.2f}초")
        logger.info(f"결과물 폴더: '{out}'")
        logger.info("=" * 50)
    finally:
        if orig_template is not None:
            config.TEMPLATE_FILE = orig_template

def run_cli(
    input_path: Optional[Union[str, Path, Iterable[Union[str, Path]]]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    template_file: Optional[Union[str, Path]] = None,
):
    start_time = time.time()
    logger.info("보험 증권 분석 자동화 시스템(CLI) 시작")
    if input_path is None: input_path = Path(config.INPUT_DIR)
    if output_dir is None: output_dir = Path(config.OUTPUT_DIR)
    orig_template = getattr(config, "TEMPLATE_FILE", None)
    try:
        if template_file:
            config.TEMPLATE_FILE = str(Path(template_file).resolve())
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)

        # ★ 새 로그 경로를 결과 폴더로 앵커링
        _anchor_logs_to_output(out)

        inputs = _expand_inputs(_coerce_paths(input_path))
        if not inputs:
            logger.warning("처리할 PDF가 없습니다.")
            return
        _process_files(inputs, out)

        logger.info("=" * 50)
        logger.info(f"모든 작업 완료(CLI). 소요: {time.time() - start_time:.2f}초")
        logger.info(f"결과물 폴더: '{out}'")
        logger.info("=" * 50)
    finally:
        if orig_template is not None:
            config.TEMPLATE_FILE = orig_template

def main():
    parser = argparse.ArgumentParser(description="보장 분석 자동화")
    parser.add_argument("--input", nargs="*", help="분석할 PDF 파일/폴더. 미지정 시 config.INPUT_DIR")
    parser.add_argument("--output", help="결과 저장 폴더. 미지정 시 config.OUTPUT_DIR")
    parser.add_argument("--template", help="엑셀 템플릿 파일. 미지정 시 config.TEMPLATE_FILE")
    args = parser.parse_args()
    run_cli(
        input_path=args.input if args.input else None,
        output_dir=args.output if args.output else None,
        template_file=args.template if args.template else None
    )

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"치명적 오류: {e}", exc_info=True)
        sys.exit(1)
