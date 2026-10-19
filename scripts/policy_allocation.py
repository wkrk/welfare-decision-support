
"""Policy-index-based allocation of five hypothetical welfare facilities.

Run:
    python scripts/policy_allocation.py --outputs outputs_policy
"""

import argparse
import math
from pathlib import Path

import pandas as pd


BUDGET = 5
MAX_PER_DONG = 3

BASELINE_REQUIRED = {
    "행정동",
    "노인수",
    "독거노인수",
    "노인복지시설수",
    "정책_시설부족지수",
}

SCENARIO_REQUIRED = {
    "행정동",
    "추가시설수",
    "시행전_부족지수",
    "시행후_부족지수",
    "지수개선량",
}


def shortage_score(elder, solo, facilities):
    """Same formula as policy_index.py."""
    return 100 * (1 + solo / elder) / (
        1 + 1000 * facilities / elder
    )


def load_and_validate(output_dir):
    baseline_path = output_dir / "policy_baseline.csv"
    scenario_path = output_dir / "policy_scenarios.csv"

    baseline = pd.read_csv(baseline_path, encoding="utf-8-sig")
    scenarios = pd.read_csv(scenario_path, encoding="utf-8-sig")

    if not BASELINE_REQUIRED.issubset(baseline.columns):
        raise ValueError("policy_baseline.csv 필수 컬럼 누락")

    if not SCENARIO_REQUIRED.issubset(scenarios.columns):
        raise ValueError("policy_scenarios.csv 필수 컬럼 누락")

    if baseline.empty or baseline["행정동"].duplicated().any():
        raise ValueError("기준 데이터가 비었거나 행정동이 중복됐습니다")

    if baseline["행정동"].isna().any():
        raise ValueError("기준 데이터에 행정동 누락")

    if (
        baseline["노인수"].le(0).any()
        or baseline["독거노인수"].lt(0).any()
        or (
            baseline["독거노인수"]
            > baseline["노인수"]
        ).any()
        or baseline["노인복지시설수"].lt(0).any()
    ):
        raise ValueError("노인 인구 또는 시설 수 오류")

    if scenarios.duplicated(["행정동", "추가시설수"]).any():
        raise ValueError("중복된 시설 추가 시나리오")

    # The input scenario must cover every dong for n=1,2,3.
    expected = {
        (dong, n)
        for dong in baseline["행정동"]
        for n in range(1, MAX_PER_DONG + 1)
    }

    actual = set(zip(
        scenarios["행정동"],
        scenarios["추가시설수"],
    ))

    if expected != actual or len(scenarios) != len(expected):
        raise ValueError(
            "모든 행정동에 대한 1~3개 시설 시나리오가 필요합니다"
        )

    # Check the two CSVs belong to a consistent calculation.
    base_lookup = baseline.set_index("행정동")

    for row in scenarios.itertuples(index=False):
        dong = row.행정동
        n = int(row.추가시설수)
        original = base_lookup.loc[dong]

        elder = float(original["노인수"])
        solo = float(original["독거노인수"])
        facilities = float(original["노인복지시설수"])

        before = shortage_score(elder, solo, facilities)
        after = shortage_score(elder, solo, facilities + n)
        improvement = before - after

        observed = (
            float(row.시행전_부족지수),
            float(row.시행후_부족지수),
            float(row.지수개선량),
        )

        calculated = (before, after, improvement)

        if not all(
            math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-8)
            for a, b in zip(observed, calculated)
        ):
            raise ValueError(
                f"{dong} +{n}개: 정책지수 계산 불일치"
            )

        if not math.isclose(
            before,
            float(original["정책_시설부족지수"]),
            rel_tol=1e-9,
            abs_tol=1e-8,
        ):
            raise ValueError(
                f"{dong}: 기준 지수와 시나리오 불일치"
            )

    return baseline, scenarios


def allocate(baseline, scenarios, method):
    """Greedy marginal allocation for a separable diminishing-return score."""

    if method not in ("plain", "needs"):
        raise ValueError("method는 plain 또는 needs여야 합니다")

    dongs = baseline["행정동"].tolist()

    if BUDGET > len(dongs) * MAX_PER_DONG:
        raise ValueError("배분 가능한 시설 수가 부족합니다")

    base_scores = baseline.set_index("행정동")[
        "정책_시설부족지수"
    ].to_dict()

    average_score = sum(base_scores.values()) / len(base_scores)

    if average_score <= 0:
        raise ValueError("평균 시설부족지수가 양수가 아닙니다")

    # needs: baseline shortage relative to overall mean.
    # This is a hypothetical policy preference, not a learned weight.
    weights = {
        dong: (
            1.0
            if method == "plain"
            else base_scores[dong] / average_score
        )
        for dong in dongs
    }

    lookup = {
        (str(row.행정동), int(row.추가시설수)):
            float(row.지수개선량)
        for row in scenarios.itertuples(index=False)
    }

    allocation = {dong: 0 for dong in dongs}
    steps = []

    for step in range(1, BUDGET + 1):
        best = None

        for dong in dongs:
            current = allocation[dong]

            if current >= MAX_PER_DONG:
                continue

            next_count = current + 1

            previous_gain = (
                lookup[(dong, current)] if current > 0 else 0.0
            )

            next_gain = lookup[(dong, next_count)]

            marginal_gain = next_gain - previous_gain
            weighted_gain = marginal_gain * weights[dong]

            candidate = (
                weighted_gain,
                marginal_gain,
                dong,
                next_count,
            )

            if best is None or candidate[0] > best[0] + 1e-12:
                best = candidate

        if best is None:
            raise ValueError("시설을 모두 배분할 수 없습니다")

        weighted_gain, marginal_gain, dong, count = best

        if marginal_gain <= 0:
            raise ValueError("시설 추가의 한계 개선량이 양수가 아닙니다")

        allocation[dong] = count

        steps.append({
            "방식": method,
            "배분순서": step,
            "행정동": dong,
            "해당동누적시설수": count,
            "이번시설_지수개선량": marginal_gain,
            "이번시설_가중개선량": weighted_gain,
        })

    records = []

    for dong in dongs:
        count = allocation[dong]

        improvement = (
            lookup[(dong, count)] if count > 0 else 0.0
        )

        records.append({
            "방식": method,
            "행정동": dong,
            "기준_시설부족지수": base_scores[dong],
            "추가시설수": count,
            "시행후_시설부족지수": base_scores[dong] - improvement,
            "지수개선량": improvement,
            "정책가중치": weights[dong],
            "가중개선량": improvement * weights[dong],
        })

    result = pd.DataFrame(records)

    if int(result["추가시설수"].sum()) != BUDGET:
        raise AssertionError("총 시설 수 제약 위반")

    if result["추가시설수"].max() > MAX_PER_DONG:
        raise AssertionError("행정동별 최대 시설 수 제약 위반")

    return result, pd.DataFrame(steps)


def main():
    parser = argparse.ArgumentParser(
        description="정책지수 기반 시설 5개 배분"
    )

    parser.add_argument(
        "--outputs",
        type=Path,
        default=Path("outputs_policy"),
    )

    args = parser.parse_args()
    output_dir = args.outputs

    baseline, scenarios = load_and_validate(output_dir)

    allocations = []
    steps = []
    summaries = []

    for method in ("plain", "needs"):
        result, trace = allocate(
            baseline, scenarios, method
        )

        allocations.append(result)
        steps.append(trace)

        summaries.append({
            "방식": method,
            "총추가시설수": int(result["추가시설수"].sum()),
            "배분행정동수": int(
                result["추가시설수"].gt(0).sum()
            ),
            "전체지수개선합": float(
                result["지수개선량"].sum()
            ),
            "가중개선합": float(
                result["가중개선량"].sum()
            ),
            "시행전지수합": float(
                result["기준_시설부족지수"].sum()
            ),
            "시행후지수합": float(
                result["시행후_시설부족지수"].sum()
            ),
        })

    allocation_df = pd.concat(
        allocations, ignore_index=True
    )

    steps_df = pd.concat(
        steps, ignore_index=True
    )

    summary_df = pd.DataFrame(summaries)

    allocation_df.to_csv(
        output_dir / "policy_allocation.csv",
        index=False,
        encoding="utf-8-sig",
    )

    steps_df.to_csv(
        output_dir / "policy_allocation_steps.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary_df.to_csv(
        output_dir / "policy_allocation_comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )

    for method in ("plain", "needs"):
        selected = allocation_df.loc[
            allocation_df["방식"].eq(method)
            & allocation_df["추가시설수"].gt(0),
            ["행정동", "추가시설수", "지수개선량"],
        ]

        print(f"\n[{method}] 시설 배분")
        print(selected.to_string(index=False))

    print("\n[방식별 비교]")
    print(summary_df.to_string(index=False))

    print("\n[완료] 정책지수 기반 시설 배분 파일 3개 저장")


if __name__ == "__main__":
    main()
