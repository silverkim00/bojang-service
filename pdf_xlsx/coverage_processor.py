# coverage_processor.py — v2025-11-12b (KST, optimized & safe)
# -*- coding: utf-8 -*-
from __future__ import annotations

# ============================================================
# [섹션 A] 표준 라이브러리 / 외부 의존성
# ============================================================
import os
import re
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from . import config
from .utils import (
    _nz, _nosp,
    strip_exclusions,
    parse_amount, format_amount_short,
)
from .mapping_rules import find_target_row

# 암 정책
try:
    from .rules.ca import POLICY as CANCER_POLICY
except Exception:
    CANCER_POLICY = {
        "combo_mode": "both",
        "combo_or_match": True,
        "drop_pseudo_small_under": 2_000_000,
    }
# ============================================================
# [섹션 B0] 토큰·정규식 상수(중앙집중)
# ============================================================
SURGERY_TOKENS = frozenset((
    "수술","종수술","대수술","기관수술","기관수술비",
    "5대기관","7대기관","2대기관",
    "혈전용해","혈전용해치료","혈전용해치료비","혈전용해수술",
    "허혈성심장질환","허혈성심장질환수술","뇌혈관질환수술",
    "질병수술","특정질병수술","상해수술","재해수술",
))
RT_TOKENS   = frozenset(("중입자","탄소이온","proton","양성자","imrt","세기조절","강도변조","방사선","항암방사선","방사선치료"))
DRUG_TOKENS = frozenset(("표적","고액항암약물","신정원","항암약물","호르몬","항호르몬","내분비","카티","car-t","cart"))
CARE_TOKENS = frozenset(("시설급여","재가급여","주야간보호","주간보호","야간보호","장기요양"))

RX_G5_ANY     = re.compile(r"(?:질병|상해)?\s*(?:\d+\s*종\s*)?수술")
RX_G5_NUM     = re.compile(r"\d+\s*종\s*수술")
RX_ROOM_GRADE = re.compile(r"(?:[1-3]\s*인\s*실|1인실|2인실|3인실|상급\s*병실|특실)", re.I)
RX_COMBO_HINT = re.compile(r"(방사선)[\s\W_·ㆍ.]*?(약물)|(약물)[\s\W_·ㆍ.]*?(방사선)")

RX_PSEUDO_EXCL_RAW = re.compile(r"(?:\d+\s*대\s*)?유사암\s*제외|소액암\s*제외")
RX_PREMIUM_SUPPORT = re.compile(r"보험료\s*납입\s*지원")

RX_INTEGRATED_C      = re.compile(r"(통합형\s*일반암\s*진단비|통합\s*암\s*진단비|통합암진단비)")
RX_INTEGRATED_C_MAIN = re.compile(r"암\s*진단")
RX_INTEGRATED_C_DER  = re.compile(r"(특정|소화기|폐암|림프|백혈병|심장암|뇌암).*진단")

RX_INTEGRATED_M      = re.compile(r"(통합형\s*전이암\s*진단비|통합\s*전이암\s*진단비|통합전이암진단비)")
RX_INTEGRATED_M_MAIN = re.compile(r"전이암\s*진단")
RX_INTEGRATED_M_DER  = re.compile(r"(보장|특정.*전이암)")

# ============================================================
# [섹션 B] 외부 규칙 훅(존재하지 않아도 안전)
# ============================================================

try:
    from .rules.registry import (
        find_label as reg_find_label,
        should_exclude as reg_should_exclude,
        is_whitelisted as reg_is_whitelisted,
    )
except Exception:
    def reg_find_label(name: str, assoc: str): return None
    def reg_should_exclude(name: str, assoc: str): return False
    def reg_is_whitelisted(name: str, assoc: str): return False


try:
    from .rules.driver import classify as drv_classify, aggregate as drv_aggregate
except Exception:
    def drv_classify(item: Dict) -> Optional[str]: return None
    def drv_aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str], scope: Dict | None = None) -> None: return None


try:
    from .rules.dementia import classify as dem_classify, aggregate as dem_aggregate
except Exception:
    def dem_classify(item: Dict) -> Optional[str]: return None
    def dem_aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str], scope: Dict | None = None) -> None: return None


try:
    from .rules.nursing import aggregate as nursing_aggregate
    try:
        from .rules.nursing import classify as nursing_classify
    except Exception:
        nursing_classify = None
except Exception:
    def nursing_aggregate(bucket, out): return None
    nursing_classify = None


try:
    from .rules.death import aggregate as _death_override
except Exception:
    def _death_override(bucket, out, scope=None): return None


try:
    from .rules.heart import aggregate as _heart_override
except Exception:
    def _heart_override(bucket, out): return None


try:
    from .rules.icu import route_day_coverage as icu_route_day
    from .rules.icu import aggregate_icu as icu_aggregate_icu
    from .rules.icu import aggregate_inpatient as icu_aggregate_inpatient
except Exception:
    icu_route_day = None
    icu_aggregate_icu = None
    icu_aggregate_inpatient = None


try:
    from .rules.silson import aggregate as sil_aggregate
except Exception:
    def sil_aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None: return None

try:
    from .rules.silson import classify as sil_classify
except Exception:
    def sil_classify(item: Dict) -> Optional[str]: return None


try:
    from .rules.cancer import aggregate as cancer_aggregate
except Exception:
    def cancer_aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None: return None


try:
    from .rules.surgery import classify as surg_classify, aggregate as surg_aggregate
except Exception:
    def surg_classify(item: Dict) -> Optional[str]: return None
    def surg_aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None: return None


try:
    from .rules.fx_burn import aggregate as fxburn_aggregate
except Exception:
    def fxburn_aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None: return None


try:
    from .rules.dental import classify as dental_classify, aggregate as dental_aggregate
except Exception:
    def dental_classify(item): return None
    def dental_aggregate(bucket, out): return None


from .logger_setup import get_logger

def _trace(tag: str, msg: str) -> None:
    try:
        get_logger("app").info(f"TRACE[{tag}] {msg}")
    except Exception:
        pass

# ============================================================
# [섹션 C] 로깅/유틸
# ============================================================
def _name_assoc(c: Dict) -> str:
    return _nz(c.get("name", "")) + _nz(c.get("association_name", ""))

def _has_any(t: str, keys) -> bool:
    t = _nosp(t)
    return any(k in t for k in keys)

def _infer_pay_mode(c: Dict) -> Optional[str]:
    assoc_raw = _nz(c.get("association_name", ""))
    assoc = _nosp(assoc_raw).lower()
    typ   = _nosp(_nz(c.get("type", ""))).lower()
    if assoc == "" or assoc == "null": return "비례"
    if ("정액" in assoc_raw) or ("정액" in typ): return "정액"
    return None

def _norm_coverages(raw) -> List[Dict[str, str]]:
    covs = []
    product = _nz((isinstance(raw, dict) and (raw.get("product_name") or raw.get("상품명") or raw.get("name") or raw.get("title"))) or "")
    for c in (raw.get("coverages") if isinstance(raw, dict) else []) or []:
        if not isinstance(c, dict): continue
        covs.append({
            "product_name": product,
            "page": _nz(c.get("page") or c.get("page_no") or c.get("_page") or ""),
            "name": _nz(c.get("name") or c.get("title")),
            "association_name": _nz(c.get("association_name") or c.get("assoc") or c.get("category")),
            "amount": _nz(c.get("amount") or c.get("value") or "0"),
            "type": _nz(c.get("type") or c.get("category")),
            "block_no": c.get("block_no") or c.get("block"),
            "_raw": c,
        })
    return covs

_UNMAPPED_LOG = getattr(config, "UNMAPPED_LOG", getattr(config, "UNMAPPED_LOG_FILE", "unmapped_log.txt"))
_EXCLUDED_LOG = getattr(config, "EXCLUDED_LOG", getattr(config, "EXCLUDED_LOG_FILE", "excluded_log.txt"))

def _fmt_log_line(c: Dict, seq: int | None = None) -> str:
    z = lambda x: (x or "").strip()
    ty, name, assoc = z(c.get("type")), z(c.get("name")), z(c.get("association_name")) or "-"
    try:
        v = c.get("_amt")
        if v is None:
            v = parse_amount(c.get("amount")) if isinstance(c.get("amount"), (int, float, str)) else None
    except Exception:
        v = None
    amt_short = format_amount_short(v) if v else "-"

    raw = c.get("block_no") or (isinstance(c.get("_raw"), dict) and (c["_raw"].get("block_no") or c["_raw"].get("block")))
    blk = None
    if raw is not None:
        try:
            blk = max(int(str(raw).strip()) - 6, 1)  # 원본7→1
        except Exception:
            blk = None
    if blk is None:
        blk = seq if seq is not None else "-"

    reason = (c.get("_reason") or "").strip()
    hint   = (c.get("_hint") or "").strip()

    cols = [f"{blk}", f"{ty or '-'}", f"{name or '-'}", f"{assoc or '-'}", f"{amt_short}", f"{reason or ''}", f"{hint or ''}"]
    return " | ".join([x if x != "" else "-" for x in cols]) + " |"

def _write(path: str, items: List[Dict], product: dict | None = None):
    try:
        from loggers.log_writer import write as _lw
        _lw(path, items, product); return
    except Exception:
        pass
    try:
        d = os.path.dirname(path);  os.makedirs(d, exist_ok=True) if d else None
        with open(path, "a", encoding="utf-8-sig") as f:
            if product:
                comp = (product.get("company") or product.get("회사") or "").strip()
                prod = (product.get("product_name") or product.get("상품명") or "").strip()
                cdate= (product.get("contract_date") or "").strip()
                prem = (product.get("monthly_premium") or "").strip()
                tail = []
                if cdate: tail.append(f"가입일자: {cdate}")
                if prem:  tail.append(f"월납: {prem}")
                f.write("\n" + "="*92 + "\n")
                f.write(f"상품 시작 : {comp} | {prod} {'| ' + ' | '.join(tail) if tail else ''}\n")
                f.write("주요 보장 목록 (블럭 1부터)\n")
                f.write("-"*92 + "\n")
            for i, c in enumerate(items, 1):
                f.write(_fmt_log_line(c, seq=i) + "\n")
            if product:
                f.write("-"*92 + "\n")
                f.write("#######  상품 종료 (END OF PRODUCT)  #######\n")
                f.write("="*92 + "\n\n")
    except Exception:
        pass

# ============================================================
# [섹션 D] 제외/화이트리스트(로컬) — 교통상해사망 가드 포함
# ============================================================
TRAFFIC_DEATH_RX = re.compile(r"교\s*통\s*(?:상해\s*)?사망")

_FORCE_EXC_KEYS = (
    "자동차보험료","보험료할증","할증","형사합의","위로금","비표준실손",
    "5대골절","5대골절수술비","5대골절진단비","중대골절","중대화상","중증화상"
)
_BASE_EXC_KEYS  = ["관혈","비관혈","생활질병"] + list(getattr(config, "EXCLUSION_KEYWORDS", []))

def _exclude_reason(name: str, assoc: str) -> tuple[bool, str | None]:
    """
    로컬 제외 규칙(정규화 이전 문자열 포함 검사):
      - 교통상해사망: 무조건 제외(EXC/TRAFFIC_DEATH)
      - 산정특례 진단/특정상해후유장해: 제외
      - 운전자/배상/벌금/실손·암치료 도메인: 통과
      - 강제 제외 키/전역 EXCLUSION(수술 도메인 제외 시): 제외
      - 사망/후유장해 자체는 통과(별도 훅이 처리)
    """
    raw = (name or "") + (assoc or "")
    if TRAFFIC_DEATH_RX.search(raw):
        return True, "EXC/TRAFFIC_DEATH"

    s = _nosp(raw)

    has_surgery_domain = ("수술" in s) or any(k in s for k in SURGERY_TOKENS)

    if "특정상해후유장해" in s:
        return True, "EXC/SPECIFIC_INJURY_IMPAIRMENT"
    if ("산정특례" in s) and (("진단" in s) or ("진단비" in s)):
        return True, "EXC/SANJEONGTOKRYE_DIAG"

    if "교통사고처리지원금" in s:
        return False, None

    # 암 치료/지원/RT/Drug/카티/입·통원 신호는 통과
    if ("암" in s) and (
        any(k in s for k in ("치료지원금","주요치료","특정치료","통합치료","암주요치료","암특정치료")) or
        any(k in s for k in RT_TOKENS) or
        any(k in s for k in DRUG_TOKENS) or
        any(k in s for k in ("입원","통원","입원일당","통원일당","입원비","통원비"))
    ):
        return False, None

    if any(k in s for k in ("특정순환계질환","순환계질환","순환계")) and any(k in s for k in ("치료","치료비","통합치료")):
        return False, None

    if any(k in s for k in ("일상생활배상책임","가족생활배상책임","가족일상생활배상책임","일배","가배책",
                             "교통사고처리","형사합의","변호사선임","방어비용","벌금","화재벌금","자동차사고부상","자동차부상")):
        return False, None

    if any(k in s for k in ("의료비","입원의료비","통원의료비","비급여mri","mri검사","mri","주사제","비급여주사","도수","체외충격파","증식치료")):
        return False, None

    if any(k in s for k in _FORCE_EXC_KEYS):
        k = next(k for k in _FORCE_EXC_KEYS if k in s)
        return True, f"EXC/RULE:{k}"

    if RX_G5_NUM.search(s):
        return False, None

    if not has_surgery_domain:
        for k in _BASE_EXC_KEYS:
            if k.replace(" ", "") in s:
                return True, f"EXC/KEY:{k}"

    if ("교통" in s) and ("후유장해" in s):
        return True, "EXC/KEY:교통후유장해"

    if ("사망" in s) or ("후유장해" in s):
        return False, None

    if any(k in s for k in CARE_TOKENS):
        return False, None

    return False, None

# ============================================================
# [섹션 E] 라벨/별칭/정규식
# ============================================================
_OTHER_LABEL = next((k for k in ("기타","기타담보","기타(참고)","비고") if k in config.HARDCODED_ROW_MAP), "기타")
_CANCER_SURGERY_LABEL = next((k for k in ("암 수술비","암수술비","암 수술","암수술") if k in config.HARDCODED_ROW_MAP), "암 수술비")
_NURSING_LABEL = next((k for k in ("간병인/간호통합",) if k in config.HARDCODED_ROW_MAP), "간병인/간호통합")

LABEL_ALIASES_TO_TEMPLATE = {
    "유사암": "유사암-갑,기,경,제",
    "허혈성심장질환진단비": "심장질환진단비",
    "허혈성 심장질환진단비": "심장질환진단비",
}

# ============================================================
# [섹션 F] 집계(버킷 생성)
# ============================================================
def aggregate_coverages(product: dict) -> Tuple[Dict[str, List[Dict]], List[str], List[str]]:
    covs = _norm_coverages(product)
    # 캐싱(정규화된 문자열/금액)
    for c in covs:
        name  = _nz(c.get("name", ""));  assoc = _nz(c.get("association_name", ""))
        ns_n  = _nosp(name);             ns_a  = _nosp(assoc)
        c["_ns_name"], c["_ns_assoc"] = ns_n, ns_a
        c["_ns_all"] = ns_n + "|" + ns_a
        try:
            c["_amt"] = int(parse_amount(c.get("amount", "0"))) or 0
        except Exception:
            c["_amt"] = 0

    product_has_cancer = any("암" in (c.get("_ns_all") or "") for c in covs or [])

    # 통합세트 메인 금액 수집
    integ_main_c = set(); integ_main_m = set()
    for _c in covs or []:
        nm = _c.get("_ns_name",""); ac = _c.get("_ns_assoc","")
        v = _c.get("_amt", 0)
        if v <= 0: continue
        if RX_INTEGRATED_C.search(nm) and RX_INTEGRATED_C_MAIN.search(ac):
            integ_main_c.add(v)
        if RX_INTEGRATED_M.search(nm) and (("전이암" in ac and "진단" in ac) or RX_INTEGRATED_M_MAIN.search(ac)):
            integ_main_m.add(v)

    kept, excluded = [], []
    for c in covs:
        nm, ac = _nz(c.get("name", "")), _nz(c.get("association_name", ""))
        s_all = c.get("_ns_all","")

        # 화이트리스트 우선 통과
        if reg_is_whitelisted(nm, ac):
            kept.append(c);  continue

        # === G5/PREPASS_START ===
        if RX_G5_ANY.search(s_all) and ("종수술" in s_all or RX_G5_NUM.search(s_all)):
            c["_g5_prepass"] = True
            kept.append(c)
            continue
        # === G5/PREPASS_END ===

        # === CARE_PREPASS_START ===
        if any(k in s_all for k in CARE_TOKENS):
            c["_care_prepass"] = True
            kept.append(c)
            continue
        # === CARE_PREPASS_END ===

        # 로컬/레지스트리 제외
        base_ex, base_reason = _exclude_reason(nm, ac)
        blk_ex  = reg_should_exclude(nm, ac)

        if base_ex or blk_ex:
            # 암 치료 도메인 관대 통과(교통상해사망은 이미 base_ex에서 컷)
            if ("암" in s_all) and (
                any(k in s_all for k in ("치료지원금","주요치료","특정치료","통합치료","암주요치료","암특정치료")) or
                any(k in s_all for k in RT_TOKENS) or
                any(k in s_all for k in DRUG_TOKENS)
            ):
                kept.append(c);  continue

            if RX_G5_ANY.search(s_all) and ("종수술" in s_all or RX_G5_NUM.search(s_all)):
                kept.append(c);  continue

            if not base_reason and blk_ex:
                base_reason = "EXC/BLACKLIST"
            c["_reason"] = base_reason or "EXC"
            excluded.append(c); continue

        kept.append(c)

    if excluded: _write(_EXCLUDED_LOG, excluded, product)

    bucket: Dict[str, List[Dict]] = defaultdict(list)
    unmapped: List[Dict] = []
    excluded_post: List[Dict] = []

    meta_seen = 0; meta_routed = 0

    def _has_rt(txt: str) -> bool:
        t = _nosp(txt)
        return any(k in t for k in RT_TOKENS)
    def _has_drug(txt: str) -> bool:
        t = _nosp(txt)
        return any(k in t for k in DRUG_TOKENS)

    for c in kept:
        name = _nz(c.get("name", "")); assoc = _nz(c.get("association_name", ""))
        nm_ns, ac_ns = c.get("_ns_name",""), c.get("_ns_assoc","")
        s_all = c.get("_ns_all","")

        if ("전이" in s_all) and ("암" in s_all):
            meta_seen += 1
            _trace("FLOW_META_CAND@covagg", f"name={name}, assoc={assoc}")

        # 합본 판정
        name_rt, name_dr = _has_rt(name), _has_drug(name)
        assoc_rt, assoc_dr= _has_rt(assoc), _has_drug(assoc)
        strict_both = (name_rt and name_dr) and (assoc_rt and assoc_dr)
        loose_hint  = ("항암방사선약물치료비" in s_all) or ("방사선약물" in s_all) or ("방사선·약물" in s_all) or ("방사선.약물" in s_all) or ("약물·방사선" in s_all) or bool(RX_COMBO_HINT.search(s_all))
        cross_pair  = (name_rt and assoc_dr) or (name_dr and assoc_rt)
        combo_or = bool(CANCER_POLICY.get("combo_or_match", True))
        is_combo = strict_both or loose_hint or (cross_pair if combo_or else False)

        # 통합암/전이(메인만 유지)
        if RX_INTEGRATED_C.search(nm_ns):
            amt = c.get("_amt", 0)
            if RX_INTEGRATED_C_MAIN.search(ac_ns):
                if product_has_cancer: bucket["__INTEGRATED_CANCER__"].append(c)
                continue
            else:
                if (integ_main_c and (amt in integ_main_c)) and (RX_INTEGRATED_C_DER.search(ac_ns) or RX_INTEGRATED_C_DER.search(nm_ns)):
                    c["_reason"] = "세트"; excluded_post.append(c); continue

        if RX_INTEGRATED_M.search(nm_ns):
            amt = c.get("_amt", 0)
            is_meta_main = ((("전이암" in ac_ns) and ("진단" in ac_ns)) or RX_INTEGRATED_M_MAIN.search(ac_ns) or RX_INTEGRATED_M_MAIN.search(nm_ns) or (("전이암" in nm_ns) and ("진단" in (nm_ns+ac_ns))))
            if is_meta_main:
                if product_has_cancer:
                    bucket["__INTEGRATED_META__"].append(c); meta_routed += 1
                    _trace("FLOW_META_ROUTE@covagg", f"bucket=__INTEGRATED_META__, name={name}, assoc={assoc}, amt={_nz(c.get('amount'))}")
                continue
            else:
                if (integ_main_m and (amt in integ_main_m)) or RX_INTEGRATED_M_DER.search(ac_ns) or RX_INTEGRATED_M_DER.search(nm_ns):
                    c["_reason"] = "세트"; excluded_post.append(c); continue

        # 운전자/치매
        drv_label = drv_classify(c)
        if drv_label: bucket[drv_label].append(c); continue
        dem_label = dem_classify(c)
        if dem_label: bucket[dem_label].append(c); continue

        # 간병
        routed_nursing = False
        try:
            if nursing_classify is not None:
                lbl = nursing_classify(c)
                if lbl: bucket[lbl].append(c); routed_nursing = True
            else:
                if any(k in s_all for k in ("간병인","간호간병통합","간호·간병통합","간호간병")):
                    bucket[_NURSING_LABEL].append(c); routed_nursing = True
        except Exception:
            if any(k in s_all for k in ("간병인","간호간병통합","간호·간병통합","간호간병")):
                bucket[_NURSING_LABEL].append(c); routed_nursing = True
        if routed_nursing: continue

        # 치아
        try:
            dent_lbl = dental_classify(c)
        except Exception:
            dent_lbl = None
        if dent_lbl:
            bucket[dent_lbl].append(c)
            continue

        # 하드 라벨 직결(안전 목록)
        direct = find_target_row(name, assoc) or reg_find_label(name, assoc)
        DIRECT_ALLOW = {
            "질병사망","상해사망","질병후유장해","상해후유장해",
            "질병,상해 입원의료비","질병,상해 통원의료비","도수,체외충격파,증식","비급여주사료","비급여영상진단MRI",
            "교통사고 처리지원금(형사합의금)","변호사 선임비용(방어비용)","자동차 부상 치료비","벌금 대인/대물",
            "일상생활배상책임","가족생활배상책임","화재벌금",
            "골절,화상 진단비","골절,화상 수술비",
        }
        if direct in DIRECT_ALLOW:
            bucket[direct].append(c);  continue

        # 유사/소액 제외 → 일반암 진단 라우팅
        if RX_PSEUDO_EXCL_RAW.search(s_all) and product_has_cancer:
            if ("진단" in s_all) or ("진단비" in s_all):
                bucket["일반암/고액암 진단비"].append(c); continue

        # 의도 플래그
        def _intent_flags(name: str, assoc: str) -> Dict[str, bool]:
            n = _nosp(name); combined = _nosp(f"{assoc}|{name}")
            TWO_MAJOR_TOKENS = ("혈전용해","혈전용해치료","혈전용해치료비","혈전용해수술","뇌혈관질환수술","허혈성심장질환수술")
            ORGANS_TOKENS = ("5대기관","7대기관","2대기관","대기관","기관수술","기관수술비")
            return {
                "surgery": ("수술" in n)
                           or any(k in combined for k in ("다빈치","다빈치로봇","로봇수술"))
                           or any(k in combined for k in TWO_MAJOR_TOKENS)
                           or any(k in combined for k in ORGANS_TOKENS),
                "treat":   any(k in combined for k in RT_TOKENS)
                           or any(k in combined for k in DRUG_TOKENS)
                           or any(k in combined for k in ("통합치료","암통합치료","특정치료","특정치료비","특정치료지원금","특정치료지원","주요치료","중점치료","치료지원금","암주요치료","암특정치료","특정순환계질환","급여치료비","방사선약물","방사선·약물","방사선.약물")),
                "day":     ("일당" in combined) or bool(re.search(r"암.*(입원|통원).*(일당|비)", combined)),
                "diag":    ("진단" in combined) or ("진단비" in combined),
            }
        flags = _intent_flags(name, assoc)

        name_m  = strip_exclusions(name)
        assoc_m = ("" if flags["surgery"] else strip_exclusions(assoc))
        tns = _nosp(name_m + assoc_m)

        # 보험료 납입지원 → 기타
        if RX_PREMIUM_SUPPORT.search(tns):
            bucket[_OTHER_LABEL].append(c);  continue

        # 암 입·통원 일당
        if product_has_cancer and ("암" in tns) and _has_any(tns, ("입원","통원","입원비","통원비","입원일당","통원일당","직접치료입원","직접치료통원")):
            bucket["암 입,통원일당"].append(c);  continue

        # 수술 > 치료 > 일당 > 진단
        if flags["surgery"]:
            # 특정질병수술 쌍일치 제외
            if _nosp(name) == "특정질병수술" and _nosp(assoc) == "특정질병수술":
                c["_reason"] = "EXC/SURG_SPECIFIC_DUAL"
                excluded_post.append(c); continue

            s_lbl = surg_classify(c)
            if s_lbl:
                if s_lbl == "__SURG_DROP__":
                    c["_reason"] = "세트" if c.get("_reason") == "세트" else "EXC/SURG_DROP"
                    excluded_post.append(c); continue
                bucket[s_lbl].append(c); continue

            t_all = _nosp(name + "|" + assoc)
            assoc_lower = _nosp(assoc)
            is_injury_assoc  = _has_any(assoc_lower, ("상해수술","재해수술"))
            is_disease_assoc = _has_any(assoc_lower, ("질병수술","특정질병수술"))

            is_davinci = any(k in t_all for k in ("다빈치","다빈치로봇","로봇수술"))
            if ("암" in t_all) and is_davinci and product_has_cancer:
                bucket[_CANCER_SURGERY_LABEL].append(c); continue

            if ("암" in t_all and "수술" in t_all and not (is_injury_assoc or is_disease_assoc) and product_has_cancer):
                bucket[_CANCER_SURGERY_LABEL].append(c)
            else:
                sj = find_target_row(name_m, assoc_m) or reg_find_label(name_m, assoc_m)
                if not sj:
                    if is_injury_assoc or _has_any(t_all, ("상해수술",)): sj = "상해 수술비"
                    elif is_disease_assoc or _has_any(t_all, ("질병수술","특정질병수술",)): sj = "질병 수술비"
                if sj: bucket[sj].append(c)
            continue

        if flags["treat"]:
            if is_combo:
                c["_rt_drug_combo"] = True
                bucket["약물 치료"].append(c)
                _trace("C_ROUTE_COMBO@covagg", f"why={'STRICT' if strict_both else 'OR_MATCH' if (cross_pair or loose_hint) else 'HINT'}, name={name}, assoc={assoc}, amt={c.get('amount')}")
                continue

            has_rt_like = name_rt or assoc_rt
            has_drug_like = name_dr or assoc_dr
            is_circ = any(k in s_all for k in ("특정순환계질환","순환계질환","순환계","심뇌혈관","2대주요"))
            if is_circ and ("암" not in s_all) and (not has_rt_like) and (not has_drug_like) and ("수술" not in s_all):
                if any(k in s_all for k in ("통합치료","통합치료비")):
                    c["_circ_grp"] = "integrated"; bucket["2대주요치료비"].append(c)
                    _trace("FLOW_BUCKET_IN@two_circ_treat", f"grp=integrated, name={name}, assoc={assoc}, amt={c.get('amount')}")
                    continue
                if any(k in s_all for k in ("특정치료","특정치료비","특정치료지원금","특정치료지원","주요치료","중점치료","치료지원금","급여치료비")):
                    c["_circ_grp"] = "main"; bucket["2대주요치료비"].append(c)
                    _trace("FLOW_BUCKET_IN@two_circ_treat", f"grp=main, name={name}, assoc={assoc}, amt={c.get('amount')}")
                    continue

            tgt = find_target_row(name_m, assoc_m) or reg_find_label(name_m, assoc_m)
            if not tgt:
                if has_rt_like:   tgt = "항암방사선"
                elif has_drug_like: tgt = "약물 치료"
            if tgt:
                bucket[tgt].append(c)
                _trace("FLOW_BUCKET_IN@covagg", f"bucket={tgt}, name={name}, assoc={assoc}, amt={c.get('amount')}")
                continue

            if any(k in s_all for k in ("특정유사암","유사암특정")) and any(k in s_all for k in ("치료","치료비")):
                c["_reason"] = "EXC/PSEUDO_TREAT"; excluded_post.append(c); continue

            tgt = find_target_row(name_m, assoc_m) or reg_find_label(name_m, assoc_m)
            if not tgt:
                if name_rt or assoc_rt:   tgt = "항암방사선"
                elif name_dr or assoc_dr: tgt = "약물 치료"
                elif any(k in s_all for k in ("통합치료","특정치료","주요치료","중점치료","치료지원금","암주요치료","암특정치료")):
                    tgt = "암주요치료비"
            if tgt:
                bucket[tgt].append(c);  continue

        if flags["day"]:
            if icu_route_day is not None:
                try:
                    handled = bool(icu_route_day(c, bucket, excluded_post))
                except Exception:
                    handled = False
                if handled:
                    continue
            if RX_ROOM_GRADE.search(tns):
                c["_reason"] = "EXC/ROOM_GRADE"; excluded_post.append(c); continue
            bucket["질병,상해 입원일당"].append(c); continue

        slbl = sil_classify(c)
        if slbl:
            bucket[slbl].append(c)
            continue

        if flags["diag"]:
            tgt = find_target_row(name_m, assoc_m) or reg_find_label(name_m, assoc_m)
            if not tgt and any(k in tns for k in ("유사암","소액암","갑상선암","기타피부암","경계성종양","제자리암")) and product_has_cancer:
                tgt = "유사암"
            if not tgt and ("암" in tns) and (("진단" in tns) or ("진단비" in tns)) and product_has_cancer:
                tgt = "일반암/고액암 진단비"
            if tgt: bucket[tgt].append(c);  continue

        fb = find_target_row(name_m or name, assoc_m or assoc) or reg_find_label(name_m or name, assoc_m or assoc)
        if fb:
            if fb == "유사암-갑,기,경,제": fb = "유사암"
            if (fb in ("암주요치료비","항암방사선","약물 치료","암 입,통원일당","유사암","일반암/고액암 진단비", _CANCER_SURGERY_LABEL)) and (not product_has_cancer):
                c["_reason"] = "UMAP/PRODUCT_NO_CANCER_SCOPE";  unmapped.append(c)
            else:
                bucket[fb].append(c)
            continue

        c["_reason"] = "UMAP/NORULE"
        hint = reg_find_label(name, assoc)
        if hint: c["_hint"] = f"후보행:{hint}"
        unmapped.append(c)
        _trace("UMAP_NORULE@covagg", f"name={name}, assoc={assoc}")

    # 유사암 세트 축소(세트/단일 각 1건만)
    def _shrink_pseudo(label: str):
        items = bucket.get(label, [])
        if len(items) <= 2: return
        SET_TOKENS = ("갑상선암","기타피부암","경계성종양","제자리암")
        def _is_set(x: Dict) -> bool:
            return any(k in _nosp(_nz(x.get("name",""))) for k in SET_TOKENS)

        set_items   = [x for x in items if _is_set(x)]
        single_items= [x for x in items if not _is_set(x)]

        def _pick_max(arr: List[Dict]) -> List[Dict]:
            if not arr: return []
            try:
                amts = [(int(x.get("_amt", 0)), idx) for idx, x in enumerate(arr)]
                keep_idx = max(amts, key=lambda t: t[0])[1]
                return [arr[keep_idx]]
            except Exception:
                return [arr[0]]

        survivors = _pick_max(set_items) + _pick_max(single_items)
        survivors = [x for x in survivors if x]
        drops = [x for x in items if x not in survivors]
        for d in drops:
            d["_reason"] = "AGG/SET_MAX_ONLY"
            excluded_post.append(d)
        bucket[label] = survivors if survivors else items[:1]

    _shrink_pseudo("유사암")

    _trace("FLOW_SUMMARY@covagg", f"meta_seen={meta_seen}, meta_routed={meta_routed}, buckets={list(bucket.keys())}")

    if excluded_post: _write(_EXCLUDED_LOG, excluded_post, product)
    if unmapped: _write(_UNMAPPED_LOG, unmapped, product)

    return bucket, [f"{_nz(x.get('name'))}|{_nz(x.get('association_name'))}|{_nz(x.get('amount'))}" for x in unmapped], \
           [f"{_nz(x.get('name'))}|{_nz(x.get('association_name'))}" for x in (excluded + excluded_post)]

# ============================================================
# [섹션 G] 라벨 별칭 → 템플릿 키로 보정
# ============================================================
def _remap_out_labels_for_template(out: Dict[str, str]) -> Dict[str, str]:
    """
    - 가변 종수 키(예: '질병3-4종 수술비', '상해3-5종 수술비')를
      템플릿의 단일 행 '질병,상해 종수술비'로 병합.
    - 같은 행에 여러 값이 모이면 ', '로 병기.
    - 기존 별칭 매핑(LABEL_ALIASES_TO_TEMPLATE)도 유지.
    """
    if not isinstance(out, dict):
        return out
    remapped: Dict[str, str] = {}

    rx_g5_var = re.compile(r"^(질병|상해)\s*\d+(?:-\d+)?종\s*수술비$")
    rx_g5_nok = re.compile(r"^(질병|상해)\s*(?:수술비\(종수\s*미표기\)|종\s*수술)$")

    def _merge(row_key: str, val: str):
        if not val:
            return
        if row_key in remapped and remapped[row_key]:
            if val not in remapped[row_key]:
                remapped[row_key] = f"{remapped[row_key]}, {val}"
        else:
            remapped[row_key] = val

    for k, v in out.items():
        alias = LABEL_ALIASES_TO_TEMPLATE.get(k)
        if alias:
            _merge(alias, v)
            continue

        if rx_g5_var.match(k) or rx_g5_nok.match(k):
            _merge("질병,상해 종수술비", f"{k} {v}")
            continue

        _merge(k, v)

    return remapped

# ============================================================
# [섹션 H] 최종 산출
# ============================================================
def _max_amt(items: List[Dict]) -> int:
    m = 0
    for i in items or []:
        v = i.get("_amt") or 0
        if v > m: m = v
    return m

def process_coverages(product: dict) -> Tuple[Dict[str, str], List[str], List[str]]:
    bucket, umap, excl = aggregate_coverages(product)
    out: Dict[str, str] = {}

    # 사망/후유(최대값)
    for key in ["질병사망","질병후유장해","상해사망","상해후유장해"]:
        if key in bucket:
            v = _max_amt(bucket[key])
            if v: out[key] = f"{key} {format_amount_short(v)}"

    # 간병
    try: nursing_aggregate(bucket, out)
    except Exception: pass

    # ICU
    try:
        if icu_aggregate_icu is not None:
            token_helper = None
            try:
                from rules.heart import analyze_tokens as _an
                token_helper = _an
            except Exception:
                token_helper = None
            icu_aggregate_icu(bucket, out, token_helper)
        if icu_aggregate_inpatient is not None:
            icu_aggregate_inpatient(bucket, out)
    except Exception:
        pass

    # 수술
    try: surg_aggregate(bucket, out)
    except Exception: pass

    # 운전자/치매/후유 훅
    try: _death_override(bucket, out, scope=None)
    except Exception: pass
    try: dem_aggregate(bucket, out, scope={"product_has_cancer": None})
    except Exception: pass
    try: drv_aggregate(bucket, out, scope={"product_has_cancer": None})
    except Exception: pass

    # 골절·화상·배상·벌금
    try: fxburn_aggregate(bucket, out)
    except Exception: pass

    # 치아
    try: dental_aggregate(bucket, out)
    except Exception: pass

    # 실손
    try:
        _trace("SILSON_CALL@proc", f"pre_out_keys={list(out.keys())}")
        sil_aggregate(bucket, out)
        _trace("SILSON_RET@proc", f"post_out_keys={list(out.keys())}")
    except Exception:
        pass

    # 암
    try:
        _trace("CANCER_CALL@proc", f"IC={len(bucket.get('__INTEGRATED_CANCER__', []))}, IM={len(bucket.get('__INTEGRATED_META__', []))}, out_pre={list(out.keys())}")
        cancer_aggregate(bucket, out)
        _trace("CANCER_RET@proc", f"out_post={list(out.keys())}")
    except Exception as e:
        _trace("CANCER_ERR@proc", f"{type(e).__name__}: {e}")

    # HEART 보정
    try: _heart_override(bucket, out)
    except Exception: pass

    # 세트 잔여 드롭 재로그
    try:
        discards = []
        for items in bucket.values():
            for c in items:
                r = (c.get("_reason") or "").strip()
                if r in ("세트", "AGG/SET_MAX_ONLY"):
                    discards.append(c)
        if discards:
            _write(_EXCLUDED_LOG, discards, product)
    except Exception:
        pass

    # ICU 버킷 존재/미출력 시 언매핑 힌트
    try:
        _icu_keys = ("질병,상해 중환자 입원일당","질병,상해 입원일당")
        if any(k in bucket for k in _icu_keys) and not any(k in out for k in _icu_keys):
            suspects = []
            for k in _icu_keys:
                for c in bucket.get(k, []):
                    cc = dict(c); cc["_reason"] = "UMAP/ICU_OUTPUT_MISSING"
                    suspects.append(cc)
            if suspects:
                _write(_UNMAPPED_LOG, suspects, product)
    except Exception:
        pass

    # 갱신(초록) 플래그 산출
    try:
        def _is_renewal_line(raw_name: str, raw_assoc: str) -> bool:
            s = f"{_nz(raw_name)}|{_nz(raw_assoc)}"
            if re.search(r"(비\s*갱신형|갱신.{0,6}(보험료|납입|면제|대체))", s):
                return False
            return any(k in s for k in ("갱신","갱신형","자동갱신"))
        row_flags = {}
        for label, items in bucket.items():
            row = config.HARDCODED_ROW_MAP.get(label)
            if not row: continue
            flags = row_flags.setdefault(int(row), [])
            for c in items:
                flags.append(_is_renewal_line(c.get("name",""), c.get("association_name","")))
        out["_ROW_RENEWAL_ALL"] = sorted([r for r, fs in row_flags.items() if fs and all(fs)])
        out["_ROW_RENEWAL_ANY"] = sorted([r for r, fs in row_flags.items() if any(fs)])
    except Exception:
        pass

    # 스냅샷 트레이스
    try:
        has_ic = ("일반암/고액암 진단비" in out) and ("통합암" in (_nz(out.get("일반암/고액암 진단비"))))
        has_im = ("전이암" in out) and ("통합전이" in (_nz(out.get("전이암"))))
        _trace("OUT_SNAPSHOT@proc", f"has_IC={has_ic}, has_IM={has_im}, out_keys={list(out.keys())}")
    except Exception:
        pass

    out = _remap_out_labels_for_template(out)
    return out, umap, excl
