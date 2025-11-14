# rules/driver.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Dict, List, Optional

from ..utils import _nz, _nosp, parse_amount, format_amount_short


# ─────────────────────────────────────────────────────────────
# 라벨 키 (config.HARDCODED_ROW_MAP 기준)
# ─────────────────────────────────────────────────────────────
LBL_AID   = "교통사고 처리지원금(형사합의금)"
LBL_LAW   = "변호사 선임비용(방어비용)"
LBL_INJ   = "자동차 부상 치료비"
LBL_FINE  = "벌금 대인/대물"
# ⚠️ 아래 3개는 fx_burn.py에서만 처리 (driver에서는 취급하지 않음)
# LBL_FFINE = "화재벌금"
# LBL_LIAB_D = "일상생활배상책임"
# LBL_LIAB_F = "가족생활배상책임"

# ─────────────────────────────────────────────────────────────
# 패턴 (운전자/벌금 계열만 유지)
# ─────────────────────────────────────────────────────────────
RX = {
    "aid":   re.compile(r"(교통사고처리|형사합의)", re.I),
    "law":   re.compile(r"(변호사\s*선임|방어비용)", re.I),
    "inj":   re.compile(r"(자동차사고부상|자동차부상)", re.I),
    "fine":  re.compile(r"(벌금)", re.I),
    # driver에서는 화재벌금/일배/가배책을 분류하지 않음(= fx_burn 전용)
    "ff":    re.compile(r"(화재\s*벌금)", re.I),
    "liab":  re.compile(r"(일상생활배상책임|일배|가배책|가족생활배상책임)", re.I),

    # 🚫 운전자와 무관: 민사/소송 법률비용류는 절대 분류하지 않음
    "black": re.compile(r"(민사\s*소송\s*법률\s*비용|소송\s*법률\s*비용)", re.I),
}

# ─────────────────────────────────────────────────────────────
def _t(item: Dict) -> str:
    return _nosp(_nz(item.get("name","")) + "|" + _nz(item.get("association_name","")))

def _max(items: List[Dict]) -> int:
    vals: List[int] = []
    for it in items or []:
        try:
            v = int(parse_amount(it.get("amount","0")))
        except Exception:
            v = 0
        if v > 0:
            vals.append(v)
    return max(vals) if vals else 0

# ─────────────────────────────────────────────────────────────
# 분류: 운전자/벌금(대인·대물)만 남기고, 화재벌금/배상책임은 fx_burn에게 위임
# ─────────────────────────────────────────────────────────────
def classify(item: Dict) -> Optional[str]:
    t = _t(item)

    # 블랙리스트: 운전자 분류 금지
    if RX["black"].search(t):
        return None

    # driver가 담당하는 라인만 반환
    if RX["aid"].search(t):
        return LBL_AID
    if RX["law"].search(t):
        return LBL_LAW
    if RX["inj"].search(t):
        return LBL_INJ

    # 벌금(대인/대물) — 단, '화재벌금'은 fx_burn 전용이므로 제외
    if RX["fine"].search(t) and not RX["ff"].search(t):
        return LBL_FINE

    # 아래 항목은 fx_burn 전용: driver에서는 절대 분류하지 않음
    # if RX["ff"].search(t):  # 화재벌금
    #     return None
    # if RX["liab"].search(t):  # 일상/가족 생활배상책임
    #     return None

    return None

# ─────────────────────────────────────────────────────────────
# 집계: 운전자/벌금(대인·대물)만 집계. 화재벌금/배상책임은 건드리지 않음.
# ─────────────────────────────────────────────────────────────
def aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str], scope=None) -> None:
    # 변호사: 금액 최대치로 병기 (짧게 '변호사')
    if LBL_LAW in bucket and LBL_LAW not in out:
        v = _max(bucket[LBL_LAW])
        if v:
            out[LBL_LAW] = f"변호사 {format_amount_short(v)}"

    # 벌금: 대인/대물 각각 최대 추출
    if LBL_FINE in bucket and LBL_FINE not in out:
        items = bucket[LBL_FINE]
        text = lambda it: _t(it)
        din  = _max([it for it in items if "대인" in text(it)])
        dmul = _max([it for it in items if "대물" in text(it)])
        parts: List[str] = []
        if din:
            parts.append(f"대인 {format_amount_short(din)}")
        if dmul:
            parts.append(f"대물 {format_amount_short(dmul)}")
        if parts:
            out[LBL_FINE] = ", ".join(parts)
        else:
            v = _max(items)
            if v:
                out[LBL_FINE] = f"벌금 {format_amount_short(v)}"

    # 자동차 부상 치료비
    if LBL_INJ in bucket and LBL_INJ not in out:
        v = _max(bucket[LBL_INJ])
        if v:
            out[LBL_INJ] = f"자부치 {format_amount_short(v)}"

    # 교통사고 처리지원금(형사합의금)
    if LBL_AID in bucket and LBL_AID not in out:
        v = _max(bucket[LBL_AID])
        if v:
            out[LBL_AID] = f"교사처 {format_amount_short(v)}"

    # 🔒 driver는 아래 키들을 절대 건드리지 않는다(= fx_burn 전용)
    # - "화재벌금"
    # - "일상생활배상책임"
    # - "가족생활배상책임"
