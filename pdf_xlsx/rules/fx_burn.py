# rules/fx_burn.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, List, Optional

from ..import config
from ..utils import _nz, _nosp, parse_amount, format_amount_short

# ────────────────────────── 유틸
def _name(c: Dict) -> str:  return _nz(c.get("name", ""))
def _assoc(c: Dict) -> str: return _nz(c.get("association_name", ""))
def _na(c: Dict) -> str:    return _nosp(_name(c) + "|" + _assoc(c))

def _amt_list(items: List[Dict]) -> List[int]:
    out = []
    for it in items or []:
        try:
            v = int(parse_amount(it.get("amount", "0")))
        except Exception:
            v = 0
        if v > 0:
            out.append(v)
    return out

def _max_amt(items: List[Dict]) -> int:
    vs = _amt_list(items)
    return max(vs) if vs else 0

def _has_any(s: str, keys) -> bool:
    s = _nosp(s)
    return any(k in s for k in keys)

# ────────────────────────── 상수 라벨(템플릿 존재 여부 고려)
LBL_FX_DIAG = "골절,화상 진단비"
LBL_FX_SURG = "골절,화상 수술비"
LBL_LIAB_1  = "일상생활배상책임"
LBL_LIAB_2  = "가족생활배상책임"
LBL_LIAB_3  = "자녀일상생활배상책임"
LBL_FFINE   = "화재벌금"


# 5대골절/중대화상 등 “버려야 할” 키워드(진단/수술 공통 가드)
_EXC_TOKENS_LOCAL = (
    "5대골절", "5대골절진단", "5대골절수술",
    "중대화상", "중증화상", "중대한화상",
)
# config 측 전역 EXCLUSION_KEYWORDS도 함께 고려
_EXC_FROM_CONFIG = tuple((getattr(config, "EXCLUSION_KEYWORDS", []) or []))

def _is_excluded_fxbrn(text: str) -> bool:
    s = _nosp(text or "")
    if any(k in s for k in _EXC_TOKENS_LOCAL):
        return True
    if any(k.replace(" ", "") in s for k in _EXC_FROM_CONFIG):
        return True
    return False

# ────────────────────────── 집계 (외부 호출 전용)
def aggregate(bucket: Dict[str, List[Dict]], out: Dict[str, str]) -> None:
    """
    전용 처리:
      1) 골절·화상 '진단비' 병기 — 서로 합본하지 않음(각 카테고리 독립 표시)
         · 같은 카테고리 내 중복 항목은 '최대값'으로 대표
         · 5대골절/중대화상 등은 제외(로컬 가드 + config EXCLUSION_KEYWORDS)
         · 출력형: out["골절,화상 진단비"] = "골절 30만, 화상 10만"
      2) (참고) 골절·화상 '수술비'는 기존 rules/surgery.py에서 처리하지만,
         혹여 이 버킷으로 흘러온 경우에도 동일 방식으로 병기해 안전장치 제공.
         · 출력형: out["골절,화상 수술비"] = "골절 300만, 화상 150만, 깁스 20만"
      3) 생활배상(일상/가족) → 단일 행으로 병기
         · 두 버킷의 최대 금액을 취해 하나로 묶어 표기
         · 템플릿에 존재하는 쪽 라벨로 기록, 값은 "가배책 1억" 형태
      4) 화재벌금 → 최대값 1줄
    """
    # ── 1) 골절·화상 '진단비' 병기 ─────────────────────────
    if LBL_FX_DIAG in bucket:
        items = bucket.get(LBL_FX_DIAG, []) or []

        fx_vals, br_vals = [], []
        for c in items:
            t = _na(c)
            if _is_excluded_fxbrn(t):
                continue
            if "진단" not in t and "진단비" not in t:
                # 혹시 진단 버킷에 수술 텍스트가 섞여 들어오면 무시
                continue

            v = _max_amt([c])
            if v <= 0:
                continue

            is_fx = "골절" in t
            is_br = "화상" in t

            # '골절,화상' 등의 합본 텍스트는 각 도메인에 동일 금액을 반영(병기 원칙)
            if is_fx:
                fx_vals.append(v)
            if is_br:
                br_vals.append(v)

        parts = []
        if fx_vals:
            parts.append(f"골절 {format_amount_short(max(fx_vals))}")
        if br_vals:
            parts.append(f"화상 {format_amount_short(max(br_vals))}")
        if parts:
            out[LBL_FX_DIAG] = ", ".join(parts)

    # ── 2) 골절·화상·깁스 '수술비' 안전 병기(보조) ────────────────
    # 원칙상 rules/surgery.py에서 처리하지만, 일부 파이프라인 변동 시 안전 그물망 제공
    if LBL_FX_SURG in bucket and LBL_FX_SURG not in out:
        items = bucket.get(LBL_FX_SURG, []) or []

        fx, br, gp = [], [], []
        for c in items:
            t = _na(c)
            if _is_excluded_fxbrn(t):
                continue
            v = _max_amt([c])
            if v <= 0:
                continue

            if ("수술" in t and "골절" in t):
                fx.append(v)
            if ("수술" in t and "화상" in t):
                br.append(v)
            if "깁스" in t:
                gp.append(v)

        parts = []
        if fx:
            parts.append(f"골절 {format_amount_short(max(fx))}")
        if br:
            parts.append(f"화상 {format_amount_short(max(br))}")
        if gp:
            parts.append(f"깁스 {format_amount_short(max(gp))}")
        if parts:
            out[LBL_FX_SURG] = ", ".join(parts)

    # ── 3) 생활배상(일상/가족/자녀) 병기 ─────────────────────────────
    row_map = getattr(config, "HARDCODED_ROW_MAP", {}) or {}

    # 버킷별 최대 금액
    v_personal = _max_amt(bucket.get(LBL_LIAB_1, [])) if LBL_LIAB_1 in bucket else 0  # 일상
    v_family   = _max_amt(bucket.get(LBL_LIAB_2, [])) if LBL_LIAB_2 in bucket else 0  # 가족
    v_child    = _max_amt(bucket.get(LBL_LIAB_3, [])) if LBL_LIAB_3 in bucket else 0  # 자녀

    has_row_personal = LBL_LIAB_1 in row_map
    has_row_family   = LBL_LIAB_2 in row_map
    has_row_child    = LBL_LIAB_3 in row_map

    # 자녀 배상(자배책) 먼저 처리
    if v_child > 0:
        # 자녀 전용 행이 있으면 거기에, 없으면 일상/가족 중 존재하는 곳에 태운다
        if has_row_child:
            target_child = LBL_LIAB_3
        elif has_row_personal:
            target_child = LBL_LIAB_1
        elif has_row_family:
            target_child = LBL_LIAB_2
        else:
            target_child = None

        if target_child:
            prev = _nz(out.get(target_child, "")).strip()
            piece = f"자배책 {format_amount_short(v_child)}"
            out[target_child] = f"{prev}, {piece}" if prev else piece

    # 일배/가배 처리
    # ① 일상/가족 두 행이 모두 있는 템플릿이면 각 행에 따로
    if has_row_personal and has_row_family:
        if v_personal > 0:
            out[LBL_LIAB_1] = f"일배책 {format_amount_short(v_personal)}"
        if v_family > 0:
            out[LBL_LIAB_2] = f"가배책 {format_amount_short(v_family)}"
    else:
        # ② 행이 1개만 있을 때 → 그 한 줄에 합쳐서 찍기
        target = None
        if has_row_personal:
            target = LBL_LIAB_1
        elif has_row_family:
            target = LBL_LIAB_2

        if target and (v_personal > 0 or v_family > 0):
            parts = []
            if v_personal > 0:
                parts.append(f"일배책 {format_amount_short(v_personal)}")
            if v_family > 0:
                parts.append(f"가배책 {format_amount_short(v_family)}")

            prev = _nz(out.get(target, "")).strip()
            txt = ", ".join(parts)
            out[target] = f"{prev}, {txt}" if prev else txt



    # ── 4) 화재벌금 ────────────────────────────────────────────────
    if LBL_FFINE in bucket:
        v = _max_amt(bucket.get(LBL_FFINE, []))
        if v:
            out[LBL_FFINE] = f"화재벌금 {format_amount_short(v)}"
