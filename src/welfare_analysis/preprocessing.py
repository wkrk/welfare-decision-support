"""Normalize facility addresses and aggregate into 25 AnSan administrative districts."""
import logging
import re
import numpy as np
import pandas as pd
from .config import (
    ANSAN_DONGS,
    FACILITY_COLS,
    WELFARE_COLS,
    PCA_WELFARE_COLS,
)
LOG = logging.getLogger(__name__)
# Road addresses alone do not always include an administrative dong.
DONG_RE = re.compile(r"(?<![가-힣0-9])([가-힣]+(?:[1-9][0-9]*)?동)(?![가-힣])")


def extract_dong(value: object, valid_names=ANSAN_DONGS) -> str | None:
    """Return a known administrative dong or None; never treat building '101동' as a dong."""
    if pd.isna(value):
        return None
    value = str(value)
    names = set(valid_names)
    # Prefer explicit '(동)' when it names one of the permitted districts.
    for candidate in re.findall(r"\(([^()]*)\)", value):
        if candidate.strip() in names:
            return candidate.strip()
    for candidate in DONG_RE.findall(value):
        if candidate in names:
            return candidate
    return None


def prepare_elder(df: pd.DataFrame) -> pd.DataFrame:
    required = {"행정동", "노인(남)", "노인(여)", "독거노인(남)", "독거노인(여)"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"노인인구 데이터 컬럼 누락: {sorted(missing)}")
    result = df.copy()
    for col in required - {"행정동"}:
        result[col] = pd.to_numeric(result[col], errors="raise")
        if result[col].isna().any() or (result[col] < 0).any():
            raise ValueError(f"음수/결측 인구 데이터: {col}")
    result["행정동"] = result["행정동"].astype(str).str.strip()
    if result["행정동"].duplicated().any():
        raise ValueError("중복된 행정동이 있습니다. 원자료 집계 단위를 확인하세요.")
    result["노인수"] = result["노인(남)"] + result["노인(여)"]
    result["독거노인수"] = result["독거노인(남)"] + result["독거노인(여)"]
    if (result["노인수"] <= 0).any() or (result["독거노인수"] > result["노인수"]).any():
        raise ValueError("노인수는 양수이고 독거노인수는 노인수 이하여야 합니다.")
    result["독거노인비율"] = result["독거노인수"] / result["노인수"] * 100
    return result[["행정동", "노인수", "독거노인수", "독거노인비율"]]


def count_facilities(df, source_column, output_column, districts, *, direct=False):
    if source_column not in df:
        raise ValueError(f"시설 원본 필수 컬럼 누락: {source_column}")
    copied = df.copy()
    valid = set(districts)
    if direct:
        copied["행정동"] = copied[source_column].astype("string").str.strip()
        copied.loc[~copied["행정동"].isin(valid), "행정동"] = pd.NA
    else:
        copied["행정동"] = copied[source_column].apply(lambda v: extract_dong(v, valid))
    dropped = int(copied["행정동"].isna().sum())
    total = len(copied)
    LOG.warning("%s: %s/%s행이 행정동 매핑되지 않아 집계에서 제외됩니다", output_column, dropped, total)
    result = copied.dropna(subset=["행정동"]).groupby("행정동").size().rename(output_column).reset_index()
    return result, {"구분": output_column, "전체행수": total, "미매핑행수": dropped, "매핑률": round((total-dropped)/total, 4) if total else 0.0}


def count_medical_facilities(df, districts):
    """Use both address fields; parenthetical legal-dong matches are *provisional*.

    A legal dong from 상세주소 may cover multiple administrative dongs. The
    provisional result supports diagnostics, not validated policy decisions.
    """
    needed = {"주소", "상세주소"}
    if not needed.issubset(df.columns):
        raise ValueError(f"의료기관 누락 컬럼: {sorted(needed - set(df.columns))}")
    first = df["주소"].apply(lambda x: extract_dong(x, districts))
    second = df["상세주소"].apply(lambda x: extract_dong(x, districts))
    district = first.fillna(second)
    only_detail = first.isna() & second.notna()
    unresolved = district.isna()
    # Legal dongs like 고잔동/사동 may not identify an administrative dong.
    LOG.warning(
        "의료기관: 주소 직접 %d건, 상세주소 기반 잠정 %d건, 미매핑 %d건 (법정동·행정동 일치 검증 필요)",
        int(first.notna().sum()), int(only_detail.sum()), int(unresolved.sum())
    )
    grouped = district.dropna().value_counts().rename_axis("행정동").reset_index(name="의료기관수")
    report = {
        "구분": "의료기관수", "전체행수": len(df), "미매핑행수": int(unresolved.sum()),
        "매핑률": round(float(district.notna().mean()), 4) if len(df) else 0,
        "주소직접매핑": int(first.notna().sum()),
        "상세주소잠정매핑": int(only_detail.sum()),
        "검증상태": "잠정 - 법정동/행정동 검증 필요"
    }
    return grouped, report


def recalculate_facility_metrics(data):
    df = data.copy()

    if (df["노인수"] <= 0).any():
        raise ValueError("노인수가 0 이하인 행정동이 있습니다")

    # 시설별 노인 1,000명당 지표
    for col in FACILITY_COLS:
        df[f"노인천명당_{col}"] = (
            df[col] / df["노인수"] * 1000
        )

    # 기존 시설 합계: 다른 코드 호환성 유지
    df["복지시설합계"] = df[list(WELFARE_COLS)].sum(axis=1)

    df["노인천명당_복지시설합계"] = (
        df["복지시설합계"] / df["노인수"] * 1000
    )

    # 새 PCA 분석용 지표: 의료기관 제외
    df["복지시설합계_의료제외"] = (
        df[list(PCA_WELFARE_COLS)].sum(axis=1)
    )

    df["노인천명당_복지시설_의료제외"] = (
        df["복지시설합계_의료제외"]
        / df["노인수"] * 1000
    )

    return df


def make_district_dataset(tables, boundaries=None, overrides=None, *, return_audits=False):
    """Aggregate all six facility categories through the same auditable mapper."""
    from .mapping import map_facilities
    base = prepare_elder(tables["elder"])
    requested = set(ANSAN_DONGS)
    if set(base["행정동"]) != requested:
        raise ValueError("기준 25개 행정동 불일치")
    specs = [
        ("medical", "의료기관수"), ("senior", "노인복지시설수"),
        ("welfare", "사회복지관수"), ("health", "보건시설수"),
        ("park", "공원수"), ("medicine", "상비약판매업소수"),
    ]
    quality, audits = [], {}
    for source, output_col in specs:
        counts, report, audit = map_facilities(tables[source], output_col,
            ANSAN_DONGS, boundaries=boundaries, overrides=overrides)
        quality.append(report)
        audits[source] = audit
        base = base.merge(counts, how="left", on="행정동", validate="one_to_one")
    base[list(FACILITY_COLS)] = base[list(FACILITY_COLS)].fillna(0).astype(int)
    result = (recalculate_facility_metrics(base), pd.DataFrame(quality))
    return (*result, audits) if return_audits else result
