# -*- coding: utf-8 -*-
from __future__ import annotations
import re
try:
    from thefuzz import process
except Exception:
    process = None

from . import config

# ───────── 유틸
def _nz(s):       return s if isinstance(s, str) else ""
def _nospace(s):  return re.sub(r"\s+", "", _nz(s))

def _clean(s: str) -> str:
    if not isinstance(s, str): return ""
    t = s
    t = (t.replace("Ⅱ","2").replace("Ⅲ","3").replace("Ⅳ","4")
           .replace("Ⅵ","6").replace("Ⅶ","7").replace("Ⅷ","8")
           .replace("III","3").replace("IV","4").replace("VI","6").replace("VII","7").replace("VIII","8")
           .replace("Ⅰ","1").replace("I","1"))
    t = (t.replace("중환자실","중환자실입원일당")
           .replace("입원(중환자실)일당","중환자실입원일당")
           .replace("중환자실(입원)일당","중환자실입원일당"))
    t = (t.replace("입원의료비(입원)","입원의료비")
           .replace("입원의료비(통원)","통원의료비")
           .replace("통원의료비(외래)","통원의료비")
           .replace("의료비(외래)","통원의료비")
           .replace("외래의료비","통원의료비")
           .replace("입원 의료비","입원의료비")
           .replace("입원(의료)비","입원의료비"))

    # 🔧 선행 수식어(간편고지/맞춤간편고지 + 괄호표기) 제거 — 문자열 맨 앞에서만
    t = re.sub(r'^\s*(간편고지|맞춤고지|맞춤간편고지)\s*(?:[\(\[\{][^)\]\}]*[\)\]\}])?\s*', '', t)

    # “제외” 괄호 제거 및 유사/소액 제외 패턴 제거
    t = re.sub(r'[\(\[\{][^)\]\}]*제외[^)\]\}]*[\)\]\}]', '', t)
    t = re.sub(r'(?:\d+\s*대\s*)?(유사암|소액암)\s*제외', '', t)
    t = re.sub(r'\s+',' ', t).strip()
    return t

# 협회 노이즈
_ASSOC_NOISE = tuple(map(lambda x: x.replace(" ",""), [
    "기타수술","기타 수술","기타수슬","기타 인보험(정액)담보","기타인보험(정액)담보"
]))
def _assoc_is_noise(assoc: str) -> bool:
    return any(k in _nospace(assoc) for k in _ASSOC_NOISE)

# 수술 라벨은 여기서 **절대 반환 금지** (rules/surgery.py 위임)
_SURGERY_BLOCK = {
    "질병 수술비","상해 수술비","질병,상해 종수술비",
    "N대(기타)수술비","5대기관수술비","2대수술비",
    "골절,화상 수술비"
}

# 퍼지 백업 후보(진단 계열)
DIAG_KEYS = [k for k,v in config.HARDCODED_ROW_MAP.items()
             if v in [20,21,23,28,29,30,31,32]]

# ───────── 추가 가드(리스크 0 목적)
# 골절/화상 합본/특정상해/중대류 → 반드시 드랍
_EXC_FX_BURN = tuple(map(lambda x: x.replace(" ",""), [
    "5대골절수술비","5대골절진단비","5대골절",
    "특정상해수술","중대골절","중대화상","중증화상","6주미만"
]))
# 운전자/배상·벌금 계열은 여기에서 라벨링 금지(각 전용 엔진 처리)
_DRIVER_BLOCK = tuple(map(lambda x: x.replace(" ",""), [
    "일상생활배상책임","가족생활배상책임","가족일상생활배상책임",
    "화재벌금","벌금","변호사선임","방어비용"
]))

# ───────── 규칙
def _rule(combined_ns: str) -> str | None:
    s  = combined_ns
    sl = s.lower()
    s_ns = _nospace(s)

    # [0] 전역 가드
    # 산정특례 진단 컷(매핑 반환하지 않음 → 상위 exclude 로직이 컷)
    if ("산정특례" in s) and (("진단" in s) or ("진단비" in s)):
        return None
        # ✅ 허혈성 심장질환 진단 (보수적 직접 매핑)
    if re.search(r"허혈성\s*심장\s*질환\s*진단(?:비)?", s):
        return "허혈성심장질환진단비"
    # 운전자/배상·벌금 — 전용 엔진만 처리
    if any(k in s_ns for k in _DRIVER_BLOCK):
        return None
    # 골절·화상 합본/특정상해/중대/기간 조건 — 반드시 드랍
    if any(k in s_ns for k in _EXC_FX_BURN):
        return None

    # [1] 실손 특수 3종
    if ("비급여mri" in sl) or ("mri검사" in sl) or ("mri" in sl): return "비급여영상진단MRI"
    if ("비급여주사" in sl) or ("주사제" in sl):                 return "비급여주사료"
    if ("도수" in sl) or ("체외충격파" in sl) or ("증식치료" in sl): return "도수,체외충격파,증식"

    # [2] 룸등급/특실
    if "특실" in s or "상급병실" in s or re.search(r"(?:^|[^0-9])(1|일)\s*인실", s):
        return "특실/상급병실"

    # [3] 일반 입원일당(암 제외)
    if "중환자실입원일당" in s or ("중환자" in s and "입원일당" in s):
        return "질병,상해 중환자 입원일당"
    if ("입원일당" in s) and ("암" not in s):
        return "질병,상해 입원일당"

    # [4] 골절/화상/깁스 (수술 라벨이더라도 여기서 이름만 반환 → 실제 반환단계에서 BLOCK으로 차단)
    #     깁스 동의어: 석고 포함
    if (("골절" in s and "진단" in s) or ("화상" in s and "진단" in s)):
        return "골절,화상 진단비"
    if (("골절" in s and "수술" in s) or ("화상" in s and "수술" in s) or ("깁스" in s) or ("석고" in s)):
        return "골절,화상 수술비"

    # [5] 암 진단(유사/소액 제외)
    if (("암" in s) and (("진단" in s) or ("진단비" in s))
        and not any(k in s for k in ("유사암","소액암","갑상선암","기타피부암","경계성종양","제자리암"))):
        return "일반암/고액암 진단비"

    # ── 치료 도메인 ───────────────────────────────────────────
    # [6] 합본(방사선·약물) → 약물 치료 선귀속 (항암방사선.약물치료비 포함)
    if re.search(r"(?:항암\s*방사선\s*[·\.\+ ]\s*약물|항암\s*약물\s*[·\.\+ ]\s*방사선|항암방사선\.약물치료비|항암방사선약물치료비|방사선약물)", s, re.I):
        return "약물 치료"

    # [7] CAR-T/카티 → 약물 치료
    if re.search(r"(CAR\s*-\s*T|CAR\s*T|car-?t|CART|카티)", s, re.I):
        return "약물 치료"

    # [8] 방사선 단독
    if re.search(r"(중입자|탄소이온|proton|양성자|imrt|세기조절|강도변조|방사선치료|항암방사선)", s, re.I):
        return "항암방사선"

    # [9] 약물 단독(표적/고액/일반)
    if re.search(r"(표적.*(약물|허가치료)|고액항암약물|고액항암약물허가치료|신정원|항암약물치료|항암약물)", s, re.I):
        return "약물 치료"

    # [10] 암 특정치료 세트
    if any(k in s for k in ("암통합치료","암중점치료","암특정치료","암주요치료","암특정치료지원","종합병원암특정치료","종합병원암특정치료지원","암특정치료지원금")):
        return "암주요치료비"

    # [11] 수술 키워드 있어도 여기선 확정 금지(위임)
    if "수술" in s:
        return None

    return None

def _fuzzy_backup(name_c: str) -> str | None:
    if not process: return None
    if ("진단" in name_c) or any(k in name_c for k in ("뇌혈관","뇌졸중","뇌출혈","허혈성","심근경색","전이암")):
        key, score = process.extractOne(name_c, DIAG_KEYS)
        if score and score >= 85:
            return key
    return None

# ───────── 엔트리
def find_target_row(name, association_name=None):
    nm  = _clean(_nz(name))
    ac  = _clean(_nz(association_name))
    combined = _nospace(f"{ac}|{nm}") if (ac and not _assoc_is_noise(ac)) else _nospace(nm)

    # 실손 특수 3종 조기 매칭(수술 아님) — 라벨 키는 그대로 유지
    cl = combined.lower()
    if ("비급여mri" in cl) or ("mri검사" in cl) or ("mri" in cl): return "비급여영상진단MRI"
    if ("비급여주사" in cl) or ("주사제" in cl):                return "비급여주사료"
    if ("도수" in cl) or ("체외충격파" in cl) or ("증식치료" in cl): return "도수,체외충격파,증식"

    # 1차 규칙
    r = _rule(combined)
    if r and r not in _SURGERY_BLOCK:
        return r

    # 퍼지 백업(진단만)
    return _fuzzy_backup(nm)
