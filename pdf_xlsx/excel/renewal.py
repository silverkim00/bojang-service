# -*- coding: utf-8 -*-
"""
excel/renewal.py — v2025-11-06r (재작성)
- 토큰 분해(괄호 외부 콤마 기준) + 부분서식(RichText) 안정화
- 갱/비갱 판정: 비갱신 우선 → 갱신 → 모호 시 검정
- 외부 의존 최소화(로컬 정규식/폴백 포함)
"""

from __future__ import annotations

import re
from typing import List, Dict, Tuple

from openpyxl.styles import Font

from ..logger_setup import logger
# 색상/공용은 layout 모듈에서 가져옴
from .layout import GREEN, BLACK

# -----------------------------
# Rich Text 지원 감지
# -----------------------------
try:
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    _RT_SUPPORTED = True
except Exception:
    CellRichText = TextBlock = None
    _RT_SUPPORTED = False


def _trace(tag: str, msg: str) -> None:
    try:
        logger.info(f"TRACE[{tag}] {msg}")
    except Exception:
        pass


# -----------------------------
# 외부 정책 폴백(갱신/비갱신 판정)
# -----------------------------
try:
    # 정책 모듈이 있으면 사용
    from ..rules.ca import cov_is_renewal as _cov_is_renewal  # type: ignore
except Exception:
    def _cov_is_renewal(cov: Dict) -> bool:
        s = f"{str(cov.get('name') or '')}|{str(cov.get('association_name') or '')}"
        if re.search(r"(비\s*갱신형|비갱신)", s, re.I):
            return False
        return ("갱신" in s)


try:
    from ..rules.ca import _RE_NOT_RENEWAL as _CA_RE_NOT_RENEWAL  # type: ignore
except Exception:
    _CA_RE_NOT_RENEWAL = re.compile(r"(비\s*갱신형|비갱신)", re.I)


# -----------------------------
# 토큰 분해/매칭 유틸
# -----------------------------
# 괄호 안의 콤마는 무시하고, 괄호 "외부" 콤마로만 쪼갬
COMMA_TOPLEVEL_RX = re.compile(r",(?![^()]*\))")


def _to_int_amount_soft(x) -> int | None:
    try:
        if isinstance(x, (int, float)):
            return int(x)
        s = str(x or "")
        m = re.findall(r"\d+", s)
        return int("".join(m)) if m else None
    except Exception:
        return None


def _filter_covs_by_token_keywords(tok: str, covs: List[Dict]) -> List[Dict]:
    """토큰의 키워드로 후보 커버리지를 1차 필터링."""
    t = (tok or "").lower()
    out: List[Dict] = []

    def _s(c):
        return f"{str(c.get('name') or '')}|{str(c.get('association_name') or '')}".lower()

    # 합본(방사선+약물)
    if ("방사선+약물" in t) or ("방사선약물" in t) or ("방사선·약물" in t):
        out = [
            c
            for c in (covs or [])
            if ("방사선약물" in _s(c)) or (("방사선" in _s(c)) and ("약물" in _s(c)))
        ]
        if out:
            return out

    # 방사선 모달리티
    for key in ("중입자", "양성자", "세기조절", "방사선"):
        if key in t:
            out = [c for c in (covs or []) if key in _s(c)]
            if out:
                return out

    # 약물/세부
    if "표적" in t:
        out = [c for c in (covs or []) if "표적" in _s(c)]
        if out:
            return out
    if "약물" in t:
        out = [c for c in (covs or []) if "약물" in _s(c)]
        if out:
            return out

    # 다빈치/로봇
    if ("다빈치" in t) or ("로봇" in t):
        out = [c for c in (covs or []) if ("다빈치" in _s(c)) or ("로봇" in _s(c))]
        if out:
            return out

    # 키워드가 불명확하면 원본 유지(모호)
    return list(covs or [])


def _decide_token_style(tok: str, covs: List[Dict]) -> Tuple[str, bool]:
    """
    토큰 한 조각에 대해 색/볼드 결정.
    우선순위: 비갱신 우선 → (있으면) 갱신 → 모호(검정)
    """
    # 1) 키워드로 1차 필터
    cand = _filter_covs_by_token_keywords(tok, covs)

    # 2) 금액으로 2차 필터(있을 때만 동일 금액 일치)
    t_amt = _to_int_amount_soft(tok)
    if t_amt is not None:
        matched = [c for c in cand if _to_int_amount_soft(c.get("amount")) == t_amt]
        if matched:
            cand = matched

    # 3) 비갱신 우선
    for c in cand:
        s = f"{str(c.get('name') or '')}|{str(c.get('association_name') or '')}"
        if _CA_RE_NOT_RENEWAL.search(s):
            _trace("RENEWAL_DECIDE_TOKEN", f"token='{tok}' -> nonrenewal -> BLACK")
            return (BLACK, False)

    # 4) 갱신 하나라도 있으면 초록+볼드
    if any(_cov_is_renewal(c) for c in cand):
        _trace("RENEWAL_DECIDE_TOKEN", f"token='{tok}' -> renewal -> GREEN/BOLD")
        return (GREEN, True)

    # 5) 모호하면 검정(최종 비갱신 우선 재확인)
    for c in (covs or []):
        s = f"{str(c.get('name') or '')}|{str(c.get('association_name') or '')}"
        if _CA_RE_NOT_RENEWAL.search(s):
            return (BLACK, False)
    _trace("RENEWAL_DECIDE_TOKEN", f"token='{tok}' -> ambiguous -> BLACK")
    return (BLACK, False)


# -----------------------------
# Public API
# -----------------------------
def _apply_richtext_tokens(cell, text: str, covs_for_row: List[Dict]) -> bool:
    """
    콤마(괄호 외부) 기준 토큰 분해 후 부분서식 적용. 성공 시 True.
    리치텍스트 미지원/토큰 1개 이하면 False.
    """
    if not (_RT_SUPPORTED and isinstance(text, str) and "," in text):
        return False

    parts = [p.strip() for p in COMMA_TOPLEVEL_RX.split(text) if (p and p.strip())]
    if len(parts) <= 1:
        return False

    try:
        rt = CellRichText()
        for i, tok in enumerate(parts):
            color, bold = _decide_token_style(tok, covs_for_row)
            rt.append(TextBlock(tok, Font(color=color, b=bold)))
            if i != len(parts) - 1:
                rt.append(TextBlock(", ", Font(color=BLACK, b=False)))
        cell.value = rt
        _trace("TOKEN_RT_APPLY", f"row={cell.row} applied parts={len(parts)}")
        return True
    except Exception as e:
        _trace("TOKEN_RT_APPLY", f"row={cell.row} failed: {e}")
        return False


def _row_has_mixed_renewal(covs: List[Dict]) -> bool:
    """행 커버리지에 갱/비갱이 섞였는지 빠르게 판정."""
    if not covs:
        return False
    has_nonrenewal = any(
        _CA_RE_NOT_RENEWAL.search(
            f"{str(c.get('name') or '')}|{str(c.get('association_name') or '')}"
        )
        for c in covs
    )
    has_renewal = any(_cov_is_renewal(c) for c in covs)
    return has_nonrenewal and has_renewal
