# -*- coding: utf-8 -*-
"""
excel/product.py — v2025-11-06
- 상품명 정리/정규화
- (n/m) 분할 상품 병합
- 상품 단위 갱신 표기/판정 유틸
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional


# ------------------ 상품명 정리 ------------------
_ALLOWED_CHARS_RX = re.compile(r"[^0-9A-Za-z가-힣\s\(\)\[\]\-.,!·&\+\/:_]+")
_MULTI_SPACE_RX   = re.compile(r"\s+")
# 표시용 노이즈(상품명에서 제거)
_NOISE_NAME_TOKENS = re.compile(
    r"(?:^\(무\)\s*|^무배당\s*|^유배당\s*|무해지형|순수보장형|표준형|일반형|일반플랜|표준플랜|플랜형)",
    re.IGNORECASE,
)
# (갱신형)류 노이즈
_NOISE_RENEWAL_TOKENS = re.compile(
    r"\s*\(\s*(?:자동\s*)?갱신\s*형\s*\)\s*|\s*\(\s*갱신\s*형\s*\)\s*|\s*자동\s*갱신\s*형\s*",
    re.IGNORECASE,
)
# (n/m) 꼬리
_PART_RX = re.compile(r"\(\s*(\d+)\s*/\s*(\d+)\s*\)\s*$")


def _nfkc(s: str) -> str:
    try:
        return unicodedata.normalize("NFKC", s)
    except Exception:
        return s


def clean_name(name: str) -> str:
    """상품명에서 불필요 토큰·마커 제거."""
    if not isinstance(name, str):
        return ""
    t = name.strip()
    # 대괄호 부가정보 제거
    t = re.sub(r'\s*\[.+?\]', '', t)
    # (n/m) 꼬리 제거
    t = _PART_RX.sub("", t).strip()
    # 배당/형 등 노이즈 제거
    t = _NOISE_NAME_TOKENS.sub("", t)
    # (갱신형) 표기 제거
    t = _NOISE_RENEWAL_TOKENS.sub("", t)
    # 다중 공백 정리
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _filter_allowed(s: str) -> str:
    s = _ALLOWED_CHARS_RX.sub(" ", s)
    s = _MULTI_SPACE_RX.sub(" ", s).strip()
    return s


def normalize_product_name(raw_name: str, max_len: int = 70) -> str:
    """표시용 상품명 정규화(길이 제한 포함)."""
    original = raw_name or ""
    name = clean_name(original)
    nfkc = _nfkc(name)
    norm = _filter_allowed(nfkc)
    if len(norm) > max_len:
        cut = norm[:max_len + 1]
        k = max(cut.rfind(" "), cut.rfind(")"), cut.rfind("]"), cut.rfind(","))
        if k >= max_len * 0.6:
            norm = cut[:k].strip()
        else:
            norm = cut[:max_len].rstrip()
    return norm


# ------------------ (n/m) 병합 ------------------
def _split_marker(name: str) -> Optional[tuple[int, int]]:
    m = _PART_RX.search(name or "")
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if a >= 1 and b >= 1 and a <= b:
        return (a, b)
    return None


def _base_name_without_marker(name: str) -> str:
    return _PART_RX.sub("", name or "").strip()


def merge_products(products: list[dict]) -> list[dict]:
    """
    같은 상품의 (1/n)~(n/n) 조각을 한 개로 병합.
    키: (회사, (마커 제거)상품명, 가입일, 월보험료)
    """
    if not products:
        return []
    kept = []
    for p in products:
        q = dict(p)
        q["coverages"] = list(p.get("coverages", []) or [])
        kept.append(q)

    groups: Dict[tuple, list] = {}
    for p in kept:
        name = p.get("product_name", "") or ""
        mark = _split_marker(name)
        if not mark:
            continue
        base = _base_name_without_marker(name)
        key = (
            (p.get("company") or "").strip(),
            base,
            (p.get("contract_date") or "").strip(),
            (p.get("monthly_premium") or "").strip(),
        )
        groups.setdefault(key, []).append(p)

    merged_ids = set()
    out: List[dict] = []
    for p in kept:
        if id(p) in merged_ids:
            continue
        name = p.get("product_name", "") or ""
        mark = _split_marker(name)
        if not mark:
            out.append(p)
            continue

        base = _base_name_without_marker(name)
        key = (
            (p.get("company") or "").strip(),
            base,
            (p.get("contract_date") or "").strip(),
            (p.get("monthly_premium") or "").strip(),
        )
        parts = groups.get(key, [])
        denom = None
        have = set()
        for it in parts:
            m = _split_marker(it.get("product_name", "") or "")
            if not m:
                continue
            if denom is None:
                denom = m[1]
            if m[1] != denom:
                denom = None
                break
            have.add(m[0])
        if denom and have == set(range(1, denom + 1)):
            merged = dict(p)
            merged["product_name"] = base
            merged_covs: List[dict] = []
            for it in parts:
                merged_ids.add(id(it))
                merged_covs.extend(it.get("coverages", []) or [])
            merged["coverages"] = merged_covs
            out.append(merged)
        else:
            out.append(p)
    return out


# ------------------ 갱신 표기 ------------------
RENEWAL_KEYWORDS = ("갱신", "갱신형", "자동갱신", "(갱)")
NEG_RENEWAL = re.compile(r"(비\s*갱신형|갱신.{0,6}(보험료|납입|면제|대체))", re.I)


def is_renewal_product(raw_name: str) -> bool:
    """상품명 자체가 갱신형 신호를 강하게 가지면 True."""
    s = raw_name or ""
    if NEG_RENEWAL.search(s):
        return False
    return any(k in s for k in RENEWAL_KEYWORDS)


def display_product_name(raw_name: str, simplified: str, all_covs_renewal: bool) -> str:
    """
    엑셀 표시용 상품명. 전체 담보 갱신이면 '(갱) ' 접두.
    simplified가 비어있으면 normalize_product_name(raw_name) 사용.
    """
    base = (simplified or "").strip()
    if not base:
        base = normalize_product_name(raw_name or "")
    # 기존에 (갱)로 시작하면 중복 제거
    base = re.sub(r"^\(\s*갱\s*\)\s*", "", base).strip()
    return f"(갱) {base}".strip() if all_covs_renewal else base
