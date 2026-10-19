"""Auditable facility-to-administrative-dong mapping, with no network/API calls.

Mapping precedence: explicit administrative-dong field, coordinates within
verified administrative boundaries, validated manual overrides, address hints.
Address hints are provisional; they should not be interpreted as verified.
"""
from __future__ import annotations
import logging
from pathlib import Path
import pandas as pd
from .preprocessing import extract_dong

LOG = logging.getLogger(__name__)
ADMIN_FIELDS = ("행정동", "행정읍면동", "행정동명", "관할행정동", "행정구역명")
ADDRESS_FIELDS = ("소재지도로명주소", "소재지지번주소", "도로명주소", "지번주소", "주소", "상세주소", "소재지주소", "소재지", "위치")
LAT_FIELDS = ("위도", "latitude", "lat", "Latitude", "LAT")
LON_FIELDS = ("경도", "longitude", "lon", "lng", "Longitude", "LON")


def _first(fields, columns):
    return next((f for f in fields if f in columns), None)


def map_facilities(df: pd.DataFrame, category: str, districts, boundaries=None, overrides=None):
    """Return (verified/provisional counts, quality report, row-level audit).

    `overrides`: DataFrame with ['구분', '원본행번호', '확인행정동']; ONLY for human-verified entries.
    """
    valid = set(districts)
    audit = df.reset_index(drop=True).copy()
    audit.insert(0, "원본행번호", range(1, len(audit) + 1))
    audit.insert(0, "구분", category)
    audit["매핑행정동"] = pd.NA
    audit["매핑방법"] = "미매핑"
    audit["검증상태"] = "미확인"

    # Priority 1: spatial join with verified administrative-dong boundaries.
    # This supersedes a possibly stale or legal-dong label in input columns.
    lat_col, lon_col = _first(LAT_FIELDS, audit.columns), _first(LON_FIELDS, audit.columns)
    if boundaries is not None and lat_col and lon_col:
        import geopandas as gpd
        lat = pd.to_numeric(audit[lat_col], errors="coerce")
        lon = pd.to_numeric(audit[lon_col], errors="coerce")
        eligible = lat.between(33, 39) & lon.between(124, 132)
        if eligible.any():
            points = gpd.GeoDataFrame(
                {"원본행번호": audit.loc[eligible, "원본행번호"]},
                geometry=gpd.points_from_xy(lon[eligible], lat[eligible]), crs="EPSG:4326")
            result = gpd.sjoin(points, boundaries[["ADM_NM", "geometry"]].to_crs(4326),
                               how="left", predicate="intersects")
            # A point on two boundaries is ambiguous: don't silently double-count.
            matched = result.dropna(subset=["ADM_NM"])
            if matched["원본행번호"].duplicated().any():
                raise ValueError("좌표가 둘 이상의 행정동 경계와 겹칩니다. 경계 중첩을 검토하세요")
            matches = matched.set_index("원본행번호")["ADM_NM"]
            ix = matches.index.to_numpy() - 1
            audit.loc[ix, "매핑행정동"] = matches.to_numpy()
            audit.loc[ix, "매핑방법"] = "좌표-행정동공간조인"
            audit.loc[ix, "검증상태"] = "좌표 기반"

    # Priority 2: explicit administrative-dong field where spatial mapping failed.
    # Keep it separate from spatial mapping for transparent coverage reporting.
    admin_col = _first(ADMIN_FIELDS, audit.columns)
    if admin_col:
        names = audit[admin_col].astype("string").str.strip()
        spatial = audit["매핑방법"].eq("좌표-행정동공간조인")
        discrepancy = spatial & names.isin(valid) & names.ne(audit["매핑행정동"])
        audit["행정동컬럼_좌표불일치"] = discrepancy.fillna(False)
        good = audit["매핑행정동"].isna() & names.isin(valid)
        audit.loc[good, "매핑행정동"] = names[good]
        audit.loc[good, "매핑방법"] = f"행정동컬럼:{admin_col}"
        audit.loc[good, "검증상태"] = "행정동명 확인(좌표 미검증)"

    # When supplied geocoded datasets contain an administrative-dong label but
    # no valid coordinates, keep it as a PROVISIONAL assignment for review.
    if "보조자료_행정동" in audit.columns:
        provided = audit["보조자료_행정동"].astype("string").str.strip()
        pending = audit["매핑행정동"].isna() & provided.isin(valid)
        audit.loc[pending, "매핑행정동"] = provided[pending]
        audit.loc[pending, "매핑방법"] = "제공_보조자료_행정동(좌표없음)"
        audit.loc[pending, "검증상태"] = "잠정(좌표 없는 제공 행정동)"

    # Administrative dong mapping overrides approved by a human reviewer.
    if overrides is not None and len(overrides):
        required = {"구분", "원본행번호", "확인행정동"}
        if not required.issubset(overrides.columns):
            raise ValueError(f"수동매핑 파일 필수 컬럼: {sorted(required)}")
        selected = overrides.loc[overrides["구분"].eq(category)].copy()
        if selected.duplicated("원본행번호").any():
            raise ValueError("수동매핑 동일 원본행번호 중복")
        if not selected["확인행정동"].isin(valid).all():
            raise ValueError("수동매핑에 기준 25개 행정동 외의 값이 있습니다")
        for _, row in selected.iterrows():
            number = int(row["원본행번호"])
            if not 1 <= number <= len(audit):
                raise ValueError("수동매핑 원본행번호 범위를 벗어남")
            ix = number - 1
            audit.loc[ix, "매핑행정동"] = row["확인행정동"]
            audit.loc[ix, "매핑방법"] = "검토완료_수동매핑"
            audit.loc[ix, "검증상태"] = "담당자 확인"

    # Address string: useful for coverage, but legal dongs and administrative dongs
    # differ. A best-effort guess must stay distinctly *provisional*.
    address_cols = [c for c in ADDRESS_FIELDS if c in audit.columns]
    pending = audit.index[audit["매핑행정동"].isna()]
    for col in address_cols:
        if len(pending) == 0:
            break
        extracted = audit.loc[pending, col].apply(lambda v: extract_dong(v, valid))
        accepted = extracted.dropna()
        if len(accepted):
            audit.loc[accepted.index, "매핑행정동"] = accepted
            audit.loc[accepted.index, "매핑방법"] = f"주소추출:{col}"
            audit.loc[accepted.index, "검증상태"] = "잠정(법정동·행정동 확인 필요)"
            pending = audit.index[audit["매핑행정동"].isna()]

    audit["집계반영"] = audit["매핑행정동"].notna()
    count = (audit.dropna(subset=["매핑행정동"])
             .groupby("매핑행정동").size().rename(category).reset_index()
             .rename(columns={"매핑행정동": "행정동"}))
    total = len(audit)
    provisional = int(audit["검증상태"].str.startswith("잠정").sum())
    unmatched = int(audit["매핑행정동"].isna().sum())
    verified = total - unmatched - provisional
    report = {
        "구분": category, "전체행수":total, "확인매핑행수":verified,
        "잠정매핑행수":provisional, "미매핑행수":unmatched,
        "매핑률":round((total-unmatched)/total,4) if total else 0.,
        "확인매핑률":round(verified/total,4) if total else 0.,
        "공간조인매핑행수":int(audit["매핑방법"].eq("좌표-행정동공간조인").sum()),
        "주소잠정매핑행수":int(audit["매핑방법"].str.startswith("주소추출:").sum()),
        "보조자료잠정매핑행수":int(audit["매핑방법"].eq("제공_보조자료_행정동(좌표없음)").sum()),
        "검증상태":"잠정매핑 포함 - 정책판단 전 확인 필요" if provisional else "확인된 매핑만 포함",
    }
    LOG.warning("%s: 확인 %d, 잠정 %d, 미매핑 %d / 전체 %d", category, verified, provisional, unmatched, total)
    return count, report, audit


def write_audits(audits: dict, output_dir):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    full = pd.concat(audits.values(), ignore_index=True)
    # These audits may include contact fields from original sources; local output only.
    full.to_csv(out / "mapping_audit_private.csv", index=False, encoding="utf-8-sig")
    full.loc[full["검증상태"] == "미확인"].to_csv(
        out / "unmapped_facilities_private.csv", index=False, encoding="utf-8-sig")
    full.loc[full["검증상태"].str.startswith("잠정")].to_csv(
        out / "provisional_facilities_private.csv", index=False, encoding="utf-8-sig")
