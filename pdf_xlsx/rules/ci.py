# -*- coding: utf-8 -*-
# rules/ci.py — CI 상품 메타 + 태깅 엔진
# v2025-11-17b (주계약 분리 집계 + 암/사망/2대 동시 처리)

from __future__ import annotations
from typing import Dict, List, Tuple

from ..utils import _nz, _nosp, parse_amount, format_amount_short
from ..logger_setup import get_logger

_log = get_logger("app")

def _trace(tag: str, msg: str) -> None:
    try:
        _log.info(f"TRACE[CI.{tag}] {msg}")
    except Exception:
        pass


# CI 상품 판별 -------------------------------------------------------------

def _detect_ci_product(product: dict) -> bool:
    """
    상품명이 CI/씨아이 등을 포함하면 CI 상품으로 본다.
    (너무 빡세게 안 하고, 느슨한 포함 기준만 사용)
    """
    name_raw = _nz(product.get("product_name") or product.get("상품명") or "")
    s = _nosp(name_raw)
    s_lower = s.lower()
    if not s and not s_lower:
        return False

    if "ci" in s_lower:
        return True
    if "씨아이" in s:
        return True
    if "criticalillness" in s_lower:
        return True
    return False


# CI 메타 태깅 -------------------------------------------------------------

def mark_ci_metadata(product: dict, coverages: List[dict]) -> None:
    """
    - 상품이 CI 인지 판단해서 product['_ci_product'] 플래그를 세운다.
    - CI 상품일 경우, 모든 담보에 '_ci_product'=True.
    - 그 중 '주계약' + (암/사망/2대 진단) 라인은 '_ci_core'=True,
      '_ci_target_label', '_ci_caption' 으로 목적 라벨/문구까지 태깅.
    """
    if not isinstance(product, dict) or not isinstance(coverages, list):
        return

    is_ci = _detect_ci_product(product)
    product["_ci_product"] = bool(is_ci)

    if not is_ci:
        # 그냥 깔끔하게 false 표시만 하고 끝
        for c in coverages:
            if isinstance(c, dict):
                c["_ci_product"] = False
        _trace("META", "non-CI product; skip core tagging")
        return

    _trace("META", "CI product detected; tagging coverages")

    for c in coverages:
        if not isinstance(c, dict):
            continue

        c["_ci_product"] = True

        name_ns = _nosp(_nz(c.get("name", "")))
        assoc_ns = _nosp(_nz(c.get("association_name", "")))

        # 기본값
        c.setdefault("_ci_core", False)
        c.pop("_ci_target_label", None)
        c.pop("_ci_caption", None)

        # 주계약만 CI 코어 후보
        if name_ns != "주계약":
            continue

        # 암 진단
        if ("암" in assoc_ns) and (("진단" in assoc_ns) or ("진단비" in assoc_ns)):
            c["_ci_core"] = True
            c["_ci_target_label"] = "일반암/고액암 진단비"
            c["_ci_caption"] = "암진단"
            continue

        # 질병 사망
        if "질병사망" in assoc_ns:
            c["_ci_core"] = True
            c["_ci_target_label"] = "질병사망"
            c["_ci_caption"] = "질병사망"
            continue

        # 상해/재해 사망
        if ("상해사망" in assoc_ns) or ("재해사망" in assoc_ns):
            c["_ci_core"] = True
            c["_ci_target_label"] = "상해사망"
            c["_ci_caption"] = "상해사망"
            continue

        # 2대 질환
        if ("뇌졸중" in assoc_ns) and (("진단" in assoc_ns) or ("진단비" in assoc_ns)):
            c["_ci_core"] = True
            c["_ci_target_label"] = "뇌졸중"
            c["_ci_caption"] = "뇌졸중"
            continue

        if ("뇌출혈" in assoc_ns) and (("진단" in assoc_ns) or ("진단비" in assoc_ns)):
            c["_ci_core"] = True
            c["_ci_target_label"] = "뇌출혈"
            c["_ci_caption"] = "뇌출혈"
            continue

        if ("급성심근경색" in assoc_ns) and (("진단" in assoc_ns) or ("진단비" in assoc_ns)):
            c["_ci_core"] = True
            c["_ci_target_label"] = "급성심근경색"
            c["_ci_caption"] = "급성심근경색"
            continue

    # 끝나고 요약 로그
    core_cnt = sum(1 for c in coverages if isinstance(c, dict) and c.get("_ci_core"))
    _trace("META_SUM", f"ci_core={core_cnt}")


# CI 태그 적용 -------------------------------------------------------------

# out 키 → 표시용 캡션 매핑
_TARGETS: Dict[str, str] = {
    "일반암/고액암 진단비": "암진단",
    "질병사망": "질병사망",
    "상해사망": "상해사망",
    "뇌졸중": "뇌졸중",
    "뇌출혈": "뇌출혈",
    "급성심근경색": "급성심근경색",
}


def _max_amt(items: List[Dict]) -> int:
    m = 0
    for c in items or []:
        try:
            v = int(c.get("_amt") or 0)
        except Exception:
            try:
                v = int(parse_amount(c.get("amount", "0")))
            except Exception:
                v = 0
        if v > m:
            m = v
    return m


def apply_ci_tag(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None:
    """
    - bucket / out 이 모두 만들어진 뒤 마지막에 호출.
    - 같은 라벨에
        CI(주계약) 라인 + 일반(특약) 라인이 같이 있으면
        -> "CI암진단 9백60만, 암진단 1천만" 처럼 한 셀에 함께 병기.
      CI 라인만 있으면
        -> "CI질병사망 1천2백만" 처럼 단독 표기.
      CI 라인이 없으면 out 은 손대지 않는다.
    """

    # CI 상품이 아니면 바로 종료
    any_ci = False
    for items in bucket.values():
        for c in items:
            if c.get("_ci_product"):
                any_ci = True
                break
        if any_ci:
            break
    if not any_ci:
        _trace("APPLY", "no CI product in bucket; skip")
        return

    _trace("APPLY", f"start; out_keys={list(out.keys())}")

    for label, caption in _TARGETS.items():
        items = bucket.get(label) or []
        if not items:
            continue

        ci_items: List[Dict] = []
        normal_items: List[Dict] = []

        for c in items:
            # 유효 금액만 집계
            try:
                amt = int(c.get("_amt") or 0)
            except Exception:
                try:
                    amt = int(parse_amount(c.get("amount", "0")))
                except Exception:
                    amt = 0
            if amt <= 0:
                continue

            is_ci_product = bool(c.get("_ci_product"))
            is_core = bool(c.get("_ci_core"))
            tgt_lbl = c.get("_ci_target_label")
            name_ns = _nosp(_nz(c.get("name", "")))

            # CI 코어 결정:
            #  - CI 상품이고
            #  - (코어 플래그 ON 이거나, 타겟라벨이 같거나, name 이 '주계약')
            if is_ci_product and (is_core or tgt_lbl == label or name_ns == "주계약"):
                ci_items.append(c)
            else:
                normal_items.append(c)

        if not ci_items:
            # 이 라벨에 CI 주계약이 없으면 손대지 않음
            continue

        ci_amt = _max_amt(ci_items)
        normal_amt = _max_amt(normal_items)

        parts = []
        if ci_amt:
            parts.append(f"CI{caption} {format_amount_short(ci_amt)}")
        if normal_amt:
            parts.append(f"{caption} {format_amount_short(normal_amt)}")

        if not parts:
            continue

        new_txt = ", ".join(parts)
        _trace("APPLY_LABEL", f"label={label}, text={new_txt}")
        out[label] = new_txt
