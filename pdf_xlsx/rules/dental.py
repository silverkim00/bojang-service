# -*- coding: utf-8 -*-
"""
rules/dental.py
치과 담보(보존/보철) 라우팅·집계

핵심:
 - 발치/발거는 집계 제외
 - 협회명/담보명 직표기(보존/보철) 최우선
 - 시술 키워드(레진/인레이/임플란트/크라운/브릿지/틀니 등) 보조
 - 금액 파싱: '10만', '1억 3천', '1,200,000' 등 허용
 - coverage_processor 훅: classify(item) → "__DENTAL__" | None
                          aggregate(bucket, out) → out["보존 / 보철"] 세팅
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple, Iterable, Union

# ========= 유틸 =========

_NUM = re.compile(r"[\d,]+")
_KOR_UNITS = (("억", 100_000_000), ("만", 10_000), ("천", 1_000))

def _nz(x: Optional[str]) -> str:
    return x or ""

def _nosp(x: str) -> str:
    return re.sub(r"\s+", "", x or "")

def parse_amount(val: Union[str, int, float, None]) -> int:
    """원 단위 정수 반환. 한국식 단위 허용."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)

    s = str(val).strip()
    if not s:
        return 0

    total = 0
    rest = s
    matched = False
    for u, mul in _KOR_UNITS:
        left, *tail = rest.split(u, 1)
        if len(tail) == 1 and left.strip():
            m = _NUM.search(left.replace(",", ""))
            if m:
                total += int(m.group()) * mul
                matched = True
                rest = tail[0]
    if matched:
        m = _NUM.search(rest.replace(",", ""))
        if m:
            total += int(m.group())
        return total

    m = _NUM.search(s)
    return int(m.group().replace(",", "")) if m else 0

# ========= 규칙 =========

EXCLUDE_KEYWORDS = ("발치", "발거")

RX_PROSTHO = re.compile(
    r"(임플란트|크라운|브릿지|틀니|지대주|PFM|지르코니아|보철치료|상실치아보철)",
    re.I,
)
RX_CONSERVE = re.compile(
    r"(레진|GI|글라스아이오노머|아말감|인레이|온레이|충전|근관|신경치료|치수치료|수복|보존치료)",
    re.I,
)

def _is_excluded(name: str, assoc: str) -> bool:
    s = (_nz(name) + "|" + _nz(assoc)).lower().replace(" ", "")
    return any(k in s for k in EXCLUDE_KEYWORDS)

def _classify_bucket(name: str, assoc: str) -> Optional[str]:
    """
    반환: "보철" | "보존" | None
    우선순위: 협회/명칭 직표기 > 시술 키워드(보철 우선)
    """
    n = _nosp(_nz(name)).lower()
    a = _nosp(_nz(assoc)).lower()

    if ("보철" in n) or ("보철" in a) or RX_PROSTHO.search(n) or RX_PROSTHO.search(a):
        return "보철"
    if ("보존" in n) or ("보존" in a) or RX_CONSERVE.search(n) or RX_CONSERVE.search(a):
        return "보존"
    return None

# ========= 퍼사드(단건 라우팅) =========

def route_and_aggregate(name: str, assoc: str, amount: Union[str, int, float]) -> Optional[Tuple[str, str, int]]:
    """
    단건 라우팅 결과:
      ("보존|보철", subtype, amount_int)
    제외 대상은 None.
    """
    if _is_excluded(name, assoc):
        return None
    bucket = _classify_bucket(name, assoc)
    if not bucket:
        return None
    amt = parse_amount(amount)
    if amt <= 0:
        return None

    # subtype: 잡힌 대표 토큰(간단 표기)
    n, a = _nz(name), _nz(assoc)
    sub = "보철치료" if bucket == "보철" else "보존치료"
    if bucket == "보철":
        m = RX_PROSTHO.search(n) or RX_PROSTHO.search(a)
        if m: sub = m.group(0)
    else:
        m = RX_CONSERVE.search(n) or RX_CONSERVE.search(a)
        if m: sub = m.group(0)
    return bucket, sub, amt

# ========= 집계기(단독 사용·테스트 용) =========

class DentalAggregator:
    """보존/보철 각각 최대값 집계."""
    def __init__(self) -> None:
        self.max_amt: Dict[str, int] = {"보존": 0, "보철": 0}

    def add_item(self, name: str, assoc: str, amount: Union[str, int, float]) -> None:
        r = route_and_aggregate(name, assoc, amount)
        if not r:
            return
        bucket, _sub, amt = r
        if amt > self.max_amt.get(bucket, 0):
            self.max_amt[bucket] = amt

    def merge(self, other: "DentalAggregator") -> None:
        for k in ("보존", "보철"):
            self.max_amt[k] = max(self.max_amt.get(k, 0), other.max_amt.get(k, 0))

    def result_dict(self) -> Dict[str, int]:
        return dict(self.max_amt)

    @staticmethod
    def _fmt(amt: int) -> str:
        if amt % 10_000 == 0 and amt < 100_000_000:
            return f"{amt // 10_000}만"
        return f"{amt:,}원"

    def result_text(self) -> str:
        parts = []
        if self.max_amt["보존"] > 0:
            parts.append(f"보존 {self._fmt(self.max_amt['보존'])}")
        if self.max_amt["보철"] > 0:
            parts.append(f"보철 {self._fmt(self.max_amt['보철'])}")
        return ", ".join(parts) if parts else ""

def aggregate_items(items: Iterable[Union[dict, tuple]]) -> Dict[str, int]:
    agg = DentalAggregator()
    for it in items:
        if isinstance(it, dict):
            agg.add_item(it.get("name"), it.get("association_name") or it.get("assoc"), it.get("amount"))
        else:
            name, assoc, amount = it
            agg.add_item(name, assoc, amount)
    return agg.result_dict()

# ========= coverage_processor 훅 =========

def classify(item: Dict) -> Optional[str]:
    """
    담보 단건을 치과 도메인으로 태울지 판정.
    - 발치/발거 포함 → None
    - 보존/보철 판정 가능 → "__DENTAL__"
    """
    name = _nz(item.get("name"))
    assoc = _nz(item.get("association_name"))
    if _is_excluded(name, assoc):
        return None
    return "__DENTAL__" if _classify_bucket(name, assoc) else None

def aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None:
    """
    bucket["__DENTAL__"] → 보존/보철 최대값 집계
    결과 키: "보존 / 보철"
    """
    items = bucket.get("__DENTAL__") or []
    if not items:
        return

    max_conserve = 0
    max_prostho = 0

    for c in items:
        name = _nz(c.get("name"))
        assoc = _nz(c.get("association_name"))
        if _is_excluded(name, assoc):
            continue
        amt = parse_amount(c.get("amount"))
        if amt <= 0:
            continue
        b = _classify_bucket(name, assoc)
        if b == "보철":
            if amt > max_prostho:
                max_prostho = amt
        elif b == "보존":
            if amt > max_conserve:
                max_conserve = amt

    parts = []
    if max_conserve:
        parts.append(f"보존 {max_conserve//10_000}만" if max_conserve % 10_000 == 0 and max_conserve < 100_000_000
                     else f"보존 {max_conserve:,}원")
    if max_prostho:
        parts.append(f"보철 {max_prostho//10_000}만" if max_prostho % 10_000 == 0 and max_prostho < 100_000_000
                     else f"보철 {max_prostho:,}원")

    out["보존 / 보철"] = ", ".join(parts) if parts else ""

__all__ = [
    "classify",
    "aggregate",
    "route_and_aggregate",
    "DentalAggregator",
    "aggregate_items",
    "parse_amount",
]
