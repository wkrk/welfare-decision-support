
"""Policy allocation comparison, maps and HTML decision report.

Run:
    python scripts/policy_report.py --outputs outputs_policy --data-dir data
"""

import argparse
import base64
import html
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from welfare_analysis.data_loader import load_boundary
from welfare_analysis.geography import select_ansan_boundaries


BUDGET = 5
MAX_PER_DONG = 3

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

METHOD_LABELS = {
    "plain": "효율성 우선",
    "needs": "수요 가중",
    "equity": "취약지역 우선",
}


def score(elder, solo, facilities):
    return 100 * (1 + solo / elder) / (
        1 + facilities * 1000 / elder
    )


def check_baseline(baseline):
    required = {
        "행정동", "노인수", "독거노인수",
        "노인복지시설수", "정책_시설부족지수"
    }
    missing = required - set(baseline.columns)
    if missing:
        raise ValueError(f"기준 데이터 컬럼 누락: {missing}")

    if len(baseline) != 25 or baseline["행정동"].duplicated().any():
        raise ValueError("25개 고유 행정동이 필요합니다")

    if (
        baseline["노인수"].le(0).any()
        or baseline["독거노인수"].lt(0).any()
        or (baseline["독거노인수"] > baseline["노인수"]).any()
        or baseline["노인복지시설수"].lt(0).any()
    ):
        raise ValueError("인구 또는 시설 수가 올바르지 않습니다")

    for row in baseline.itertuples(index=False):
        calculated = score(
            row.노인수,
            row.독거노인수,
            row.노인복지시설수,
        )
        if abs(calculated - row.정책_시설부족지수) > 1e-8:
            raise ValueError(f"{row.행정동}: 정책지수 불일치")


def allocate_equity(baseline):
    """Allocate to the dong with the highest current shortage score."""

    result = baseline.copy()
    result["추가시설수"] = 0

    for _ in range(BUDGET):
        candidates = result.loc[
            result["추가시설수"] < MAX_PER_DONG
        ].copy()

        candidates["현재부족지수"] = candidates.apply(
            lambda row: score(
                row["노인수"],
                row["독거노인수"],
                row["노인복지시설수"] + row["추가시설수"],
            ),
            axis=1,
        )

        chosen = candidates.sort_values(
            ["현재부족지수", "행정동"],
            ascending=[False, True],
        ).index[0]

        result.loc[chosen, "추가시설수"] += 1

    result["시행후_시설부족지수"] = result.apply(
        lambda row: score(
            row["노인수"],
            row["독거노인수"],
            row["노인복지시설수"] + row["추가시설수"],
        ),
        axis=1,
    )

    result["지수개선량"] = (
        result["정책_시설부족지수"]
        - result["시행후_시설부족지수"]
    )

    result = result.rename(
        columns={"정책_시설부족지수": "기준_시설부족지수"}
    )

    result["방식"] = "equity"

    return result[
        [
            "방식", "행정동", "기준_시설부족지수",
            "추가시설수", "시행후_시설부족지수",
            "지수개선량",
        ]
    ]


def validate_allocation(frame, baseline):
    if frame["행정동"].duplicated().any():
        raise ValueError("배분 결과에 중복 행정동이 있습니다")

    if set(frame["행정동"]) != set(baseline["행정동"]):
        raise ValueError("배분 결과의 행정동 구성 불일치")

    counts = frame["추가시설수"]

    if (
        counts.isna().any()
        or (counts < 0).any()
        or (counts > MAX_PER_DONG).any()
        or not (counts == counts.astype(int)).all()
    ):
        raise ValueError("행정동별 추가 시설 수 오류")

    if int(counts.sum()) != BUDGET:
        raise ValueError("시설 총량이 5개가 아닙니다")

    base = baseline.set_index("행정동")

    for row in frame.itertuples(index=False):
        original = base.loc[row.행정동]

        before = score(
            original["노인수"],
            original["독거노인수"],
            original["노인복지시설수"],
        )

        after = score(
            original["노인수"],
            original["독거노인수"],
            original["노인복지시설수"] + row.추가시설수,
        )

        if (
            abs(before - row.기준_시설부족지수) > 1e-8
            or abs(after - row.시행후_시설부족지수) > 1e-8
            or abs(before - after - row.지수개선량) > 1e-8
        ):
            raise ValueError(
                f"{row.방식}/{row.행정동}: 배분 계산 불일치"
            )


def create_summary(allocations):
    records = []

    for method, part in allocations.groupby("방식"):
        before = part["기준_시설부족지수"].sum()
        after = part["시행후_시설부족지수"].sum()

        records.append({
            "방식": method,
            "배분방식": METHOD_LABELS[method],
            "추가시설합계": int(part["추가시설수"].sum()),
            "선정지역수": int(part["추가시설수"].gt(0).sum()),
            "개선량합계": before - after,
            "지수합계감소율(%)": (before - after) / before * 100,
            "시행후최대부족지수": part[
                "시행후_시설부족지수"
            ].max(),
        })

    return pd.DataFrame(records)


def create_comparison_chart(summary, output_dir):
    ordered = summary.set_index("방식").loc[
        ["plain", "needs", "equity"]
    ]

    fig, ax = plt.subplots(figsize=(9, 5))

    bars = ax.barh(
        ordered["배분방식"],
        ordered["개선량합계"],
        color=["#4872a7", "#61a58d", "#e5a65c"],
    )

    ax.invert_yaxis()
    ax.set_xlabel("시설부족지수 개선량 합계")
    ax.set_title("정책 대안별 시설부족지수 개선량 비교")

    for bar in bars:
        ax.text(
            bar.get_width() + 1,
            bar.get_y() + bar.get_height() / 2,
            f"{bar.get_width():.2f}",
            va="center",
        )

    ax.set_xlim(0, max(ordered["개선량합계"]) * 1.22)

    fig.tight_layout()
    path = output_dir / "policy_comparison.png"
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return path


def create_allocation_maps(allocations, data_dir, output_dir):
    boundaries = select_ansan_boundaries(
        load_boundary(data_dir)
    ).to_crs(epsg=5179)

    fig, axes = plt.subplots(
        1, 3, figsize=(19, 7), constrained_layout=True
    )

    for ax, method in zip(
        axes, ["plain", "needs", "equity"]
    ):
        part = allocations.loc[
            allocations["방식"].eq(method)
        ]

        geo = boundaries.merge(
            part,
            left_on="ADM_NM",
            right_on="행정동",
            validate="one_to_one",
        )

        if len(geo) != 25:
            raise ValueError(
                f"{method}: 지도와 행정동 결합 불일치"
            )

        geo.plot(
            column="추가시설수",
            cmap="YlOrRd",
            vmin=0,
            vmax=3,
            linewidth=0.7,
            edgecolor="#555555",
            ax=ax,
        )

        # Only label districts receiving a facility.
        selected = geo.loc[geo["추가시설수"] > 0]

        for _, row in selected.iterrows():
            pt = row.geometry.representative_point()

            ax.annotate(
                f'{row["ADM_NM"]} +{int(row["추가시설수"])}',
                (pt.x, pt.y),
                fontsize=8,
                ha="center",
                va="center",
                bbox={
                    "boxstyle": "round,pad=0.2",
                    "fc": "white",
                    "alpha": 0.85,
                    "ec": "none",
                },
            )

        ax.set_title(METHOD_LABELS[method], fontsize=14)
        ax.set_axis_off()

    path = output_dir / "policy_allocation_maps.png"
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return path


def image_uri(path):
    content = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{content}"


def create_html(allocations, summary, chart, maps, output_dir):
    sections = []

    for method in ("plain", "needs", "equity"):
        selected = allocations.loc[
            allocations["방식"].eq(method)
            & allocations["추가시설수"].gt(0),
            [
                "행정동", "추가시설수", "기준_시설부족지수",
                "시행후_시설부족지수", "지수개선량"
            ],
        ].sort_values("지수개선량", ascending=False)

        table_html = selected.to_html(
            index=False,
            float_format=lambda x: f"{x:.3f}",
            border=0,
            classes="report-table",
        )

        sections.append(
            f"<section><h2>{METHOD_LABELS[method]}</h2>"
            f"{table_html}</section>"
        )

    summary_html = summary.to_html(
        index=False,
        float_format=lambda x: f"{x:.3f}",
        border=0,
        classes="report-table",
    )

    document = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>안산시 노인복지시설 배분 의사결정 보고서</title>
<style>
body {{
  font-family: "Malgun Gothic", Arial, sans-serif;
  background: #f4f6fa; color: #253044;
  margin: 0; line-height: 1.7;
}}
main {{ max-width: 1200px; margin: auto; padding: 28px; }}
section {{
  background: white; padding: 25px; margin: 20px 0;
  border-radius: 12px; border: 1px solid #e0e5ec;
}}
h1 {{ font-size: 29px; }}
h2 {{ font-size: 21px; }}
img {{ width: 100%; height: auto; }}
.report-table {{ border-collapse: collapse; width: 100%; }}
.report-table th, .report-table td {{
  border-bottom: 1px solid #e4e8ef;
  padding: 9px; text-align: left;
}}
.report-table th {{ background: #eaf0f7; }}
.notice {{
  background: #fff7e8; padding: 15px;
  border-left: 4px solid #c58b32;
}}
</style>
</head>
<body>
<main>
<h1>안산시 노인복지시설 배분 의사결정 보고서</h1>
<p>분석 대상: 25개 행정동 / 가상 추가 시설: 총 5개</p>

<section>
<h2>1. 분석 목적</h2>
<p>
PCA와 K-Means는 지역 특성 분석에 사용하고,
시설 배분은 독립적인 정책 시설부족지수로 평가한다.
동일한 공급 총량과 지역별 배분 상한을 적용하여
효율성, 수요 가중, 취약지역 우선 대안을 비교한다.
</p>
</section>

<section>
<h2>2. 배분 방식별 결과</h2>
{summary_html}
<img alt="배분 방식별 개선량" src="{image_uri(chart)}">
</section>

<section>
<h2>3. 정책 대안별 배분 지도</h2>
<img alt="안산시 배분 지도" src="{image_uri(maps)}">
</section>

{''.join(sections)}

<section>
<h2>4. 의사결정 해석</h2>
<p>
개선량 합계는 계산된 시설부족지수의 감소량이며,
실제 주민 편익, 예산 절감액 또는 사회적 투자수익률이 아니다.
</p>
<p>
효율성 우선 방식은 개선량 합계에,
취약지역 우선 방식은 지역별 최대 부족 수준에 초점을 둔다.
수요 가중 방식은 정책 가중치를 사용한 별도의 목적함수다.
</p>
</section>

<section>
<h2>5. 데이터 및 모형의 한계</h2>
<div class="notice">
노인복지시설 집계 범위가 제한적이며,
잠정 매핑과 미매핑 시설이 존재한다.
시설별 설치 비용, 수용인원, 이동거리, 실제 이용률은
반영하지 않았다. 분석 지수와 가중치는 가상 정책 모형이며
실제 시설 입지 또는 투자 결정을 의미하지 않는다.
</div>
</section>
</main>
</body>
</html>"""

    path = output_dir / "policy_decision_report.html"
    path.write_text(document, encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--outputs",
        type=Path,
        default=Path("outputs_policy"),
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
    )
    args = parser.parse_args()

    output_dir = args.outputs
    baseline = pd.read_csv(
        output_dir / "policy_baseline.csv",
        encoding="utf-8-sig",
    )
    previous = pd.read_csv(
        output_dir / "policy_allocation.csv",
        encoding="utf-8-sig",
    )

    check_baseline(baseline)

    original_methods = previous.loc[
        previous["방식"].isin(["plain", "needs"]),
        [
            "방식", "행정동", "기준_시설부족지수",
            "추가시설수", "시행후_시설부족지수",
            "지수개선량",
        ],
    ].copy()

    if set(original_methods["방식"]) != {"plain", "needs"}:
        raise ValueError("plain과 needs 결과가 모두 필요합니다")

    equity = allocate_equity(baseline)

    allocations = pd.concat(
        [original_methods, equity],
        ignore_index=True,
    )

    for _, group in allocations.groupby("방식"):
        validate_allocation(group, baseline)

    summary = create_summary(allocations)

    allocations.to_csv(
        output_dir / "policy_allocation_three_methods.csv",
        index=False, encoding="utf-8-sig",
    )
    summary.to_csv(
        output_dir / "policy_three_methods_summary.csv",
        index=False, encoding="utf-8-sig",
    )

    chart = create_comparison_chart(summary, output_dir)
    maps = create_allocation_maps(
        allocations, args.data_dir, output_dir
    )
    report = create_html(
        allocations, summary, chart, maps, output_dir
    )

    print("\n[정책 대안 비교]")
    print(summary.to_string(index=False))

    print("\n[취약지역 우선 배분]")
    print(
        equity.loc[equity["추가시설수"] > 0,
                   ["행정동", "추가시설수", "지수개선량"]]
        .to_string(index=False)
    )

    print(f"\n[완료] {report}")
    print(f"[완료] {maps}")
    print(f"[완료] {chart}")


if __name__ == "__main__":
    main()
