"""Load AnSan boundaries using code + name, never name alone (names repeat nationally)."""
from .config import ANSAN_DONGS

def select_ansan_boundaries(gdf):
    required = {"ADM_CD", "ADM_NM", "geometry"}
    if not required.issubset(gdf.columns):
        raise ValueError(f"경계 데이터 필수 컬럼 누락: {sorted(required - set(gdf.columns))}")
    filtered = gdf.loc[
        gdf["ADM_CD"].astype(str).str.startswith("3109") & gdf["ADM_NM"].isin(ANSAN_DONGS)
    ].copy()
    if len(filtered) != 25 or filtered["ADM_NM"].duplicated().any() or set(filtered["ADM_NM"]) != set(ANSAN_DONGS):
        raise ValueError("안산시 경계 25개 검증 실패: 행정코드/기준일/경계파일을 확인하세요")
    if filtered.crs is None:
        raise ValueError("경계파일 좌표계(CRS) 정보가 없습니다")
    return filtered.to_crs(epsg=4326)

def merge_boundaries(districts, boundaries):
    result = boundaries.merge(districts, left_on="ADM_NM", right_on="행정동", how="left", validate="one_to_one", indicator=True)
    if not (result["_merge"] == "both").all():
        raise ValueError("행정동과 지도 경계가 완전히 결합되지 않았습니다")
    return result.drop(columns="_merge")
