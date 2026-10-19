import pandas as pd
import pytest
from welfare_analysis.config import FACILITY_COLS
from welfare_analysis.preprocessing import recalculate_facility_metrics
from welfare_analysis.vulnerability import fit_vulnerability
from welfare_analysis.simulation import simulate_one, compare_scenarios

def test_direction_and_no_baseline_mutation():
    rows=[]
    for i in range(8):
        row={"행정동": f"테스트{i}", "노인수": 1000+i*120,
             "독거노인수": 130+i*27, "독거노인비율": (130+i*27)/(1000+i*120)*100}
        row.update({name: i % 3 + (1 if name=="의료기관수" else 0) for name in FACILITY_COLS})
        rows.append(row)
    base=recalculate_facility_metrics(pd.DataFrame(rows))
    scored, model, _, _=fit_vulnerability(base)
    before=scored.copy(deep=True)
    result=simulate_one(scored, model, "테스트0", add_count=2)
    assert result["추가개수"] == 2
    pd.testing.assert_frame_equal(scored,before)
    assert result["취약도순위개선"] == result["시행후순위"] - result["현재순위"]
    assert len(compare_scenarios(scored, model)[0]) == 24

def test_invalid_target():
    rows=[]
    for i in range(5):
        row={"행정동":f"테스트{i}","노인수":1000,"독거노인수":150+i*5,"독거노인비율":15+i*.5}
        row.update({name:i+1 for name in FACILITY_COLS}); rows.append(row)
    scored,model,_,_=fit_vulnerability(recalculate_facility_metrics(pd.DataFrame(rows)))
    with pytest.raises(ValueError): simulate_one(scored, model, "없는동")
