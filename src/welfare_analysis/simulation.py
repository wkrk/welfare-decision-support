"""Counterfactual scenario: add facilities to one dong, hold original PCA fit fixed."""
import pandas as pd
from .config import FACILITY_COLS
from .preprocessing import recalculate_facility_metrics


def simulate_one(baseline, model, target_dong, facility_col="노인복지시설수", add_count=1):
    if facility_col not in FACILITY_COLS:
        raise ValueError(f"알 수 없는 시설 종류: {facility_col}")
    if not isinstance(add_count, int) or add_count < 1:
        raise ValueError("추가 시설수는 양의 정수여야 합니다")
    target = baseline["행정동"].eq(target_dong)
    if int(target.sum()) != 1:
        raise ValueError(f"대상 행정동 미확인 또는 중복: {target_dong}")
    after = baseline.copy()
    after.loc[target, facility_col] += add_count
    after = recalculate_facility_metrics(after)
    after["시행후_PCA"] = model.score(after)
    after["시행후순위"] = after["시행후_PCA"].rank(ascending=False, method="min").astype(int)
    original = baseline.loc[target].iloc[0]
    changed = after.loc[target].iloc[0]
    return {
        "행정동": target_dong, "추가시설": facility_col, "추가개수": add_count,
        "시행전_PCA": float(original["PCA_복지취약도"]),
        "시행후_PCA": float(changed["시행후_PCA"]),
        "취약도점수개선": float(original["PCA_복지취약도"] - changed["시행후_PCA"]),
        "현재순위": int(original["현재순위"]),
        "시행후순위": int(changed["시행후순위"]),
        # The lower rank number is HIGHER vulnerability; moving to 20 from 1 is improvement.
        "취약도순위개선": int(changed["시행후순위"] - original["현재순위"]),
    }


def compare_scenarios(baseline, model, add_counts=(1, 2, 3)):
    results = [simulate_one(baseline, model, dong, add_count=int(n))
               for n in add_counts for dong in baseline["행정동"]]
    details = pd.DataFrame(results)
    summary = details.groupby("추가개수").agg(
        평균점수개선=("취약도점수개선", "mean"),
        평균순위개선=("취약도순위개선", "mean"),
        순위개선지역수=("취약도순위개선", lambda x: int((x > 0).sum())),
    ).reset_index()
    return details, summary
