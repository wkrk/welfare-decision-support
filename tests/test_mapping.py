import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from welfare_analysis.mapping import map_facilities


def test_address_fallback_and_provisional():
    df = pd.DataFrame({"소재지도로명주소": ["경기도 안산시 해양로 12", "경기도 안산시 101동 12"],
                       "소재지지번주소": ["경기도 안산시 사동 100", ""]})
    counts, report, audit = map_facilities(df, "기관수", ["사동"])
    assert report["잠정매핑행수"] == 1
    assert report["미매핑행수"] == 1
    assert counts.loc[0, "기관수"] == 1
    assert "잠정" in audit.loc[0, "검증상태"]


def test_explicit_admin_column_verified():
    df = pd.DataFrame({"행정읍면동": ["사동", "존재하지않는동"]})
    _, report, _ = map_facilities(df, "기관수", ["사동"])
    assert report["확인매핑행수"] == 1


def test_coordinate_spatial_join():
    boundary = gpd.GeoDataFrame({"ADM_NM": ["사동"]},
        geometry=[box(126.8,37.3,126.9,37.4)], crs="EPSG:4326")
    df = pd.DataFrame({"위도": [37.35, 38.0], "경도": [126.85, 129.0]})
    _, report, audit = map_facilities(df,"기관수",["사동"],boundaries=boundary)
    assert report["확인매핑행수"] == 1
    assert audit.loc[0,"매핑방법"] == "좌표-행정동공간조인"


def test_manual_override():
    df = pd.DataFrame({"주소":["안산시 해양로 12"]})
    overrides = pd.DataFrame({"구분":["기관수"],"원본행번호":[1],"확인행정동":["사동"]})
    _, report, _ = map_facilities(df, "기관수", ["사동"], overrides=overrides)
    assert report["확인매핑행수"] == 1


def test_spatial_takes_precedence_over_conflicting_admin_name():
    boundary = gpd.GeoDataFrame({"ADM_NM": ["사동", "이동"]},
        geometry=[box(126.8,37.3,126.85,37.4), box(126.85,37.3,126.9,37.4)], crs="EPSG:4326")
    df = pd.DataFrame({"행정동": ["이동"], "위도": [37.35], "경도": [126.82]})
    counts, report, audit = map_facilities(df, "기관수", ["사동", "이동"], boundaries=boundary)
    assert audit.loc[0,"매핑행정동"] == "사동"
    assert bool(audit.loc[0,"행정동컬럼_좌표불일치"])
    assert counts.loc[0,"행정동"] == "사동"
    assert report["공간조인매핑행수"] == 1

def test_provisional_rows_are_counted_and_audited():
    df = pd.DataFrame({"주소": ["안산시 사동 13", "알 수 없음"]})
    counts, report, audit = map_facilities(df,"기관수",["사동"])
    assert report["잠정매핑행수"] == 1
    assert report["미매핑행수"] == 1
    assert bool(audit.loc[0,"집계반영"])
    assert not bool(audit.loc[1,"집계반영"])
    assert counts.loc[0,"기관수"] == 1
