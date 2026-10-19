from welfare_analysis.coordinate_enrichment import enrich_tables
import pandas as pd


def test_coordinates_without_parenthesized_suffix(tmp_path):
    pd.DataFrame({"시설명": ["테스트기관"], "위도": [37.3], "경도": [126.8]}).to_csv(
        tmp_path / "의료기관_위도와경도.csv", index=False, encoding="utf-8-sig"
    )
    tables = {"medical": pd.DataFrame({"의료기관명": ["테스트기관"]})}
    result = enrich_tables(tables, tmp_path)
    assert result["medical"].loc[0, "위도"] == 37.3


def test_coordinates_with_legacy_suffix(tmp_path):
    pd.DataFrame({"시설명": ["테스트기관"], "위도": [37.3], "경도": [126.8]}).to_csv(
        tmp_path / "의료기관_위도와경도(1).csv", index=False, encoding="utf-8-sig"
    )
    tables = {"medical": pd.DataFrame({"의료기관명": ["테스트기관"]})}
    result = enrich_tables(tables, tmp_path)
    assert result["medical"].loc[0, "경도"] == 126.8
