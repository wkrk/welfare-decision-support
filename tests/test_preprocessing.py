import pandas as pd
import pytest
from welfare_analysis.preprocessing import extract_dong, prepare_elder, count_facilities

def test_extract_no_building_false_positive():
    assert extract_dong("경기도 안산시 단원구 101동") is None
    assert extract_dong("경기도 안산시 상록구 사동 12") == "사동"
    assert extract_dong("안산시 (본오1동) 77") == "본오1동"

def test_unmapped_is_reported():
    df = pd.DataFrame({"주소": ["안산시 사동 1", "안산시 101동 20"]})
    result, quality = count_facilities(df, "주소", "시설수", ["사동"])
    assert result.loc[0, "시설수"] == 1
    assert quality["미매핑행수"] == 1

def test_elder_zero_rejected():
    df = pd.DataFrame({"행정동": ["사동"], "노인(남)": [0], "노인(여)": [0], "독거노인(남)": [0], "독거노인(여)": [0]})
    with pytest.raises(ValueError): prepare_elder(df)
