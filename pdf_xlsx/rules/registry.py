# rules/registry.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Optional
from .. import config

# ─────────────────────────────────────────────────────────────
# 작은 유틸
# ─────────────────────────────────────────────────────────────
def _nz(s):
    return s if isinstance(s, str) else ""

def _nosp(s):
    import re as _re
    return _re.sub(r"\s+", "", _nz(s))

def _has_any(s: str, keys) -> bool:
    s = _nosp(s)
    return any(k.replace(" ", "") in s for k in keys)

def _exists_label(label: str) -> bool:
    try:
        return label in config.HARDCODED_ROW_MAP
    except Exception:
        return False

def _pick(*cands: str) -> Optional[str]:
    for c in cands:
        if _exists_label(c):
            return c
    return None

# ─────────────────────────────────────────────────────────────
# 표준 라벨 (config.HARDCODED_ROW_MAP 기반)
# ─────────────────────────────────────────────────────────────
# 사망/후유
LBL_DEATH_D   = _pick("질병사망")
LBL_DEATH_I   = _pick("상해사망")
LBL_IMPAIR_D  = _pick("질병후유장해")
LBL_IMPAIR_I  = _pick("상해후유장해")  # 재해후유장해 포함

# 실손
LBL_SIL_INP   = _pick("질병,상해 입원의료비")
LBL_SIL_OUT   = _pick("질병,상해 통원의료비")
LBL_SIL_M1    = _pick("도수,체외충격파,증식")
LBL_SIL_M2    = _pick("비급여주사료")
LBL_SIL_M3    = _pick("비급여영상진단MRI")

# 일반 수술/종수술
LBL_GEN_SURG_D = _pick("질병 수술비")
LBL_GEN_SURG_I = _pick("상해 수술비")
LBL_GEN_5      = _pick("질병,상해 종수술비")

# 치과/골절·화상
LBL_TOOTH     = _pick("보존 / 보철")
LBL_FX_DIAG   = _pick("골절,화상 진단비")
LBL_FX_SURG   = _pick("골절,화상 수술비")

# 배상/벌금(표준 라벨)
LBL_LIAB_D = _pick("일상생활배상책임")
LBL_LIAB_F = _pick("가족생활배상책임")
LBL_FFINE  = _pick("화재벌금")
LBL_FINE   = _pick("벌금 대인/대물")
LBL_LAW    = _pick("변호사 선임비용(방어비용)")
LBL_AID    = _pick("교통사고 처리지원금(형사합의금)")
LBL_INJ    = _pick("자동차 부상 치료비")

# 뇌/심 진단 3종 (우선 규칙용 라벨)
LBL_CEREBRO  = _pick("뇌혈관질환진단비")          # 28행
LBL_MI       = _pick("급성심근경색")              # 32행
LBL_ISCHEMIC = _pick("허혈성심장질환진단비")      # 31행 (config에서 alias 보강)

# ─────────────────────────────────────────────────────────────
# 정규식
# ─────────────────────────────────────────────────────────────
# 교통상해사망(표기 변형 포함) → 전면 제외 트리거
TRAFFIC_DEATH_RX = re.compile(r"교\s*통\s*(?:상해\s*)?사망")

RX = {
    # 사망/후유
    "death_d": re.compile(r"(질병\s*사망|질병사망)"),
    "death_i": re.compile(r"(상해\s*사망|상해사망|재해사망)"),
    "imp_d":   re.compile(r"질병.{0,12}?후유장해"),
    "imp_i":   re.compile(r"(?:(?:상해|재해)).{0,12}?후유장해"),

    # 후유장해 임계어 (렌더는 원문 유지, 제외 판단 힌트용)
    "imp_gte3":  re.compile(r"3\s*%\s*(?:이상|↑|\+)"),
    "imp_lte80": re.compile(r"80\s*%\s*(?:이하|↓)"),
    "imp_range": re.compile(r"3\s*~\s*100\s*%"),

    # 실손
    "sil_in":  re.compile(r"(입원\s*의료비|입원의료비|입원비\(실손\))"),
    "sil_out": re.compile(r"(통원\s*의료비|통원의료비|외래|처방|조제)"),
    "sil_m1":  re.compile(r"(도수|체외충격파|증식치료)"),
    "sil_m2":  re.compile(r"(비급여\s*주사|주사제)"),
    "sil_m3":  re.compile(r"(비급여\s*mri|mri검사|mri)", re.I),

    # 일반 수술/종수술
    "surg_i":  re.compile(r"(상해\s*수술|재해\s*수술)"),
    "surg_d":  re.compile(r"(질병\s*수술)"),
    "surg_5":  re.compile(r"(종\s*수술|5\s*종\s*수술)"),

    # 골절/화상 (진단/수술) + 깁스(치료)
    "fx_diag": re.compile(
        r"(골절\s*진단|화상\s*진단|"
        r"골절[,·]?\s*화상\s*진단|골절화상\s*진단|"
        r"골절[,·]?\s*화상\s*진단비|골절진단비|화상진단비)"
    ),
    "fx_surg": re.compile(
        r"(골절\s*수술|화상\s*수술|골절[,·]?\s*화상\s*수술|골절화상\s*수술|깁스|석고)"
    ),

    # 치과
    "tooth": re.compile(r"(보존|보철)"),

    # 배상/벌금(라벨 라우팅용)
    "liab": re.compile(r"(일상생활배상책임|가족생활배상책임|일배|가배책)", re.I),
    "ff":   re.compile(r"(화재\s*벌금)", re.I),
    "fine": re.compile(r"(벌금)", re.I),
    "law":  re.compile(r"(변호사\s*선임|방어비용)", re.I),
    "aid":  re.compile(r"(교통사고처리|형사합의)", re.I),
    "inj":  re.compile(r"(자동차사고부상|자동차부상)", re.I),

    # 뇌/심 진단 3종 (우선 규칙)
    "cerebro":  re.compile(r"(뇌혈관\s*질환\s*진단(?:비)?|뇌혈관\s*진단(?:비)?)"),
    "mi":       re.compile(r"(급성\s*심근경색(?:증)?\s*진단(?:비)?)"),
    "ischemic": re.compile(r"(허혈성\s*심장\s*질환\s*진단(?:비)?)"),
}

# ─────────────────────────────────────────────────────────────
# 도메인 정규화
# ─────────────────────────────────────────────────────────────
def _normalize_injury_words(na: str) -> str:
    """재해 → 상해 치환(상해계 규칙 공통)"""
    return na.replace("재해", "상해")

# ─────────────────────────────────────────────────────────────
# 라벨 찾기
# ─────────────────────────────────────────────────────────────
def find_label(name: str, assoc: str) -> Optional[str]:
    na = _normalize_injury_words(_nosp(_nz(name) + "|" + _nz(assoc)))

    # 사망/후유
    if LBL_DEATH_I and RX["death_i"].search(na):  return LBL_DEATH_I
    if LBL_DEATH_D and RX["death_d"].search(na):  return LBL_DEATH_D
    if LBL_IMPAIR_I and RX["imp_i"].search(na):   return LBL_IMPAIR_I
    if LBL_IMPAIR_D and RX["imp_d"].search(na):   return LBL_IMPAIR_D

    # 뇌/심 진단 3종 — 우선 고정 매핑
    if LBL_CEREBRO and RX["cerebro"].search(na):   return LBL_CEREBRO
    if LBL_MI and RX["mi"].search(na):             return LBL_MI
    if LBL_ISCHEMIC and RX["ischemic"].search(na): return LBL_ISCHEMIC

    # 실손
    if LBL_SIL_INP and RX["sil_in"].search(na):   return LBL_SIL_INP
    if LBL_SIL_OUT and RX["sil_out"].search(na):  return LBL_SIL_OUT
    if LBL_SIL_M1 and RX["sil_m1"].search(na):    return LBL_SIL_M1
    if LBL_SIL_M2 and RX["sil_m2"].search(na):    return LBL_SIL_M2
    if LBL_SIL_M3 and RX["sil_m3"].search(na):    return LBL_SIL_M3

    # 일반 수술/종수술
    if LBL_GEN_SURG_I and RX["surg_i"].search(na): return LBL_GEN_SURG_I
    if LBL_GEN_SURG_D and RX["surg_d"].search(na): return LBL_GEN_SURG_D
    if LBL_GEN_5 and RX["surg_5"].search(na):      return LBL_GEN_5

    # 골절/화상/치과
    if LBL_FX_DIAG and RX["fx_diag"].search(na):   return LBL_FX_DIAG
    if LBL_FX_SURG and RX["fx_surg"].search(na):   return LBL_FX_SURG
    if LBL_TOOTH and RX["tooth"].search(na):       return LBL_TOOTH

    # 배상/벌금(라벨 라우팅; 집계는 각 전담 모듈에서 처리)
    if LBL_LIAB_D and RX["liab"].search(na):
        return LBL_LIAB_D
    if LBL_LIAB_F and ("가족생활배상책임" in na):
        return LBL_LIAB_F
    if LBL_FFINE and RX["ff"].search(na):
        return LBL_FFINE
    if LBL_FINE and RX["fine"].search(na) and not RX["ff"].search(na):
        return LBL_FINE
    if LBL_LAW and RX["law"].search(na):
        return LBL_LAW
    if LBL_AID and RX["aid"].search(na):
        return LBL_AID
    if LBL_INJ and RX["inj"].search(na):
        return LBL_INJ

    # 협회명 특수키: 유사암 진단
    if "소액암진단(유사암진단)" in _nosp(_nz(assoc)):
        return _pick("유사암")

    return None

# ─────────────────────────────────────────────────────────────
# 제외 규칙
# ─────────────────────────────────────────────────────────────
ALWAYS_EXCLUDE_TOKENS = (
    "5대골절수술비", "5대골절진단비", "5대골절",
    "특정상해수술",
    "중대골절", "중대화상", "중증화상",
    "6주미만",
)

def _should_exclude_fx_burn_always(na: str) -> bool:
    return _has_any(na, ALWAYS_EXCLUDE_TOKENS)

def _config_exclusion_hit(na: str) -> bool:
    try:
        keys = getattr(config, "EXCLUSION_KEYWORDS", []) or []
        return bool(keys) and _has_any(na, keys)
    except Exception:
        return False

# ─────────────────────────────────────────────────────────────
# 화이트리스트 (수술/유사암 예외 통과)
# ─────────────────────────────────────────────────────────────
def is_whitelisted(name: str, assoc: str) -> bool:
    na = _nosp(_nz(name) + "|" + _nz(assoc))

    # 혈전용해 변형 허용
    if any(k in na for k in ("혈전용해", "혈전용해치료", "혈전용해치료비", "혈전용해수술", "혈전용해수술비", "혈전용해수술료",
                              "혈전 용해", "혈전-용해", "혈전·용해")):
        return True

    # 다빈치/로봇 + 암
    has_robot = any(k in na for k in ("다빈치", "로봇수술", "로봇"))
    has_cancer = ("암" in na) or any(k in na for k in ("갑상선암", "전립선암"))
    if has_robot and has_cancer:
        return True

    # 유사암 진단(지원/면제류는 제외)
    if "소액암진단(유사암진단)" in na:
        if not any(k in na for k in ("보험료납입지원", "납입면제", "지원금")):
            return True
    if ("유사암" in na or "갑상선암" in na or "기타피부암" in na) and ("진단" in na):
        if not any(k in na for k in ("보험료납입지원", "납입면제", "지원금")):
            return True

    return False

# ─────────────────────────────────────────────────────────────
# 제외 판정 본체
# ─────────────────────────────────────────────────────────────
def should_exclude(name: str, assoc: str) -> bool:
    """
    제외 정책(최신):
      A) 교통상해사망: 무조건 제외(최우선, 어떤 화이트리스트보다 우선)
      B) 수술 화이트리스트: 혈전용해/다빈치(암)/유사암 진단은 블랙리스트보다 통과
      C) 로컬 항상 제외 토큰 컷
      D) 전역 EXCLUSION_KEYWORDS 적용
      E) 후유장해는 통과(원문 수식 유지)
      F) 기본 비제외
    """
    raw = _nz(name) + "|" + _nz(assoc)
    na_raw = _nosp(raw)
    na = _normalize_injury_words(na_raw)

    # A) 교통상해사망 전면 제외(최우선)
    if TRAFFIC_DEATH_RX.search(na_raw) or TRAFFIC_DEATH_RX.search(na):
        return True

    # B) 화이트리스트 우선 통과
    if is_whitelisted(name, assoc):
        return False

    # C) 로컬 항상 제외
    if _should_exclude_fx_burn_always(na):
        return True

    # D) 전역 제외 키워드
    if _config_exclusion_hit(na):
        return True

    # E) 후유장해 완화(상해/질병 불문)
    if RX["imp_i"].search(na) or RX["imp_d"].search(na):
        return False

    # F) 기본
    return False
