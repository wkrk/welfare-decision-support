
"""Policy-oriented facility supply index.

This is a hypothetical decision-support index,
not a causal estimate of social welfare outcomes.
"""

import pandas as pd


def calculate_policy_index(df):
    """Calculate a monotonic facility-supply shortage index."""
    result = df.copy()

    required = {
        "노인수",
        "독거노인수",
        "노인복지시설수",
    }

    missing = required - set(result.columns)
    if missing:
        raise ValueError(f"필수 컬럼 누락: {sorted(missing)}")

    if (result["노인수"] <= 0).any():
        raise ValueError("노인수는 0보다 커야 합니다")

    if (
        (result["독거노인수"] < 0)
        | (result["독거노인수"] > result["노인수"])
        | (result["노인복지시설수"] < 0)
    ).any():
        raise ValueError("노인 인구 또는 시설 수가 올바르지 않습니다")

    # 독거노인 비율: 0~1
    solo_ratio = (
        result["독거노인수"] / result["노인수"]
    )

    # 노인 1,000명당 노인복지시설 수
    supply = (
        result["노인복지시설수"]
        / result["노인수"] * 1000
    )

    # 공급량이 증가할수록 부족 지수 감소
    # 독거노인 비율이 높으면 수요 가중
    result["정책_시설부족지수"] = (
        100 * (1 + solo_ratio) / (1 + supply)
    )

    return result


def simulate_policy(
    baseline,
    add_counts=(1, 2, 3),
):
    """Simulate adding senior welfare facilities to each district."""
    baseline = calculate_policy_index(baseline)
    results = []

    for add_count in add_counts:
        if not isinstance(add_count, int) or add_count < 1:
            raise ValueError("추가 시설 수는 양의 정수여야 합니다")

        for _, row in baseline.iterrows():
            after = baseline.copy()

            target = after["행정동"].eq(row["행정동"])

            after.loc[target, "노인복지시설수"] += add_count
            after = calculate_policy_index(after)

            before_score = float(row["정책_시설부족지수"])
            after_score = float(
                after.loc[target, "정책_시설부족지수"].iloc[0]
            )

            improvement = before_score - after_score

            if improvement < -1e-9:
                raise ValueError(
                    "시설 증가 후 부족 지수가 악화됐습니다"
                )

            results.append({
                "행정동": row["행정동"],
                "추가시설수": add_count,
                "시행전_부족지수": before_score,
                "시행후_부족지수": after_score,
                "지수개선량": improvement,
            })

    return pd.DataFrame(results)
