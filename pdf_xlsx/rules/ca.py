# -*- coding: utf-8 -*-
# rules/ca.py — Cancer domain policy (tokens/regex/buckets/renewal) — v2025-11-04

from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple, Literal

# (옵션) TRACE 로깅
try:
    from logger_setup import logger as _log
    def _trace(tag: str, msg: str): _log.info(f"TRACE[CA.{tag}] {msg}")
except Exception:  # 로거 미존재 환경 호환
    def _trace(tag: str, msg: str): pass


# ─────────────────────────────────────────────────────────
# 정책 파라미터
# ─────────────────────────────────────────────────────────
POLICY = {
    # RT+Drug 합본 표기 정책: 'both' | 'prefer_combo' | 'prefer_split'
    "combo_mode": "both",

    # OR 매칭 허용: 이름/협회 중 한 쪽에만 RT+Drug 동시 존재해도 합본 인정
    "combo_or_match": True,

    # 특정유사암/유사암특정 '치료' 소액 컷(원). limit 이하(≤)는 드롭, '제외' 토큰 있으면 보존
    "drop_pseudo_small_under": 2_000_000,

    # 갱신 판정: '비갱신' 토큰이 있으면 강제 비갱신, 그 외 '갱신' 토큰 있으면 갱신
    # (엣지: '보험료 갱신' 등 의미 왜곡 토큰은 상위 엔진에서 이미 필터링됨)
}

def get_policy(key: str, default=None):
    return POLICY.get(key, default)


# ─────────────────────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────────────────────
def _nz(s: object) -> str:
    return s if isinstance(s, str) else ""

def _nosp(s: object) -> str:
    return re.sub(r"\s+", "", _nz(s))

def _name_assoc(c: Dict) -> str:
    return f"{_nz(c.get('name',''))}|{_nz(c.get('association_name',''))}"

def normalize_amount_to_int(x) -> int:
    """금액 파싱: int/float/str(숫자·콤마·한글단위 섞임) 허용. 실패 시 0."""
    if x is None: return 0
    if isinstance(x, (int, float)): return int(x)
    s = _nz(x)

    # 한글 단위 처리(억/만). '1억2천3백만' 같은 복합은 안전하게 숫자만 추출 후 보수 처리.
    # 여기서는 보편 케이스: "1억", "3천만", "120만" 정도만 커버 (정밀 파서는 상위 유틸 존중)
    s_num = re.sub(r"[^\d]", "", s)
    try:
        n = int(s_num) if s_num else 0
    except Exception:
        n = 0

    # 억/만 토큰이 명확하면 보정
    s_ns = _nosp(s)
    if "억" in s_ns and "만" not in s_ns and n < 10_000:  # "1억"
        return n * 100_000_000
    if "만" in s_ns and n < 1_000_000:  # "300만"
        return n * 10_000
    return n


# ─────────────────────────────────────────────────────────
# 갱신 판정 (요청 반영: 'RT+Drug 합본' 여부와 무관, **개별 담보의 비갱신** 우선)
# ─────────────────────────────────────────────────────────
_RE_NOT_RENEWAL = re.compile(r"(비\s*갱신형|비갱신)", re.I)
_RE_RENEWAL     = re.compile(r"(자동\s*)?갱신", re.I)

def cov_is_nonrenewal(cov: Dict) -> bool:
    """담보 단일 품목이 비갱신인지(강판정)."""
    s = _name_assoc(cov)
    return bool(_RE_NOT_RENEWAL.search(s))

def cov_is_renewal(cov: Dict) -> bool:
    """
    단일 담보 갱신 판정:
      - '비갱신' 토큰 있으면 False(우선)
      - 그 외 '갱신' 토큰 있으면 True
      - 둘 다 없으면 Unknown(False 반환; 상위 엔진에서 보조 로직 병행)
    """
    s = _name_assoc(cov)
    if _RE_NOT_RENEWAL.search(s): return False
    return bool(_RE_RENEWAL.search(s))

def group_has_any_renewal(covs: List[Dict]) -> bool:
    """그룹 내 하나라도 '갱신'이면 True (지표용)."""
    return any(cov_is_renewal(c) for c in (covs or []))

def group_has_any_nonrenewal(covs: List[Dict]) -> bool:
    """그룹 내 하나라도 '비갱신'이면 True → 부분 갱신 도색 시 **비갱신 가드**에 사용."""
    return any(cov_is_nonrenewal(c) for c in (covs or []))


# ─────────────────────────────────────────────────────────
# 유사암/소액 처리
# ─────────────────────────────────────────────────────────
PSEUDO_TOKENS        = ("유사암","소액암","4대유사","갑상선암","기타피부암","경계성종양","제자리암")
PSEUDO_SET_TOKENS    = ("갑상선암","기타피부암","경계성종양","제자리암")
PSEUDO_DIAG_HINTS    = ("유사암진단","소액암진단","4대유사암진단")
SPEC_PSEUDO_TREAT    = ("특정유사암","유사암특정")
SPEC_PSEUDO_EXCEPT   = ("제외",)

def is_pseudo_set(cov: Dict) -> bool:
    return any(k in _nosp(_nz(cov.get("name",""))) for k in PSEUDO_SET_TOKENS)

def is_pseudo_diag(cov: Dict) -> bool:
    s = _nosp(_name_assoc(cov))
    return ("진단" in s) or any(k in s for k in PSEUDO_DIAG_HINTS)

def drop_pseudo_small(cov: Dict, limit: Optional[int] = None) -> bool:
    """
    특정유사암/유사암특정 '치료'의 소액 컷(≤limit) 라인 드롭.
    단, '제외' 토큰 있으면 보존.
    """
    s = _nosp(_name_assoc(cov))
    if any(tok in s for tok in SPEC_PSEUDO_EXCEPT):
        return False
    if not any(k in s for k in SPEC_PSEUDO_TREAT):
        return False
    amt = normalize_amount_to_int(cov.get("amount"))
    _limit = int(limit if limit is not None else get_policy("drop_pseudo_small_under", 2_000_000))
    return amt <= _limit


# ─────────────────────────────────────────────────────────
# RT(방사선) / DRUG(약물) 버킷 + 레이블
# ─────────────────────────────────────────────────────────
RT_TOKENS_CI = ("중입자","탄소이온","carbon")
RT_TOKENS_PR = ("양성자","proton")
RT_TOKENS_IM = ("세기조절","imrt","IMRT","강도변조")
RT_TOKENS_RT = ("방사선","방사선치료","항암방사선")

def _has_any(s: str, keys) -> bool:
    t = _nosp(s).lower()
    return any(_nosp(k).lower() in t for k in keys)

def rt_bucket(cov: Dict) -> Optional[str]:
    s = _name_assoc(cov)
    if _has_any(s, RT_TOKENS_CI): return "CI"  # 중입자(탄소이온)
    if _has_any(s, RT_TOKENS_PR): return "PR"  # 양성자
    if _has_any(s, RT_TOKENS_IM): return "IM"  # 세기조절(IMRT)
    if _has_any(s, RT_TOKENS_RT): return "RT"  # 일반 방사선
    return None

def label_for_rt_bucket(code: str) -> str:
    return {"CI":"중입자", "PR":"양성자", "IM":"세기조절", "RT":"방사선"}.get(code, "방사선")

DRUG_TOKENS_TG   = ("표적","표적항암약물","표적항암약물허가치료")
DRUG_TOKENS_HG   = ("고액항암약물","고액항암약물허가치료","신정원")
DRUG_TOKENS_CT   = ("카티","CAR-T","car-t","CART","cart")
DRUG_TOKENS_GN   = ("항암약물","항암약물치료")
DRUG_TOKENS_HORM = ("호르몬","항호르몬","내분비")

def drug_bucket(cov: Dict) -> Optional[str]:
    s = _name_assoc(cov)
    # 카티 우선(가려짐 방지)
    if _has_any(s, DRUG_TOKENS_CT):   return "CT"  # CAR-T
    if _has_any(s, DRUG_TOKENS_TG):   return "TG"  # 표적
    if _has_any(s, DRUG_TOKENS_HG):   return "HG"  # 고액약물/신정원
    if _has_any(s, DRUG_TOKENS_GN):   return "GN"  # 일반 항암약물
    if _has_any(s, DRUG_TOKENS_HORM): return "HM"  # 호르몬
    return None

def label_for_drug_bucket(code: str) -> str:
    return {"CT":"카티", "TG":"표적", "HG":"고액약물", "GN":"약물", "HM":"호르몬"}.get(code, "약물")


# ─────────────────────────────────────────────────────────
# RT+DRUG 합본 판정
# ─────────────────────────────────────────────────────────
COMBO_HINTS = (
    "방사선약물","항암방사선약물",
    "방사선·약물","약물·방사선",
    "방사선.약물","항암방사선.약물치료비",
    "방사선+약물","약물+방사선",
)

def is_rt_drug_combined(name: str, assoc: str) -> bool:
    """이름/협회 한쪽 또는 둘 다에 RT+Drug 혼합 신호가 있으면 True."""
    s = _nosp(_nz(name) + _nz(assoc))
    if any(h in s for h in COMBO_HINTS):
        return True
    # 명시 키워드 동시 포함
    has_rt = ("방사선" in s)
    has_dr = ("약물" in s)
    if has_rt and has_dr:
        return True
    # 느슨한 패턴 매칭
    return bool(re.search(r"(방사선)[\s\W_·ㆍ.]*?(약물)|(약물)[\s\W_·ㆍ.]*?(방사선)", s))

def combo_decision(*, name: str, assoc: str,
                   any_rt: bool, any_drug: bool) -> Literal["combo","split","both"]:
    """
    합본 처리 결정:
      - combo_or_match=True면 이름/협회 중 한 쪽만 합본 힌트여도 합본 허용
      - combo_mode: both|prefer_combo|prefer_split
    """
    mode  = get_policy("combo_mode", "both")
    allow_or = bool(get_policy("combo_or_match", True))
    hinted = is_rt_drug_combined(name, assoc)
    if allow_or:
        hinted = hinted or (any_rt and any_drug)
    if not hinted:
        return "split"

    if mode == "prefer_combo":
        return "combo"
    if mode == "prefer_split":
        return "split"
    return "both"  # 기본


# ─────────────────────────────────────────────────────────
# 통합세트 / 협회 진단
# ─────────────────────────────────────────────────────────
INTEG_C_NAME = re.compile(r"(통합형?\s*일반암\s*진단비|통합\s*암\s*진단비|통합암진단비)", re.I)
INTEG_M_NAME = re.compile(r"(통합형?\s*전이암\s*진단비|통합\s*전이암\s*진단비|통합전이암진단비)", re.I)
INTEG_C_MAIN = re.compile(r"암\s*진단(\(유병자\))?$", re.I)
INTEG_M_MAIN = re.compile(r"전이암\s*진단", re.I)

ASSOC_GENERAL = re.compile(r"^암\s*진단(\(유병자\))?$")
ASSOC_HIGH    = re.compile(r"^고액암\s*진단(\(유병자\))?$")

def is_integ_cancer_by_name(cov: Dict) -> bool:
    return bool(INTEG_C_NAME.search(_nosp(_nz(cov.get("name","")))))

def is_integ_meta_by_name(cov: Dict) -> bool:
    return bool(INTEG_M_NAME.search(_nosp(_nz(cov.get("name","")))))

def assoc_is_general_diag(assoc: str) -> bool:
    return bool(ASSOC_GENERAL.search(_nz(assoc)))

def assoc_is_high_diag(assoc: str) -> bool:
    return bool(ASSOC_HIGH.search(_nz(assoc)))

def integ_main_match(cov: Dict, *, meta: bool) -> bool:
    s = _nz(cov.get("association_name",""))
    if bool((INTEG_M_MAIN if meta else INTEG_C_MAIN).search(s)):
        return True
    # 이름에 '전이암 진단' 변종이 들어오는 엣지
    return meta and bool(INTEG_M_MAIN.search(_nz(cov.get("name",""))))


# ─────────────────────────────────────────────────────────
# 암 주요치료비 그룹/기간
# ─────────────────────────────────────────────────────────
def mt_group(cov: Dict) -> str:
    """
    A: 암통합치료
    B: 하이클래스(이름/협회에 '하이클래스' 포함, 단 RT/Drug 단어 없음)
    C: 비례형(assoc이 비거나 '진단후 N년' 등 기간 토큰)
    D: 고정형(그 외)
    """
    s_all = _nosp(_name_assoc(cov))
    assoc = _nosp(_nz(cov.get("association_name","")))
    if ("통합치료" in s_all) or ("암통합치료" in s_all):
        return "A"
    if ("하이클래스" in s_all) and (("방사선" not in s_all) and ("약물" not in s_all)):
        return "B"
    if (assoc == "" or assoc.lower()=="null") or re.search(r"(진단후)?\s*\d+\s*년", s_all):
        return "C"
    return "D"

def extract_years(cov: Dict) -> Optional[int]:
    s = _nosp(_name_assoc(cov))
    m = re.search(r"(진단후)?\s*(\d+)\s*년", s)
    if m:
        try:
            return int(m.group(2))
        except Exception:
            return None
    return None


# ─────────────────────────────────────────────────────────
# 파생 헬퍼 (표시/정합성)
# ─────────────────────────────────────────────────────────
def is_combo_candidate(cov: Dict) -> bool:
    """한 담보 내에서 RT/Drug 키워드가 모두 감지되는지(합본 후보)."""
    s = _nosp(_name_assoc(cov))
    return ("방사선" in s) and ("약물" in s)

def pretty_rt_label(codes: List[str]) -> str:
    """RT 서브버킷 다수일 때 표시 문자열(최대 4종 고정 순서)."""
    order = ["CI","PR","IM","RT"]
    seen = [c for c in order if c in set(codes or [])]
    return ", ".join(label_for_rt_bucket(c) for c in seen)

def pretty_drug_label(codes: List[str]) -> str:
    """DRUG 서브버킷 다수일 때 표시 문자열(우선순위: TG>HG>GN>CT>HM)."""
    order = ["TG","HG","GN","CT","HM"]
    seen = [c for c in order if c in set(codes or [])]
    return ", ".join(label_for_drug_bucket(c) for c in seen)


# ─────────────────────────────────────────────────────────
# 모듈 로드 TRACE
# ─────────────────────────────────────────────────────────
_trace("LOAD",
       f"combo_mode={get_policy('combo_mode')}, combo_or={get_policy('combo_or_match')}, "
       f"pseudo_cut={get_policy('drop_pseudo_small_under')}")
