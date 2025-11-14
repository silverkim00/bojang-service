# -*- coding: utf-8 -*-
from pathlib import Path

# ────────────────── 경로 설정 ──────────────────
BASE_DIR = Path(__file__).resolve().parent
_TEMPLATE_DIR = BASE_DIR / "static" / "templates"

# ✅ 템플릿: A3/A4 동시 지원
TEMPLATE_FILE_A3 = str(_TEMPLATE_DIR / "base_template.xlsx")      # A3 인쇄용
TEMPLATE_FILE_A4 = str(_TEMPLATE_DIR / "base_template2.xlsx")     # A4 인쇄용
TEMPLATE_FILES = {  # analyze(template_size=…)에서 사용
    "a3": TEMPLATE_FILE_A3,
    "a4": TEMPLATE_FILE_A4,
}
# 하위 호환(기본값 A4)
TEMPLATE_FILE = TEMPLATE_FILE_A4

# ────────────────── 공용 설정(호환 유지) ──────────────────
INPUT_DIR = "."
OUTPUT_DIR = "output_results"
LOG_DIR = "logs"
LOG_FILE_PATH = "debug.log"
UNMAPPED_LOG_FILE = "unmapped_log.txt"
EXCLUDED_LOG_FILE = "excluded_log.txt"

# ────────────────── 파서 튜닝 ──────────────────
FUZZY_MATCH_THRESHOLD = 88

# ────────────────── 제외 키워드(현행 유지) ──────────────────
EXCLUSION_KEYWORDS = [
    "상급병실료차액", "기타수술", "총합", "합계금액", "page", "p.", "페이지", "유의사항", "보험약관",
    "면허정지위로금", "면허취소위로금", "이륜", "주계약", "無상해", "(2,3인실)", "중대골절",
    "중대화상", "중대한", "無리빙케어", "無삼성리빙케어1.4", "보너스",
    "보복운전피해위로금", "보복운전", "기타", "5대장기이식수술비", "5대골절진단비", "5대골절수술비",
    "중증화상", "5대골절", "3대시각질환수술비", "교통사고 처리지원금(6주미만)", "6주미만", "교통상해사망",
]

# ────────────────── 엑셀 행 맵(요양급여 신설 + 하위 +1) ──────────────────
HARDCODED_ROW_MAP = {
    # 상단 요약
    "회사명": 4, "상품명": 5, "가입일": 6, "만기": 7, "납입기간": 8, "월 보험료": 9, "납입횟수": 10,
    "납입한 보험료": 11, "예상납입 보험료": 12, "총 보험료": 13, "기타": 14, "주요 담보": 15,

    # 담보 영역
    "질병사망": 16, "질병후유장해": 17, "상해사망": 18, "상해후유장해": 19,
    "일반암/고액암 진단비": 20, "유사암": 21, "암주요치료비": 22, "전이암": 23,
    "암 수술비": 24, "항암방사선": 25, "약물 치료": 26, "암 입,통원일당": 27,

    "뇌혈관질환진단비": 28, "뇌졸중": 29, "뇌출혈": 30, "심장질환진단비": 31, "급성심근경색": 32,
    "2대주요치료비": 33, "2대수술비": 34,

    "질병,상해 입원일당": 35, "질병,상해 중환자 입원일당": 36,
    "간병인/간호통합": 37, "치매": 38,

    # ★ 신설 행
    "요양급여": 39,

    # ↓ 이하 기존 대비 +1 시프트
    "질병 수술비": 40, "상해 수술비": 41, "질병,상해 종수술비": 42,
    "5대기관수술비": 43, "N대(기타)수술비": 44,
    "교통사고 처리지원금(형사합의금)": 45, "변호사 선임비용(방어비용)": 46,
    "자동차 부상 치료비": 47, "벌금 대인/대물": 48,

    # 실손/비급여(섹션 전체 +1)
    "질병,상해 입원의료비": 49, "질병,상해 통원의료비": 50,
    "도수,체외충격파,증식": 51, "비급여주사료": 52, "비급여영상진단MRI": 53,

    # 골절/화상/기타(하단 +1)
    "골절,화상 진단비": 54, "골절,화상 수술비": 55, "화재벌금": 56,
    "일상생활배상책임": 57, "보존 / 보철": 58,
}

# ────────────────── 동의어/변종 매핑 보정 ──────────────────
HARDCODED_ROW_MAP.setdefault("유사암-갑,기,경,제", HARDCODED_ROW_MAP["유사암"])
HARDCODED_ROW_MAP.setdefault("암 입·통원일당", HARDCODED_ROW_MAP["암 입,통원일당"])
HARDCODED_ROW_MAP.setdefault("암수술비", HARDCODED_ROW_MAP["암 수술비"])
HARDCODED_ROW_MAP.setdefault("허혈성심장질환진단비", HARDCODED_ROW_MAP["심장질환진단비"])
HARDCODED_ROW_MAP.setdefault("N대(기타) 수술비", HARDCODED_ROW_MAP["N대(기타)수술비"])
HARDCODED_ROW_MAP.setdefault("5대 기관수술비",   HARDCODED_ROW_MAP["5대기관수술비"])

# ────────────────── 도메인 특수 키워드(행 상수 의존 제거) ──────────────────
_ROW_2MAJOR = HARDCODED_ROW_MAP["2대수술비"]
for k in ["혈전용해", "혈전용해치료", "혈전용해치료비", "혈전용해 수술비", "혈전 용해", "혈전-용해", "혈전·용해"]:
    HARDCODED_ROW_MAP.setdefault(k, _ROW_2MAJOR)

_ROW_CANCER_SURG = HARDCODED_ROW_MAP["암 수술비"]
for k in ["다빈치", "다빈치 수술비", "다빈치로봇", "다빈치로봇암수술비", "로봇수술", "로봇 수술비"]:
    HARDCODED_ROW_MAP.setdefault(k, _ROW_CANCER_SURG)
