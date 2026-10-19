import pandas as pd
import pytest
from welfare_analysis.config import FACILITY_COLS
from welfare_analysis.preprocessing import recalculate_facility_metrics
from welfare_analysis.clustering import cluster_districts
from welfare_analysis.vulnerability import fit_vulnerability
from welfare_analysis.simulation import compare_scenarios
from welfare_analysis.validation import evaluate_cluster_counts, evaluate_pca_direction, evaluate_scenarios, save_validation_report


def sample():
    rows = []
    for i in range(12):
        elder = 900 + i*115
        row = {"행정동": f"시험{i}", "노인수": elder, "독거노인수": 160+i*18,
               "독거노인비율": (160+i*18)/elder*100}
        row.update({c: (i*i + j*3) % 11 for j,c in enumerate(FACILITY_COLS)})
        rows.append(row)
    return recalculate_facility_metrics(pd.DataFrame(rows))


def test_validation_outputs(tmp_path):
    dataset = sample()
    clustered, _ = cluster_districts(dataset)
    baseline, model, _, _ = fit_vulnerability(clustered)
    details, summary = compare_scenarios(baseline, model)
    k, d, s = save_validation_report(baseline, model, details, summary, tmp_path)
    assert len(k) == 7 and len(d) == 4 and len(s) == 3
    assert (tmp_path / "validation_report.md").exists()
    assert int(s["시나리오수"].sum()) == 36


def test_validation_rejects_wrong_improvement():
    bad = pd.DataFrame({"추가개수":[1], "시행전_PCA":[2.0], "시행후_PCA":[1.0],
                        "취약도점수개선":[-1.0], "현재순위":[1],
                        "시행후순위":[2], "취약도순위개선":[1]})
    with pytest.raises(ValueError, match="점수개선 계산"):
        evaluate_scenarios(bad, pd.DataFrame())
