
"""Finalize portfolio maps and documentation.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\finalize_portfolio.py
"""

from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
import pandas as pd

from welfare_analysis.data_loader import load_boundary
from welfare_analysis.geography import select_ansan_boundaries


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs_policy"
DOCS = ROOT / "docs"
DATA = ROOT / "data"

METHODS = [
    ("plain", "효율성 우선"),
    ("needs", "수요 가중"),
    ("equity", "취약지역 우선"),
]

COLORS = ["#f1f4f8", "#f2af59", "#d87640", "#963c35"]
CMAP = ListedColormap(COLORS)
NORM = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], CMAP.N)

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def save_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(content).strip() + "\n",
        encoding="utf-8",
    )
    print("[완료]", path.relative_to(ROOT))


def load_results():
    allocation = pd.read_csv(
        OUTPUT / "policy_allocation_three_methods.csv",
        encoding="utf-8-sig",
    )

    summary = pd.read_csv(
        OUTPUT / "policy_three_methods_summary.csv",
        encoding="utf-8-sig",
    )

    baseline = pd.read_csv(
        OUTPUT / "policy_baseline.csv",
        encoding="utf-8-sig",
    )

    expected_dongs = set(baseline["행정동"])

    if len(expected_dongs) != 25 or len(baseline) != 25:
        raise ValueError("25개 행정동 기준 데이터가 아닙니다")

    for method, _ in METHODS:
        part = allocation.loc[allocation["방식"] == method]

        if (
            len(part) != 25
            or set(part["행정동"]) != expected_dongs
            or part["행정동"].duplicated().any()
        ):
            raise ValueError(f"{method}: 행정동 구성 오류")

        counts = part["추가시설수"]

        if (
            counts.isna().any()
            or (counts < 0).any()
            or (counts > 3).any()
            or not (counts == counts.astype(int)).all()
            or int(counts.sum()) != 5
        ):
            raise ValueError(f"{method}: 배분 제약조건 오류")

        before = part["기준_시설부족지수"]
        after = part["시행후_시설부족지수"]
        improvement = part["지수개선량"]

        if ((before - after - improvement).abs() > 1e-8).any():
            raise ValueError(f"{method}: 개선량 계산 불일치")

        reported = summary.loc[summary["방식"] == method]

        if len(reported) != 1:
            raise ValueError(f"{method}: 요약 데이터 오류")

        actual_sum = float(improvement.sum())
        reported_sum = float(reported.iloc[0]["개선량합계"])

        if abs(actual_sum - reported_sum) > 1e-8:
            raise ValueError(f"{method}: 요약 개선량 불일치")

    return allocation, summary, baseline


def make_final_map(allocation):
    boundaries = select_ansan_boundaries(
        load_boundary(DATA)
    ).to_crs(epsg=5179)

    if (
        len(boundaries) != 25
        or boundaries["ADM_NM"].duplicated().any()
    ):
        raise ValueError("지도 경계는 25개 고유 행정동이어야 합니다")

    fig, axes = plt.subplots(
        1, 3, figsize=(22, 9)
    )

    for ax, (method, label) in zip(axes, METHODS):
        part = allocation.loc[
            allocation["방식"] == method
        ].copy()

        geo = boundaries.merge(
            part,
            left_on="ADM_NM",
            right_on="행정동",
            how="inner",
            validate="one_to_one",
        )

        if len(geo) != 25:
            raise ValueError(f"{method}: 지도 결합 실패")

        # Daebu-dong is displayed in a separate inset.
        city = geo.loc[geo["ADM_NM"] != "대부동"]
        daebu = geo.loc[geo["ADM_NM"] == "대부동"]

        city.plot(
            column="추가시설수",
            cmap=CMAP,
            norm=NORM,
            linewidth=0.7,
            edgecolor="#596477",
            ax=ax,
        )

        selected = geo.loc[
            geo["추가시설수"] > 0
        ].sort_values("ADM_NM")

        city_selected = selected.loc[
            selected["ADM_NM"] != "대부동"
        ]

        # Numbered labels avoid overlapping long dong names.
        legend_lines = []

        for number, (_, row) in enumerate(
            selected.iterrows(), start=1
        ):
            legend_lines.append(
                f"{number}. {row['ADM_NM']} +"
                f"{int(row['추가시설수'])}"
            )

            if row["ADM_NM"] != "대부동":
                pt = row.geometry.representative_point()

                ax.text(
                    pt.x, pt.y, str(number),
                    ha="center", va="center",
                    fontsize=9, fontweight="bold",
                    bbox=dict(
                        boxstyle="circle,pad=0.22",
                        facecolor="white",
                        edgecolor="#333333",
                        alpha=0.95,
                    ),
                )

        # Zoom to the main urban area.
        xmin, ymin, xmax, ymax = city.total_bounds
        margin_x = (xmax - xmin) * 0.08
        margin_y = (ymax - ymin) * 0.08

        ax.set_xlim(xmin - margin_x, xmax + margin_x)
        ax.set_ylim(ymin - margin_y, ymax + margin_y)
        ax.set_aspect("equal")
        ax.set_axis_off()
        ax.set_title(label, fontsize=17, pad=14)

        # Daebu-dong inset.
        inset = ax.inset_axes([0.02, 0.02, 0.30, 0.34])

        daebu.plot(
            column="추가시설수",
            cmap=CMAP,
            norm=NORM,
            linewidth=0.6,
            edgecolor="#596477",
            ax=inset,
        )

        inset.set_axis_off()
        inset.set_title("대부동", fontsize=10)

        if int(daebu.iloc[0]["추가시설수"]) > 0:
            daebu_number = next(
                n for n, (_, row) in enumerate(
                    selected.iterrows(), start=1
                )
                if row["ADM_NM"] == "대부동"
            )

            pt = daebu.iloc[0].geometry.representative_point()

            inset.text(
                pt.x, pt.y, str(daebu_number),
                ha="center", va="center",
                fontsize=9, fontweight="bold",
                bbox=dict(
                    boxstyle="circle,pad=0.2",
                    facecolor="white",
                    edgecolor="#333333",
                ),
            )

        ax.text(
            0.5, -0.08,
            "  |  ".join(legend_lines),
            transform=ax.transAxes,
            ha="center", va="top",
            fontsize=10,
            wrap=True,
        )

    patches = [
        Patch(facecolor=COLORS[n], edgecolor="#596477",
              label=f"시설 {n}개 추가")
        for n in range(4)
    ]

    fig.legend(
        handles=patches,
        loc="lower center",
        ncol=4,
        fontsize=11,
        frameon=False,
        bbox_to_anchor=(0.5, 0.045),
    )

    fig.suptitle(
        "안산시 노인복지시설 배분 대안 비교",
        fontsize=21, y=0.97,
    )

    fig.subplots_adjust(
        left=0.02, right=0.98,
        top=0.87, bottom=0.20,
        wspace=0.10,
    )

    path = OUTPUT / "policy_allocation_maps_final.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)

    print("[완료]", path.relative_to(ROOT))


def make_docs(allocation, summary, baseline):
    methods = {
        row["방식"]: row
        for _, row in summary.iterrows()
    }

    def info(method, col):
        return methods[method][col]

    result_lines = []

    for method, label in METHODS:
        part = allocation.loc[
            (allocation["방식"] == method)
            & (allocation["추가시설수"] > 0)
        ].sort_values("지수개선량", ascending=False)

        selected = ", ".join(
            f"{row['행정동']}(+{int(row['추가시설수'])})"
            for _, row in part.iterrows()
        )

        result_lines.append(
            f"| {label} | {selected} | "
            f"{float(info(method, '개선량합계')):.2f} | "
            f"{float(info(method, '시행후최대부족지수')):.2f} |"
        )

    results_table =  "\n".join(
    "        " + line for line in result_lines
)

    save_text(
        ROOT / "README_PORTFOLIO.md",
        """
        # 안산시 공공데이터 기반 복지시설 배분 의사결정 지원

        Python, GeoPandas, PCA, K-Means 및 정책 시뮬레이션을
        활용한 데이터 기반 의사결정 지원 프로젝트입니다.

        ## 프로젝트 목적

        안산시 25개 행정동의 고령인구 및 복지시설 자료를
        통합하고 지역별 특성을 비교합니다.

        제한된 시설 공급 조건에서 대안별 결과를 분석하여
        의사결정에 필요한 기초자료를 제시합니다.

        ## 분석 구조

        1. 공공데이터 수집 및 데이터 품질 확인
        2. 시설 주소·좌표와 행정동 경계 공간조인
        3. PCA 및 K-Means 기반 지역 특성 분석
        4. 별도 시설부족지수 설계
        5. 시설 총 5개 배분 대안 비교
        6. 지도 및 HTML 보고서 생성

        ## 주요 기술

        - Python / pandas / NumPy
        - GeoPandas / Shapely
        - scikit-learn / PCA / K-Means
        - Matplotlib / Folium
        - pytest

        ## 핵심 결과

        - 25개 행정동 분석
        - 75개 단일 지역 시설 확충 시나리오
        - 효율성, 수요 가중, 취약지역 우선 3개 배분 대안 비교
        - 총 5개 시설 추가, 행정동별 최대 3개 제약

        ![정책 대안 비교](outputs_policy/policy_comparison.png)

        ![최종 시설 배분 지도](outputs_policy/policy_allocation_maps_final.png)

        ## 문서

        - [분석 방법론](docs/METHODOLOGY.md)
        - [분석 결과](docs/RESULTS.md)
        - [한계 및 유의사항](docs/LIMITATIONS.md)
        - [재현 실행 안내](docs/WORKFLOW.md)

        ## 해석상 주의

        본 프로젝트는 가상 투자 대안 비교를 위한 분석입니다.
        정책지수 개선은 실제 복지 효과, 투자수익률 또는
        최적 입지의 실증적 증거를 의미하지 않습니다.

        데이터 및 분석상의 한계는 LIMITATIONS 문서를 참고하세요.
        """,
    )

    save_text(
        DOCS / "METHODOLOGY.md",
        """
        # 분석 방법론

        ## 1. 분석 대상

        안산시 25개 행정동의 고령인구, 독거노인 및
        시설 분포를 행정동 단위로 통합합니다.

        ## 2. 데이터 매핑

        좌표가 있는 시설은 행정동 SHP 경계와 공간조인합니다.
        좌표가 없는 일부 자료는 명시적 행정동 정보,
        보조자료 또는 주소를 통해 연결합니다.

        좌표 기반 확인, 잠정 매핑, 미매핑을 구분해
        데이터 품질을 평가합니다.

        ## 3. 탐색적 분석

        PCA를 이용해 지역별 변수의 주요 변동 패턴을 살펴봅니다.
        K-Means를 이용해 유사한 특성을 가진 행정동을 묶습니다.

        PCA 설명분산비율은 예측 정확도가 아닙니다.
        PCA 점수를 시설 추가 효과로 직접 해석하지 않습니다.

        ## 4. 독립적인 정책 시설부족지수

        독거노인 비율을 r, 노인 1,000명당 노인복지시설 수를 s라 하면:

        `시설부족지수 = 100 × (1 + r) / (1 + s)`

        이 지수는 시설 공급이 늘면 감소하도록 정의한
        가상 의사결정 지원 지표입니다.

        계수 100과 수요 가중 구조는 분석자가 설정한 가정으로,
        공식 정책 가중치나 검증된 사회적 효과가 아닙니다.

        ## 5. 시설 배분

        총 시설 5개와 행정동별 최대 3개 추가 조건을 적용합니다.

        - plain: 시설부족지수 개선량 합계 최대화
        - needs: 초기 시설부족지수 기반 가중 개선량 최대화
        - equity: 각 단계에서 현재 부족지수가 가장 큰 지역 우선

        plain과 needs는 감소하는 한계 개선량을 기준으로
        시설을 순차 배분합니다.

        equity는 최대 부족 지역을 우선하는 휴리스틱이며,
        모든 형평성 지표에 대한 전역 최적해를 보장하지 않습니다.
        """,
    )

    save_text(
        DOCS / "RESULTS.md",
        f"""
        # 정책 대안 비교 결과

        분석 대상: 25개 행정동

        배분 제약: 시설 총 5개, 행정동별 최대 3개

        ## 방식별 결과

        | 방식 | 선정 지역 | 지수 개선 합계 | 시행 후 최대 부족지수 |
        |---|---|---:|---:|
        {results_table}

        ## 분석 해석

        효율성 우선과 수요 가중 방식은 동일한 배분 결과를 보였습니다.

        취약지역 우선 방식은 총 개선량은 상대적으로 작지만,
        시행 후 가장 큰 시설부족지수를 낮추는 방향으로 작동했습니다.

        두 목적 중 어느 것을 우선할지는 별도의 정책 판단이 필요합니다.

        ## 시각화

        ![개선량 비교](../outputs_policy/policy_comparison.png)

        ![시설 배분 지도](../outputs_policy/policy_allocation_maps_final.png)

        ## 주의사항

        본 결과는 모형상의 시설 공급 부족 변화입니다.
        실제 설치비, 이용량, 교통 접근성과 수용인원을 고려한
        시설 입지 권고는 아닙니다.
        """,
    )

    save_text(
        DOCS / "LIMITATIONS.md",
        """
        # 데이터 및 모형의 한계

        ## 1. 원자료 기준일의 차이

        공공데이터 자료마다 기준일이 다르므로 동일 시점의
        시설 공급 및 노인인구 현황이라고 가정하기 어렵습니다.

        ## 2. 시설 매핑의 불확실성

        일부 시설은 주소 또는 보조자료에 의해 잠정 매핑되었습니다.
        미매핑 시설도 존재하므로 지역별 집계에 오차가 있을 수 있습니다.

        지도상 위치 확인과 행정동명 확인은 동일한 검증 수준이 아닙니다.

        ## 3. 노인복지시설 자료 범위

        현재 사용하는 노인복지시설 자료의 집계 범위가 제한적입니다.
        분석 대상 시설 수가 지역의 모든 복지서비스 공급을 의미하지 않습니다.

        ## 4. 정책지수 설계

        부족지수의 수식과 가중치는 분석 목적에 따라 설정한
        가상 모형입니다. 공식 정책지수나 실증적으로 검증된 지표가 아닙니다.

        ## 5. 시설 배분 제약

        시설 총 5개는 가상 공급량입니다.
        실제 설치비용, 부지, 법적 기준, 수용정원,
        운영인력, 교통 접근성, 주민 이용률은 반영하지 않았습니다.

        ## 6. PCA·K-Means의 해석

        PCA는 변수들의 변동 패턴을 설명하며,
        K-Means는 데이터 특성에 따른 군집을 제공합니다.

        두 분석은 실제 정책 효과나 인과관계를 입증하지 않습니다.

        ## 7. 활용 범위

        본 결과는 추가 조사를 위한 후보 지역 및
        투자 대안을 비교하는 의사결정 지원 자료입니다.
        실제 투자 결정에는 현장 조사와 비용·편익 검토가 필요합니다.
        """,
    )

    save_text(
        DOCS / "WORKFLOW.md",
        r"""
        # 실행 및 재현 안내

        ## 1. 준비

        프로젝트 루트에서 가상환경을 준비하고
        pyproject.toml 및 requirements.txt에 따른
        의존성을 설치합니다.

        Windows CMD:

        ```cmd
        .venv\Scripts\python.exe -m pip install -e .
        .venv\Scripts\python.exe -m pip install pytest
        ```

        원본 공공데이터 및 SHP 구성 파일은 data 폴더에 둡니다.
        파일명과 인코딩은 config.py를 참고하세요.

        ## 2. PCA·군집·데이터 품질 분석

        ```cmd
        .venv\Scripts\python.exe -m welfare_analysis.main --output-dir outputs_policy
        ```

        이 명령은 policy_index.py가 main.py에 연결된
        현재 버전을 기준으로 합니다.

        ## 3. 정책지수 기반 시설 배분

        ```cmd
        .venv\Scripts\python.exe scripts\policy_allocation.py --outputs outputs_policy
        ```

        ## 4. 세 가지 배분 대안 및 보고서

        ```cmd
        .venv\Scripts\python.exe scripts\policy_report.py --outputs outputs_policy --data-dir data
        ```

        ## 5. 포트폴리오 지도 및 문서 갱신

        ```cmd
        .venv\Scripts\python.exe scripts\finalize_portfolio.py
        ```

        ## 6. 테스트

        ```cmd
        .venv\Scripts\python.exe -m pytest -v
        ```

        ## 7. HTML 보고서

        ```cmd
        start outputs_policy\policy_decision_report.html
        ```

        주의: 기존 PCA 기반 시설 배분 스크립트의 출력은
        최종 정책지수 기반 투자 결과와 구분해야 합니다.
        """,
    )


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    allocation, summary, baseline = load_results()

    make_final_map(allocation)
    make_docs(allocation, summary, baseline)

    print("\n포트폴리오 지도 및 문서 생성 완료")


if __name__ == "__main__":
    main()
