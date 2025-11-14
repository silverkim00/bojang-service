# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, List, Optional
import re

# 프로젝트 유틸 (런타임에 rules 패키지 바깥 utils 모듈이 존재)
from ..utils import _nz, _nosp, strip_exclusions, parse_amount, format_amount_short

# 룸등급(1/2/3인실, 상급병실, 특실) → 제외
RX_ROOMGRADE = re.compile(r"(?:[1-3]\s*인\s*실|1인실|2인실|3인실|상급\s*병실|특실)", re.I)

# ICU(중환자실) 키워드
RX_ICU = re.compile(r"(중환|중환자|중환자실|ICU)", re.I)
RX_CANCER_ICU = re.compile(r"(암)", re.I)

def _name_assoc(c: Dict) -> str:
    return _nz(c.get("name", "")) + _nz(c.get("association_name", ""))

def _max_amt(items: List[Dict]) -> int:
    vals: List[int] = []
    for i in items or []:
        try:
            v = int(parse_amount(i.get("amount", "0")) or 0)
        except Exception:
            v = 0
        if v > 0:
            vals.append(v)
    return max(vals) if vals else 0

def route_day_coverage(item: Dict, bucket: Dict[str, List[Dict]], excluded_post: List[Dict]) -> bool:
    """
    35/36행 라우팅 전담.
      - 룸등급 키워드 감지 시 제외(EXC/ROOM_GRADE)
      - ICU 토큰 + '입원일당' → '질병,상해 중환자 입원일당'(36행)
      - 그 외 → '질병,상해 입원일당'(35행)
    return: 처리 여부(True=라우팅/제외됨)
    """
    name = _nz(item.get("name", ""))
    assoc = _nz(item.get("association_name", ""))

    name_m = strip_exclusions(name)
    assoc_m = strip_exclusions(assoc)
    tns = _nosp(name_m + assoc_m)

    # 룸등급 제외
    if RX_ROOMGRADE.search(tns):
        item["_reason"] = "EXC/ROOM_GRADE"
        excluded_post.append(item)
        return True

    # ICU vs 일반
    if RX_ICU.search(tns) and ("입원일당" in tns):
        bucket["질병,상해 중환자 입원일당"].append(item)
        return True

    bucket["질병,상해 입원일당"].append(item)
    return True

def aggregate_icu(bucket: Dict[str, List[Dict]], out: Dict[str, str], token_helper) -> None:
    """
    36행 출력.
      - token_helper: rules.heart.analyze_tokens (two_major/brain/heart)
      - 2대/뇌/심/암/질병/상해 감지된 항목 전부 병기(우선순위 정렬)
      - 세분이 하나라도 있으면 제네릭 '중환자실 {금액}'은 출력 억제
      - 세분 전무 시 제네릭 최대만 출력
    """
    key = "질병,상해 중환자 입원일당"
    if key not in bucket:
        return
    items = bucket[key]

    def t(c: Dict) -> str: return _nosp(_name_assoc(c))
    def amt(c: Dict) -> int:
        try: return int(parse_amount(c.get("amount","0")) or 0)
        except Exception: return 0

    mx = {
        "2대중환자": 0,
        "뇌중환자": 0,
        "심중환자": 0,
        "암중환자": 0,
        "질병중환자": 0,
        "상해중환자": 0,
        "중환자실": 0,
    }

    for c in items:
        s = t(c); v = amt(c)
        if v <= 0:
            continue
        if not RX_ICU.search(s):  # ICU 토큰 없으면 안전상 스킵
            continue

        # 암 ICU
        if RX_CANCER_ICU.search(s):
            mx["암중환자"] = max(mx["암중환자"], v)

        # 뇌/심/2대 토큰 판정은 heart 헬퍼에 위임
        tokens = token_helper(s) if token_helper else {"two_major": False, "brain": False, "heart": False}
        if tokens.get("two_major"):
            mx["2대중환자"] = max(mx["2대중환자"], v)
        else:
            if tokens.get("brain"):
                mx["뇌중환자"] = max(mx["뇌중환자"], v)
            if tokens.get("heart"):
                mx["심중환자"] = max(mx["심중환자"], v)

        # 질병/상해 일반 토큰
        if "질병" in s:
            mx["질병중환자"] = max(mx["질병중환자"], v)
        if "상해" in s:
            mx["상해중환자"] = max(mx["상해중환자"], v)

        # 제네릭 최대
        mx["중환자실"] = max(mx["중환자실"], v)

    parts: List[str] = []
    order = ["2대중환자","뇌중환자","심중환자","암중환자","질병중환자","상해중환자"]
    for k in order:
        if mx[k]:
            parts.append(f"{k} {format_amount_short(mx[k])}")

    if parts:
        out[key] = ", ".join(parts)
    elif mx["중환자실"]:
        out[key] = f"중환자실 {format_amount_short(mx['중환자실'])}"

def aggregate_inpatient(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None:
    """
    35행 출력. '상해 X, 질병 Y' 병기.
    """
    key = "질병,상해 입원일당"
    if key not in bucket:
        return
    items = bucket[key]

    inj_vals: List[int] = []
    dis_vals: List[int] = []
    for c in items:
        s = _name_assoc(c)
        try:
            v = int(parse_amount(c.get("amount","0")) or 0)
        except Exception:
            v = 0
        if v <= 0:
            continue
        if "상해" in s:
            inj_vals.append(v)
        if "질병" in s:
            dis_vals.append(v)

    parts = []
    if inj_vals:
        parts.append(f"상해 {format_amount_short(max(inj_vals))}")
    if dis_vals:
        parts.append(f"질병 {format_amount_short(max(dis_vals))}")
    if parts:
        out[key] = ", ".join(parts)
