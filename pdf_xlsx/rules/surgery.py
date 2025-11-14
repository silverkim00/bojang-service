# rules/surgery.py — surgery domain classifier/aggregator — v2025-11-12d
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from collections import Counter
from typing import Dict, List, Optional

from ..utils import _nz, _nosp, parse_amount, format_amount_short

# ───────────────── 공통 유틸
def _name(c: Dict) -> str:  return _nz(c.get("name", ""))
def _assoc(c: Dict) -> str: return _nz(c.get("association_name", ""))
def _na(c: Dict) -> str:    return _nosp(_name(c) + "|" + _assoc(c))

def _get_amount(item: Dict) -> int:
    v = item.get("_amt")
    if isinstance(v, int) and v >= 0: return v
    try: return int(parse_amount(item.get("amount","0")))
    except Exception: return 0

def _amt_list(items: List[Dict]) -> List[int]:
    out = []
    for it in items or []:
        v = _get_amount(it)
        if v > 0: out.append(v)
    return out

def _max_amt(items: List[Dict]) -> int:
    m = 0
    for it in items or []:
        v = _get_amount(it)
        if v > m: m = v
    return m

def _sum_amt(items: List[Dict]) -> int:
    s = 0
    for it in items or []:
        s += _get_amount(it)
    return s

def _has_any(s: str, keys) -> bool:
    s = _nosp(s)
    return any(k in s for k in keys)

# ───────────────── 라벨 상수
LBL_2MAJOR   = "2대수술비"
LBL_5ORGAN   = "5대기관수술비"
LBL_N_SURG   = "N대(기타)수술비"
LBL_GSURG_D  = "질병 수술비"
LBL_GSURG_I  = "상해 수술비"
LBL_G5       = "질병,상해 종수술비"
LBL_FX_SURG  = "골절,화상 수술비"
LBL_ROBOT    = "다빈치 수술비"  # 전용 버킷; 최종 표시는 24행(암 수술비)에 병기

# ───────────────── 정규식/키워드
RX_N_ALLOWED   = re.compile(r"(?P<n>\d+)\s*대\s*(?:주요)?\s*질병\s*수술(?:비)?", re.I)
RX_N_LEADING   = re.compile(r"(?P<n>\d+)\s*대")

RX_KIND_RANGE  = re.compile(r"(?P<lo>\d+)\s*[\-~–]\s*(?P<hi>\d+)\s*종", re.I)
RX_KIND_SINGLE = re.compile(r"(?P<n>\d+)\s*종", re.I)
RX_G5_HINT     = re.compile(r"(종\s*수술|종수술|질병\s*종수술|상해\s*종수술|신질병\s*종수술|신상해\s*종수술)", re.I)

RX_GSET_GENERIC= re.compile(r"주요\s*심[·\.]?\s*뇌[·\.]?\s*5\s*대\s*혈관\s*수술", re.I)

RX_7ORG        = re.compile(r"7\s*대\s*기관\s*수술", re.I)
RX_TAG_2ORG    = re.compile(r"[\(\[\{]?\s*2\s*대\s*기관\s*[\)\]\}]?")
RX_TAG_5ORG    = re.compile(r"[\(\[\{]?\s*5\s*대\s*기관\s*[\)\]\}]?")

K_BRAIN        = ("뇌혈관질환수술", "뇌혈관수술", "뇌혈관")
K_ISCHEMIC     = ("허혈성심장질환수술", "허혈성심장질환", "허혈성")
K_THROM        = ("혈전용해", "혈전용해치료", "혈전용해치료비", "혈전용해수술", "혈전 용해", "혈전-용해", "혈전·용해")

K_FX           = ("골절",)
K_BRN          = ("화상",)
K_GIPS         = ("깁스", "깁스치료", "석고")

def _is_cancer_robot(na: str) -> bool:
    has_robot = any(k in na for k in ("다빈치", "로봇수술", "로봇"))
    has_cancer = ("암" in na) or any(k in na for k in ("갑상선암", "전립선암"))
    return has_robot and has_cancer

# ───────────────── 종수(1~N종) 추출
def _extract_gkinds(item: Dict) -> None:
    na = _na(item)

    dom = None
    if "질병" in na or "신질병" in na:
        dom = "D"
    elif "상해" in na or "재해" in na or "신상해" in na:
        dom = "I"
    item["_gk_domain"] = dom

    m = RX_KIND_RANGE.search(na)
    if m:
        lo = int(m.group("lo")); hi = int(m.group("hi"))
        if lo > hi: lo, hi = hi, lo
        item["_gk_lo"] = lo
        item["_gk_hi"] = hi

    ns = []
    for sm in RX_KIND_SINGLE.finditer(na):
        try:
            n = int(sm.group("n")); ns.append(n)
        except Exception:
            pass
    if ns:
        item["_gk_ns"] = sorted(set(ns))

# ───────────────── 특정질병수술 가드/전용 라우팅
_CANON_SUFFIX_CHOP = re.compile(r"(?:[ivxⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]|[0-9])+$", re.I)
_SEP_CHARS_STRIP   = re.compile(r"[()\[\]{}·\.\-_/]")
_RX_ANY_N_DAE      = re.compile(r"(\d+)\s*대", re.I)

def _canon_surg_label(x: str) -> str:
    s = _nosp(_nz(x)).lower()
    s = _SEP_CHARS_STRIP.sub("", s)
    s = _CANON_SUFFIX_CHOP.sub("", s)
    return s

def _extract_specific_n(na: str) -> Optional[int]:
    s = _nosp(na)
    if ("특정질병수술" not in s) and ("특정질병수술비" not in s):
        return None
    ns = [int(m.group(1)) for m in _RX_ANY_N_DAE.finditer(s)]
    return min(ns) if ns else None

# ───────────────── 분류기
def classify(item: Dict) -> Optional[str]:
    # 듀얼 특정질병수술 → 드롭
    if _canon_surg_label(_name(item)) == "특정질병수술" and _canon_surg_label(_assoc(item)) == "특정질병수술":
        return "__SURG_DROP__"

    na0 = _na(item)

    # 다빈치(암) 우선
    if _is_cancer_robot(na0):
        return LBL_ROBOT

    # 특정질병수술 + N대 변종 → N대(기타)
    n_specific = _extract_specific_n(na0)
    if n_specific:
        item.setdefault("_n_leading", str(n_specific))
        return LBL_N_SURG

    na = na0

    # 2대 개별
    if _has_any(na, K_BRAIN) or _has_any(na, K_ISCHEMIC) or _has_any(na, K_THROM):
        item["_two_major_specific"] = True
        return LBL_2MAJOR

    # 7대기관
    if RX_7ORG.search(na):
        if RX_TAG_2ORG.search(na):
            item.setdefault("_surg_src", "7ORG-2ORG")
            return LBL_2MAJOR
        if RX_TAG_5ORG.search(na):
            return LBL_5ORGAN
        return "__SURG_GENERIC__"

    # 제너릭 '주요심·뇌·5대혈관수술'
    if RX_GSET_GENERIC.search(na):
        if not (_has_any(na, K_BRAIN) or _has_any(na, K_ISCHEMIC) or _has_any(na, K_THROM)):
            item.setdefault("_surg_src", "GENERIC_2MAJOR")
            return LBL_2MAJOR

    # N대(기타)
    m = RX_N_ALLOWED.search(na)
    if m:
        try:
            n = int(m.group("n"))
        except Exception:
            n = 0
        if n >= 10:
            item.setdefault("_n_leading", str(n))
            return LBL_N_SURG

    # 종수술
    if RX_G5_HINT.search(na):
        _extract_gkinds(item)
        return LBL_G5

    # 골절/화상/깁스(수술측)
    if (("수술" in na) and (_has_any(na, K_FX) or _has_any(na, K_BRN))) or _has_any(na, K_GIPS):
        return LBL_FX_SURG

    # 일반 수술
    if "질병수술" in na or ("수술" in na and "질병" in na):
        return LBL_GSURG_D
    if ("상해수술" in na) or ("수술" in na and ("상해" in na or "재해" in na)):
        return LBL_GSURG_I

    return None

# ───────────────── 집계기
def aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None:
    # 질병/상해 일반 수술
    if LBL_GSURG_D in bucket:
        v = _max_amt(bucket[LBL_GSURG_D])
        if v:
            out[LBL_GSURG_D] = f"{LBL_GSURG_D} {format_amount_short(v)}"
    if LBL_GSURG_I in bucket:
        v = _max_amt(bucket[LBL_GSURG_I])
        if v:
            out[LBL_GSURG_I] = f"{LBL_GSURG_I} {format_amount_short(v)}"

    # 종수술(가변 키)
    if LBL_G5 in bucket:
        items = bucket[LBL_G5]
        d_items = [c for c in items if c.get("_gk_domain") == "D"]
        i_items = [c for c in items if c.get("_gk_domain") == "I"]

        def _kind_str(sub: List[Dict]) -> Optional[str]:
            lo_vals = [c.get("_gk_lo") for c in sub if isinstance(c.get("_gk_lo"), int)]
            hi_vals = [c.get("_gk_hi") for c in sub if isinstance(c.get("_gk_hi"), int)]
            has_range = bool(lo_vals or hi_vals)

            ns_all = []
            for c in sub:
                ns_all.extend(c.get("_gk_ns", []) if isinstance(c.get("_gk_ns", []), list) else [])
            ns_all = sorted(set([n for n in ns_all if isinstance(n, int)]))
            has_single = bool(ns_all)

            if has_single:
                lo_s, hi_s = min(ns_all), max(ns_all)
                if has_range:
                    lo_r = min(lo_vals) if lo_vals else lo_s
                    hi_r = max(hi_vals) if hi_vals else hi_s
                    if (lo_s > lo_r) or (hi_s < hi_r):
                        return f"{lo_s}-{hi_s}종" if lo_s != hi_s else f"{lo_s}종"
                return f"{lo_s}-{hi_s}종" if lo_s != hi_s else f"{lo_s}종"

            if has_range:
                lo = min(lo_vals) if lo_vals else None
                hi = max(hi_vals) if hi_vals else None
                if lo is not None and hi is not None:
                    return f"{lo}-{hi}종" if lo != hi else f"{lo}종"
            return None

        def _amt_str(sub: List[Dict]) -> Optional[str]:
            vals = sorted(set(_amt_list(sub)))
            if not vals: return None
            return format_amount_short(vals[0]) if len(vals) == 1 else f"{format_amount_short(vals[0])}~{format_amount_short(vals[-1])}"

        wrote_any = False

        if d_items:
            ks = _kind_str(d_items)
            as_ = _amt_str(d_items)
            if as_:
                lbl_d = (f"질병{ks} 수술비" if ks else "질병종수술")
                out[lbl_d] = as_
                wrote_any = True

        if i_items:
            ks = _kind_str(i_items)
            as_ = _amt_str(i_items)
            if as_:
                lbl_i = (f"상해{ks} 수술비" if ks else "상해종수술")
                out[lbl_i] = as_
                wrote_any = True

        if not wrote_any:
            v_all = _max_amt(items)
            if v_all:
                out[LBL_G5] = format_amount_short(v_all)

    # N대(기타)
    if LBL_N_SURG in bucket:
        pairs = [
            (
                c,
                c.get("_n_leading") or
                (RX_N_LEADING.search(_na(c)).group("n") if RX_N_LEADING.search(_na(c)) else None)
            )
            for c in bucket[LBL_N_SURG]
        ]
        ns = [n for _, n in pairs if n]
        if ns:
            rep = Counter(ns).most_common(1)[0][0]
            items_rep = [c for c, n in pairs if n == rep]
            vals = sorted(set(_amt_list(items_rep)))
            if vals:
                out[LBL_N_SURG] = (
                    f"{rep}대 {format_amount_short(vals[0])}"
                    if len(vals) == 1 else
                    f"{rep}대 {format_amount_short(vals[0])}~{format_amount_short(vals[-1])}"
                )

    # 5대기관
    if LBL_5ORGAN in bucket:
        v = _max_amt(bucket[LBL_5ORGAN])
        if v:
            out[LBL_5ORGAN] = f"5대기관 {format_amount_short(v)}"

    # 골절/화상/깁스(수술)
    if LBL_FX_SURG in bucket:
        items_fx = bucket[LBL_FX_SURG]
        def has(c, ks): return any(k in _na(c) for k in ks)
        fx = _max_amt([c for c in items_fx if has(c, K_FX) and "수술" in _na(c)])
        br = _max_amt([c for c in items_fx if has(c, K_BRN) and "수술" in _na(c)])
        gp = _max_amt([c for c in items_fx if has(c, K_GIPS)])
        parts = []
        if fx: parts.append(f"골절 {format_amount_short(fx)}")
        if br: parts.append(f"화상 {format_amount_short(br)}")
        if gp: parts.append(f"깁스 {format_amount_short(gp)}")
        if parts:
            out[LBL_FX_SURG] = ", ".join(parts)

    # 2대 수술
    if LBL_2MAJOR in bucket:
        items2 = bucket[LBL_2MAJOR]
        def has(c, ks): return any(k in _na(c) for k in ks)

        specific_items = [c for c in items2 if c.get("_two_major_specific")]
        v_brain = _max_amt([c for c in specific_items if has(c, K_BRAIN)])
        v_isch  = _max_amt([c for c in specific_items if has(c, K_ISCHEMIC)])
        v_throm = _max_amt([c for c in specific_items if has(c, K_THROM)])

        src_2org    = [c for c in items2 if _nz(c.get("_surg_src")) == "7ORG-2ORG"]
        src_generic = [c for c in items2 if _nz(c.get("_surg_src")) == "GENERIC_2MAJOR"]
        v_sum2      = _sum_amt(src_2org) + _sum_amt(src_generic)

        parts = []
        if v_brain: parts.append(("뇌혈관", v_brain))
        if v_isch:  parts.append(("허혈성", v_isch))
        if v_throm: parts.append(("혈전용해", v_throm))
        order = {"뇌혈관":0, "허혈성":1, "혈전용해":2}
        parts.sort(key=lambda kv: order.get(kv[0], 99))
        txts = [f"{k} {format_amount_short(v)}" for k, v in parts]
        if v_sum2: txts.append(f"2대 {format_amount_short(v_sum2)}")
        if txts:
            out[LBL_2MAJOR] = ", ".join(txts)

    # 다빈치 → 24행 병기
    if LBL_ROBOT in bucket:
        v_robot = _max_amt(bucket[LBL_ROBOT])
        if v_robot:
            add_txt = f"다빈치 {format_amount_short(v_robot)}"
            base = (_nz(out.get("암 수술비"))).strip()
            if add_txt not in [t.strip() for t in base.split(",") if t.strip()]:
                out["암 수술비"] = (f"{base}, {add_txt}".strip(", ").strip()) if base else add_txt


__all__ = ["classify", "aggregate"]
