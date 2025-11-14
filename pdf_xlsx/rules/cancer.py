# rules/cancer.py — policy-driven aggregator (RT/Drug/Combo + CAR-T) — v2025-11-12d
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple

# 정책·토큰·버킷 유틸
try:
    from rules.ca import (
        POLICY as CA_POLICY,
        get_policy,
        is_rt_drug_combined, rt_bucket, drug_bucket,
        drop_pseudo_small, mt_group, extract_years,
        assoc_is_general_diag, assoc_is_high_diag,
        is_integ_cancer_by_name, is_integ_meta_by_name, integ_main_match,
        PSEUDO_SET_TOKENS, PSEUDO_DIAG_HINTS,
    )
except Exception:  # 안전 폴백(필요 최소만)
    CA_POLICY = {"combo_mode": "both", "combo_or_match": True, "drop_pseudo_small_under": 2_000_000}
    def get_policy(k, d=None): return CA_POLICY.get(k, d)
    def is_rt_drug_combined(n, a): return ("방사선" in f"{n}{a}") and ("약물" in f"{n}{a}")
    def rt_bucket(c): return None
    def drug_bucket(c): return None
    def drop_pseudo_small(c, limit=None): return False
    def mt_group(c): return "D"
    def extract_years(c): return None
    def assoc_is_general_diag(a): return bool(re.search(r"^암\s*진단(\(유병자\))?$", a))
    def assoc_is_high_diag(a): return bool(re.search(r"^고액암\s*진단(\(유병자\))?$", a))
    def is_integ_cancer_by_name(c): return False
    def is_integ_meta_by_name(c): return False
    def integ_main_match(c, *, meta): return False
    PSEUDO_SET_TOKENS = ("갑상선암","기타피부암","경계성종양","제자리암")
    PSEUDO_DIAG_HINTS = ("진단금","확정","병리","조직","확진")

# utils import (패키지/스크립트 둘 다 지원)
try:
    from ..utils import parse_amount, format_amount_short
except Exception:
    from utils import parse_amount, format_amount_short
    
# logger import (패키지/스크립트 모두 안전)
try:
    from ..logger_setup import get_logger
except ImportError:
    try:
        from logger_setup import get_logger
    except ImportError:
        import logging
        get_logger = lambda name: logging.getLogger(name)

def _trace(tag: str, msg: str) -> None:
    try:
        get_logger("app").info(f"TRACE[{tag}] {msg}")
    except Exception:
        pass

# ── 소형 유틸
def _nz(s: object) -> str:
    return s if isinstance(s, str) else ""

def _nosp(s: object) -> str:
    return re.sub(r"\s+", "", _nz(s))

def _name_assoc(c: Dict) -> str:
    return _nz(c.get("name", "")) + "|" + _nz(c.get("association_name", ""))

def _get_amount(item: Dict) -> int:
    v = item.get("_amt")
    if isinstance(v, int) and v >= 0:
        return v
    try:
        return int(parse_amount(item.get("amount", "0")))
    except Exception:
        return 0

def _amt_list(items: List[Dict]) -> List[int]:
    out: List[int] = []
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

def _has_any(s: str, keys) -> bool:
    t = _nosp(s).lower()
    return any(_nosp(k).lower() in t for k in keys)

# 지급방식 로컬 추론(coverage_processor 태깅 누락 대비)
def _infer_pay_mode_local(c: Dict) -> Optional[str]:
    assoc_raw = _nz(c.get("association_name", ""))
    typ_raw   = _nz(c.get("type", ""))
    name_raw  = _nz(c.get("name", ""))
    s_all     = f"{assoc_raw}|{typ_raw}|{name_raw}"
    if "정액" in s_all:
        return "정액"
    assoc = _nosp(assoc_raw).lower()
    if assoc == "" or assoc == "null":
        return "비례"
    return None

# ── 라벨
LABEL_GENERAL = "일반암/고액암 진단비"
LABEL_PSEUDO  = "유사암"
LABEL_META    = "전이암"
LABEL_RT      = "항암방사선"
LABEL_DRUG    = "약물 치료"
LABEL_MT      = "암주요치료비"
LABEL_CSURG   = "암 수술비"
LABEL_DAY     = "암 입,통원일당"

LABEL_ALIASES_TO_TEMPLATE = {
    "유사암": "유사암-갑,기,경,제",
}

def _remap_out_labels_for_template(out: Dict[str, str]) -> Dict[str, str]:
    if not out:
        return out
    m: Dict[str, str] = {}
    for k, v in out.items():
        m[LABEL_ALIASES_TO_TEMPLATE.get(k, k)] = v
    return m

# ── 분류기 (세트/특수)
def classify(item: Dict) -> Optional[str]:
    if is_integ_meta_by_name(item):
        _trace("CANCER_CLASSIFY", f"type=INTEGRATED_META, name={_nz(item.get('name'))}")
        return "__INTEGRATED_META__"
    if is_integ_cancer_by_name(item):
        _trace("CANCER_CLASSIFY", f"type=INTEGRATED_CANCER, name={_nz(item.get('name'))}")
        return "__INTEGRATED_CANCER__"
    if drug_bucket(item) == "CT":
        _trace("CANCER_CLASSIFY", f"type=DRUG(CAR-T), name={_nz(item.get('name'))}")
        return LABEL_DRUG
    return None

# ── 집계기
def aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None:
    # 0) 통합세트
    if "__INTEGRATED_CANCER__" in bucket:
        items = bucket["__INTEGRATED_CANCER__"]
        main = [c for c in items if integ_main_match(c, meta=False)]
        v = _max_amt(main) if main else _max_amt(items)
        if v:
            out[LABEL_GENERAL] = f"통합암 {format_amount_short(v)}"
            _trace("C_AGG_INTEG_C", f"통합암={v}")

    if "__INTEGRATED_META__" in bucket:
        items = bucket["__INTEGRATED_META__"]
        main = [c for c in items if integ_main_match(c, meta=True)]
        v = _max_amt(main) if main else _max_amt(items)
        if v:
            out[LABEL_META] = f"통합전이 {format_amount_short(v)}"
            _trace("C_AGG_INTEG_M", f"통합전이={v}")

    # 1) 유사암 합산(세트+단일 최대)
    pseudo_sum = 0
    if LABEL_PSEUDO in bucket:
        items = bucket[LABEL_PSEUDO]

        def _is_set(c: Dict) -> bool:
            return any(k in _nosp(_nz(c.get("name",""))) for k in PSEUDO_SET_TOKENS)

        def _is_diag(c: Dict) -> bool:
            s = _nosp(_name_assoc(c))
            return ("진단" in s) or any(k in s for k in PSEUDO_DIAG_HINTS)

        set_vals = _amt_list([c for c in items if _is_set(c) and _is_diag(c) and not drop_pseudo_small(c)])
        single_vals = _amt_list([c for c in items if (not _is_set(c)) and _is_diag(c) and not drop_pseudo_small(c)])
        pseudo_sum = (max(set_vals) if set_vals else 0) + (max(single_vals) if single_vals else 0)
    if pseudo_sum:
        out[LABEL_PSEUDO] = f"유사암 {format_amount_short(pseudo_sum)}"
        _trace("C_AGG_PSEUDO", f"유사암합계={pseudo_sum}")

    # 2) 일반/고액(협회명)
    if (LABEL_GENERAL not in out) and (LABEL_GENERAL in bucket):
        items = bucket[LABEL_GENERAL]
        def _not_integ_name(c: Dict) -> bool:
            return not is_integ_cancer_by_name(c)
        general_v = _max_amt([c for c in items if _not_integ_name(c) and assoc_is_general_diag(_nz(c.get("association_name","")))])
        high_v    = _max_amt([c for c in items if assoc_is_high_diag(_nz(c.get("association_name","")))])
        parts = []
        if general_v: parts.append(f"일반암 {format_amount_short(general_v)}")
        if high_v:    parts.append(f"고액암 {format_amount_short(high_v)}")
        if parts:
            out[LABEL_GENERAL] = ", ".join(parts)
            _trace("C_AGG_GEN_HIGH", f"일반암={general_v}, 고액암={high_v}")

    # 3) 전이암(일반 전이)
    if (LABEL_META not in out) and (LABEL_META in bucket):
        items = bucket[LABEL_META]
        mv = _max_amt([c for c in items if ("전이" in _nosp(_name_assoc(c))) and ("진단" in _nosp(_name_assoc(c)))])
        if mv:
            out[LABEL_META] = f"전이암 {format_amount_short(mv)}"
            _trace("C_AGG_META", f"전이암={mv}")

    # 4) 항암방사선(서브버킷별 최대)
    if LABEL_RT in bucket:
        items = [c for c in bucket[LABEL_RT] if not drop_pseudo_small(c)]
        ci = _max_amt([c for c in items if rt_bucket(c) == "CI"])
        pr = _max_amt([c for c in items if rt_bucket(c) == "PR"])
        im = _max_amt([c for c in items if rt_bucket(c) == "IM"])
        rt = _max_amt([c for c in items if rt_bucket(c) == "RT"])
        parts = []
        if ci: parts.append(("중입자", ci))
        if pr: parts.append(("양성자", pr))
        if im: parts.append(("세기조절", im))
        if rt: parts.append(("방사선", rt))
        if parts:
            label_order = {"중입자":0, "양성자":1, "세기조절":2, "방사선":3}
            parts.sort(key=lambda kv: label_order.get(kv[0], 99))
            out[LABEL_RT] = ", ".join(f"{k} {format_amount_short(v)}" for k, v in parts)
            _trace("C_AGG_RT", f"parts={parts}")

    # 5) 약물 치료(콤보 정책 + 단일모달)
    if LABEL_DRUG in bucket:
        raw_items = bucket[LABEL_DRUG]
        items = []
        for c in raw_items:
            if drop_pseudo_small(c):
                _trace("C_PSEUDO_DROP@drug", _name_assoc(c))
                continue
            items.append(c)

        combo_mode = get_policy("combo_mode", "both")
        combo_or   = get_policy("combo_or_match", True)

        def _is_combo(c: Dict) -> bool:
            n, a = _nz(c.get("name","")), _nz(c.get("association_name",""))
            if combo_or:
                return is_rt_drug_combined(n, "") or is_rt_drug_combined("", a) or is_rt_drug_combined(n, a) or bool(c.get("_rt_drug_combo"))
            return is_rt_drug_combined(n, a) or bool(c.get("_rt_drug_combo"))

        combined = [c for c in items if _is_combo(c)]
        singles  = [c for c in items if c not in combined]

        buckets = {"TG": [], "HG": [], "GN": [], "CT": [], "HM": []}
        for c in singles:
            k = drug_bucket(c)
            if k in buckets:
                buckets[k].append(c)

        combo = _max_amt(combined)
        tg    = _max_amt(buckets["TG"])
        hg    = _max_amt(buckets["HG"])
        ct    = _max_amt(buckets["CT"])
        gn    = _max_amt(buckets["GN"])
        hm    = _max_amt(buckets["HM"])

        if ct:
            gn = 0

        parts: List[str] = []
        if combo_mode in ("both", "prefer_combo"):
            if combo: parts.append(f"방사선+약물 {format_amount_short(combo)}")
        if combo_mode in ("both", "prefer_split"):
            if tg: parts.append(f"표적 {format_amount_short(tg)}")
            if hg: parts.append(f"고액약물 {format_amount_short(hg)}")
            if ct: parts.append(f"카티 {format_amount_short(ct)}")
            if hm: parts.append(f"호르몬 {format_amount_short(hm)}")
            if not ct and gn: parts.append(f"항암약물 {format_amount_short(gn)}")

        if parts:
            order = ("방사선+약물","표적","고액약물","카티","호르몬","항암약물")
            parts.sort(key=lambda s: order.index(s.split()[0]) if s.split() else 999)
            out[LABEL_DRUG] = ", ".join(parts)
            _trace("C_AGG_DRUG", f"parts={parts}, combo={combo}, TG={tg}, HG={hg}, CT={ct}, GN={gn}, HM={hm}")

    # 6) 암주요치료비(_pay_mode 반영)
    if LABEL_MT in bucket and (LABEL_MT not in out):
        items = list(bucket[LABEL_MT])

        HINTS = ("통합치료","암통합치료","특정치료","특정치료비","특정치료지원금","특정치료지원",
                 "주요치료","중점치료","치료지원금","암주요치료","암특정치료")

        def _looks_mt(c: Dict) -> bool:
            s = _nosp(_name_assoc(c))
            if "암" not in s: return False
            if any(k in s for k in ("특정유사암","유사암특정")): return False
            if any(x in s for x in ("중입자","탄소이온","proton","양성자","imrt","세기조절","강도변조","방사선치료","항암방사선","방사선")):
                return False
            if any(x in s for x in ("표적","고액항암약물","신정원","항암약물","호르몬","항호르몬","내분비","카티","car-t","cart")):
                return False
            return any(h in s for h in HINTS)

        for bk, arr in bucket.items():
            if bk in (LABEL_MT, LABEL_RT, LABEL_DRUG, "__INTEGRATED_CANCER__", "__INTEGRATED_META__"):
                continue
            for c in arr or []:
                if _looks_mt(c) and c not in items:
                    items.append(c)

        groups = {"A": [], "B": [], "C": [], "D": []}  # A:통합/암통치, B:하이클래스, C:비례, D:정액
        for it in items:
            if drop_pseudo_small(it):
                continue
            pm = (it.get("_pay_mode") or "").strip() or (_infer_pay_mode_local(it) or "")
            if pm == "정액":
                groups["D"].append(it)
                _trace("C_AGG_MT_PM", f"D name={_nz(it.get('name'))} assoc={_nz(it.get('association_name'))}")
            elif pm == "비례":
                groups["C"].append(it)
                _trace("C_AGG_MT_PM", f"C name={_nz(it.get('name'))} assoc={_nz(it.get('association_name'))}")
            else:
                g = mt_group(it)
                groups[g].append(it)
                _trace("C_AGG_MT_PM", f"AUTO={g} name={_nz(it.get('name'))} assoc={_nz(it.get('association_name'))}")

        def _max_with_years(arr: List[Dict]) -> Tuple[int, Optional[int]]:
            if not arr: return 0, None
            mv = _max_amt(arr)
            ys: List[int] = []
            for x in arr:
                y = extract_years(x)
                if y: ys.append(y)
            return mv, (max(ys) if ys else None)

        a_v, a_y = _max_with_years(groups["A"])
        b_v, b_y = _max_with_years(groups["B"])
        c_v, c_y = _max_with_years(groups["C"])
        d_v, d_y = _max_with_years(groups["D"])

        parts: List[str] = []
        def _fmt_mt(tag, years, amt):
            y = f"{years}년, " if years else ""
            return f"암주요치료({y}{tag}) {format_amount_short(amt)}"

        if a_v: parts.append(_fmt_mt("통합", a_y, a_v))
        if b_v: parts.append(_fmt_mt("하이클래스", b_y, b_v))
        if c_v: parts.append(_fmt_mt("비례", c_y, c_v))
        if d_v: parts.append(_fmt_mt("정액", d_y, d_v))
        if parts:
            out[LABEL_MT] = ", ".join(parts)
            _trace("C_AGG_MT", f"parts={parts}")

    # 7) 암 수술비
    if (LABEL_CSURG in bucket) and (LABEL_CSURG not in out):
        v = _max_amt(bucket[LABEL_CSURG])
        if v:
            out[LABEL_CSURG] = f"암수술비 {format_amount_short(v)}"
            _trace("C_AGG_SURG", f"암수술비={v}")

    # 8) 암 입/통원 일당
    if (LABEL_DAY in bucket) and (LABEL_DAY not in out):
        items = bucket[LABEL_DAY]
        def _is_inp(c: Dict) -> bool:
            t = _nosp(_name_assoc(c)); return ("입원" in t) or ("입통원" in t) or ("입원의료비" in t)
        def _is_out(c: Dict) -> bool:
            t = _nosp(_name_assoc(c)); return ("통원" in t) or ("외래" in t) or ("통원의료비" in t)
        vin = _max_amt([c for c in items if _is_inp(c)])
        vout= _max_amt([c for c in items if _is_out(c)])
        if vin and vout: out[LABEL_DAY] = f"암입원 {format_amount_short(vin)}, 암통원 {format_amount_short(vout)}"
        elif vin:        out[LABEL_DAY] = f"암입원 {format_amount_short(vin)}"
        elif vout:       out[LABEL_DAY] = f"암통원 {format_amount_short(vout)}"
        if (vin or vout):
            _trace("C_AGG_DAY", f"암입원={vin}, 암통원={vout}")

    # 9) 라벨 리맵
    mapped = _remap_out_labels_for_template(out)
    out.clear(); out.update(mapped)


__all__ = ["classify", "aggregate"]
