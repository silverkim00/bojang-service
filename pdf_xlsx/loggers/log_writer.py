# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import re

# 외부 의존: utils.format_amount_short, utils.parse_amount
try:
    from utils import format_amount_short, parse_amount
except Exception:
    # 실패 시 안전 폴백 (로그 출력은 원문 금액 그대로)
    def format_amount_short(v):  # type: ignore
        try:
            v = int(v)
            if v <= 0: return "-"
            # 아주 단순 폴백(만/억 축약 없음)
            return f"{v:,}"
        except Exception:
            return "-"
    def parse_amount(s):  # type: ignore
        try:
            s = str(s or "").strip()
            if not s: return 0
            # 숫자만 있으면 정수화, 아니면 실패
            t = re.sub(r"[^\d]", "", s)
            return int(t) if t.isdigit() else 0
        except Exception:
            return 0

# ───────────────────────── 유틸 ─────────────────────────
def _nz(s):
    return s if isinstance(s, str) else ""

def _line(cols):
    return " | ".join(x if (x is not None and x != "") else "-" for x in cols) + " |"

def _fmt_amt_cell(c: Dict) -> str:
    """
    금액 표기 규칙:
      1) _parsed_amount가 양수면 → 축약 표기
      2) amount 원문을 parse_amount로 파싱 성공하면 → 축약 표기
      3) 둘 다 실패하면 → 원문 문자열 그대로
      4) 전부 없으면 → "-"
    """
    # 1) 미리 파싱된 값
    v = c.get("_parsed_amount")
    if isinstance(v, (int, float)) and v > 0:
        try:
            return format_amount_short(int(v))
        except Exception:
            pass

    # 2) 원문 파싱 시도
    amt_raw = c.get("amount")
    if isinstance(amt_raw, (int, float)):
        try:
            vv = int(amt_raw)
            return format_amount_short(vv) if vv > 0 else (str(amt_raw).strip() or "-")
        except Exception:
            pass
    else:
        try:
            pv = parse_amount(_nz(amt_raw))
            if isinstance(pv, int) and pv > 0:
                return format_amount_short(pv)
        except Exception:
            pass

    # 3) 원문 그대로
    s = _nz(amt_raw).strip()
    return s if s else "-"

def _block_no(c: Dict, seq: int) -> str:
    """
    블럭 번호 보정: 원본 7 → 표시 1. 최소 1.
    c.block_no 또는 c._raw.block_no / c._raw.block 사용.
    """
    raw = None
    if isinstance(c, dict):
        raw = c.get("block_no") or (
            isinstance(c.get("_raw"), dict) and (c["_raw"].get("block_no") or c["_raw"].get("block"))
        )
    if raw is None:
        return str(seq)
    try:
        return str(max(int(str(raw).strip()) - 6, 1))
    except Exception:
        return str(seq)

def _header(product: dict) -> str:
    comp  = (product.get("company") or product.get("회사") or "").strip()
    prod  = (product.get("product_name") or product.get("상품명") or "").strip()
    cdate = (product.get("contract_date") or "").strip()
    prem  = (product.get("monthly_premium") or "").strip()
    tail  = []
    if cdate: tail.append(f"가입일자: {cdate}")
    if prem:  tail.append(f"월납: {prem}")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("")
    lines.append("".ljust(92, "="))
    lines.append(f"상품 시작 [{stamp}] : {comp} | {prod} {'| ' + ' | '.join(tail) if tail else ''}")
    lines.append("주요 보장 목록 (블럭 1부터)")
    lines.append("".ljust(92, "-"))
    # 고정 컬럼 헤더(요청 사양): 블럭 | 유형 | 명칭 | 협회명 | 금액(축약) | 이유 | 힌트
    lines.append("블럭 | 유형 | 명칭 | 협회명 | 금액(축약) | 이유 | 힌트 |")
    return "\n".join(lines) + "\n"

def _footer() -> str:
    lines = []
    lines.append("".ljust(92, "-"))
    lines.append("#######  상품 종료 (END OF PRODUCT)  #######")
    lines.append("".ljust(92, "="))
    lines.append("")
    return "\n".join(lines)

# ───────────────────────── 메인 API ─────────────────────────
def write(path: str, items: List[Dict], product: dict | None = None) -> None:
    """
    고정 포맷으로 로그를 append:
      - 상품 헤더/푸터 포함
      - 블럭 보정(7→1)
      - 컬럼: 블럭 | 유형 | 명칭 | 협회명 | 금액(축약) | 이유 | 힌트
      - 금액: 축약 표기(파싱 실패 시 원문)
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8-sig") as f:
        if product:
            f.write(_header(product))

        for i, c in enumerate(items, 1):
            ty    = _nz(c.get("type"))
            name  = _nz(c.get("name"))
            assoc = _nz(c.get("association_name")) or "-"
            amt   = _fmt_amt_cell(c)
            reason= (c.get("_reason") or "").strip()
            hint  = (c.get("_hint") or "").strip()

            row = _line([_block_no(c, i), ty or "-", name or "-", assoc or "-", amt, reason, hint])
            f.write(row + "\n")

        if product:
            f.write(_footer())
