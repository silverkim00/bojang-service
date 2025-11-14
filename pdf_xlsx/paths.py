# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

def _detect_base_dir() -> Path:
    """
    패키지 기준 프로젝트 루트 추정:
      - APP_ROOT 환경변수가 있으면 우선 사용
      - 그 외엔 pdf_xlsx/ 의 상위(= new3/)를 루트로 사용
    """
    env = os.getenv("APP_ROOT")
    if env:
        return Path(env).resolve()
    # 현재 파일: <...>/pdf_xlsx/paths.py
    return Path(__file__).resolve().parents[1]

# 프로젝트 루트
BASE_DIR: Path = _detect_base_dir()

def prj(*parts: str | os.PathLike) -> Path:
    """
    프로젝트 루트 기준 경로 조합
    ex) prj('data','inputs','a.pdf') -> <BASE_DIR>/data/inputs/a.pdf
    """
    return BASE_DIR.joinpath(*map(str, parts))

def here(*parts: str | os.PathLike) -> Path:
    """
    pdf_xlsx 폴더 기준 경로 조합
    ex) here('templates','base.xlsx') -> <BASE_DIR>/pdf_xlsx/templates/base.xlsx
    """
    return Path(__file__).resolve().parent.joinpath(*map(str, parts))

def ensure_dir(p: Path) -> Path:
    """
    파일 경로 p의 상위 디렉터리를 생성(존재해도 OK)하고 p를 그대로 반환.
    쓰기 전 안전하게 호출.
    """
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
