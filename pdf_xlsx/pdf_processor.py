# -*- coding: utf-8 -*-
from __future__ import annotations
import re
import fitz
from pathlib import Path
from .logger_setup import logger

def extract_customer_name(doc: fitz.Document, pdf_path: Path) -> str:
    try:
        first_page_text = doc[0].get_text("text")
        match = re.search(r'([가-힣]+)\s*\(?\d+세\s*,\s*[가-힣]+\)?\s*님의', first_page_text)
        if match:
            customer_name = match.group(1).strip().replace("님의상품별가입담보상세", "").strip()
            return customer_name.split('/')[-1] if '/' in customer_name else customer_name
    except Exception as e:
        logger.warning(f"고객 이름 자동 추출 실패: {e}. 파일명을 사용합니다.")
    return re.sub(r'_.*', '', pdf_path.stem)

def parse_product_info(blocks: list) -> dict:
    info = {
        "company": "정보없음", "product_name": "정보없음", "contract_date": "정보없음",
        "monthly_premium": "정보없음", "payment_period": "정보없음", "maturity_period": "정보없음",
        "coverages": []
    }

    date_pattern_found = False

    # 회사명 (Block 3)
    try:
        info["company"] = blocks[2][4].split('|')[0].strip()
    except IndexError:
        logger.warning("회사명 블록(3)을 찾을 수 없습니다.")

    # 상품명 (Block 4)
    try:
        info["product_name"] = blocks[3][4].replace('|', ' ').strip()
    except IndexError:
        logger.warning("상품명 블록(4)을 찾을 수 없습니다.")

    # 날짜(가입일/만기일) 및 월 보험료 (Block 6) - 1순위
    try:
        block_006_text = blocks[5][4]
        if date_match := re.search(r'(\d{4}-\d{2}-\d{2})~(\d{4}-\d{2}-\d{2})', block_006_text):
            info["contract_date"] = date_match.group(1)
            info["maturity_period"] = date_match.group(2)
            date_pattern_found = True

        if "납입완료" in block_006_text:
            info["monthly_premium"] = "납입완료"
        elif any(s in block_006_text for s in ["보험료미제공", "월납/0년"]):
            info["monthly_premium"] = "보험료미제공"
        elif premium_match := re.search(r'([\d,]+)원', block_006_text):
            info["monthly_premium"] = premium_match.group(1)
    except IndexError:
        logger.warning("보험료/날짜 블록(6)을 찾을 수 없습니다.")

    # 납입기간 (Block 5) - 독립적으로 실행
    try:
        block_005_text = blocks[4][4]
        period_parts = [p.strip() for p in block_005_text.split('/') if p.strip()]
        payment_period_str = next((p for p in period_parts if '년' in p), None)
        if payment_period_str:
            info["payment_period"] = payment_period_str
    except IndexError:
        logger.warning("납입기간 블록(5)을 찾을 수 없습니다.")

    # 예비(Fallback) 로직
    if not date_pattern_found:
        try:
            if date_match_fallback := re.search(r'(\d{4}-\d{2}-\d{2})', blocks[2][4]):
                info["contract_date"] = date_match_fallback.group(1)
        except IndexError:
            pass

        try:  # 만기 정보는 아직 설정되지 않았을 때만 Block 5에서 가져옴
            if info["maturity_period"] == "정보없음":
                period_parts = [p.strip() for p in blocks[4][4].split('/') if p.strip()]
                if len(period_parts) >= 2:
                    info["maturity_period"] = period_parts[-1]
        except IndexError:
            pass

    # 담보 (Block 7부터)
    try:
        for block in blocks[6:]:
            text = block[4].replace('\n', ' | ')
            parts = [p.strip() for p in text.split('|') if p.strip()]
            if len(parts) >= 5:
                info["coverages"].append({"type": parts[1], "name": parts[2], "association_name": parts[3], "amount": parts[4]})
            elif len(parts) == 4 and any(c.isdigit() for c in parts[-1]):
                info["coverages"].append({"type": parts[1], "name": parts[2], "association_name": parts[2], "amount": parts[3]})
    except IndexError:
        logger.warning("담보 블록(7+)을 처리하는 중 오류가 발생했습니다.")

    return info

def extract_data_from_pdf(pdf_path: Path) -> dict:
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.error(f"'{pdf_path}' 파일을 열 수 없습니다: {e}")
        return {}

    customer_name = extract_customer_name(doc, pdf_path)
    all_products, processed_pages = [], set()

    for page_num, page in enumerate(doc):
        if page_num in processed_pages:
            continue

        blocks = sorted(page.get_text("blocks"), key=lambda b: (b[1], b[0]))
        if len(blocks) < 4:
            continue

        product_name_block = blocks[3][4]
        current_product_blocks = blocks

        # (1/2) → (2/2) 병합 (엄격)
        if '(1/2)' in product_name_block and page_num + 1 < len(doc):
            base_name = product_name_block.split('(1/2)')[0].strip()
            next_page_blocks = sorted(doc[page_num + 1].get_text("blocks"), key=lambda b: (b[1], b[0]))

            # 다음 페이지 4번 블록에 동일 base 포함 + (2/2) 표시 확인
            next_name = next_page_blocks[3][4] if len(next_page_blocks) > 3 else ""
            strict_pair_ok = (base_name in next_name) and ('(2/2)' in next_name)

            if strict_pair_ok:
                header_blocks = blocks[:6] if len(blocks) >= 6 else blocks
                coverage_blocks = (blocks[6:] if len(blocks) >= 7 else []) + \
                                  (next_page_blocks[6:] if len(next_page_blocks) >= 7 else [])
                current_product_blocks = header_blocks + coverage_blocks
                processed_pages.add(page_num + 1)
                logger.info(f"PDFMERGE: '{base_name}' (1/2)+(2/2) merged at pages {page_num+1},{page_num+2}")
            else:
                logger.info(f"PDFMERGE: skip - pair not strict for base='{base_name}'")

        info = parse_product_info(current_product_blocks)
        all_products.append(info)

    doc.close()
    return {"customer_name": customer_name, "products": all_products}
