
"""Entry point: python -m welfare_analysis.main --data-dir data --output-dir outputs."""

import argparse
import logging
from pathlib import Path

import pandas as pd

from .config import DATA_DIR, OUTPUT_DIR
from .data_loader import load_tables, load_boundary
from .preprocessing import make_district_dataset
from .mapping import write_audits
from .coordinate_enrichment import enrich_tables
from .geography import select_ansan_boundaries, merge_boundaries
from .clustering import cluster_districts
from .vulnerability import fit_vulnerability
from .simulation import compare_scenarios
from .validation import save_validation_report
from .visualization import (
    save_map,
    save_static_map,
    save_scenario_chart,
)
from .policy_index import (
    calculate_policy_index,
    simulate_policy,
)
LOG = logging.getLogger(__name__)


def run(data_dir=DATA_DIR, output_dir=OUTPUT_DIR, k=4):
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 원본 데이터 로드 및 좌표 보완
    tables = load_tables(data_dir)
    tables = enrich_tables(tables, data_dir)

    # 2. 안산시 행정동 경계 로드
    boundaries = select_ansan_boundaries(
        load_boundary(data_dir)
    )

    # 3. 검증된 수동 매핑 자료 확인
    overrides_path = data_dir / "verified_dong_overrides.csv"

    overrides = (
        pd.read_csv(overrides_path, encoding="utf-8-sig")
        if overrides_path.is_file()
        else None
    )

    # 4. 행정동별 분석 데이터 생성
    districts, report, audits = make_district_dataset(
        tables,
        boundaries=boundaries,
        overrides=overrides,
        return_audits=True,
    )

    # 5. 매핑 품질 기록
    write_audits(audits, output_dir)

    report.to_csv(
        output_dir / "mapping_quality.csv",
        index=False,
        encoding="utf-8-sig",
    )

    verified_count = int(report["확인매핑행수"].sum())
    provisional_count = int(report["잠정매핑행수"].sum())
    unmatched_count = int(report["미매핑행수"].sum())

    LOG.info(
        "전체 시설 집계: 확인 %d건 + 잠정 %d건 반영, 미매핑 %d건 제외",
        verified_count,
        provisional_count,
        unmatched_count,
    )

    if unmatched_count > 0:
        LOG.warning(
            "미매핑 시설 %d건이 있습니다. "
            "mapping_quality.csv를 확인하세요.",
            unmatched_count,
        )

    if provisional_count > 0:
        LOG.warning(
            "잠정 매핑 %d건이 분석에 포함되어 있습니다. "
            "실제 정책 판단 전에 행정동 검증이 필요합니다.",
            provisional_count,
        )

    # 6. K-Means 군집분석
    districts, clusters = cluster_districts(
        districts,
        k=k,
    )

    # 7. PCA 기반 상대적 취약도 분석
    baseline, model, loadings, explained = fit_vulnerability(
        districts
    )
    # PCA와 독립된 시설 공급 정책지수
    policy_baseline = calculate_policy_index(baseline)

    policy_scenarios = simulate_policy(
        policy_baseline,
        add_counts=(1, 2, 3),
    )

    # 별도 결과 저장
    policy_baseline[
        [
            "행정동",
            "노인수",
            "독거노인수",
            "노인복지시설수",
            "정책_시설부족지수",
        ]
    ].to_csv(
        output_dir / "policy_baseline.csv",
        index=False,
        encoding="utf-8-sig",
    )

    policy_scenarios.to_csv(
        output_dir / "policy_scenarios.csv",
        index=False,
        encoding="utf-8-sig",
    )

    LOG.info(
        "정책지수 시뮬레이션 완료: %d개 시나리오",
        len(policy_scenarios),
    )

    LOG.info(
        "PCA PC1 설명분산비율: %.4f (예측 정확도 아님)",
        explained,
    )

    # 8. 지도용 행정동 데이터 결합
    geo = merge_boundaries(baseline, boundaries)

    # 9. 시설 확충 시나리오 계산
    details, summary = compare_scenarios(
        baseline,
        model,
    )

    # 10. 시나리오 계산 방향 검사
    tolerance = 1e-9

    improved = int(
        (details["취약도점수개선"] > tolerance).sum()
    )

    worsened = int(
        (details["취약도점수개선"] < -tolerance).sum()
    )

    unchanged = int(
        (details["취약도점수개선"].abs() <= tolerance).sum()
    )

    LOG.info(
        "시나리오 분석: 개선 %d건, 악화 %d건, 변화 없음 %d건",
        improved,
        worsened,
        unchanged,
    )

    if worsened > 0:
        LOG.warning(
            "주의: 시설 추가 후 PCA 취약도 점수가 "
            "악화되는 시나리오 %d건 발견.",
            worsened,
        )
        LOG.warning(
            "현재 PCA 점수는 시설 투자 효과를 "
            "보장하는 지표가 아닙니다."
        )

    # 11. 분석 검증 보고서
    save_validation_report(
        baseline,
        model,
        details,
        summary,
        output_dir,
        chosen_k=k,
    )

    # 12. 분석 결과 CSV 저장
    output_files = {
        "district_scores.csv": baseline,
        "cluster_summary.csv": clusters,
        "pca_loadings.csv": loadings,
        "scenario_details.csv": details,
        "scenario_summary.csv": summary,
    }

    for filename, dataframe in output_files.items():
        dataframe.to_csv(
            output_dir / filename,
            index=(filename == "cluster_summary.csv"),
            encoding="utf-8-sig",
        )

    # 13. 지도 생성
    save_map(
        geo,
        output_dir / "vulnerability_map.html",
    )

    save_static_map(
        geo,
        output_dir / "vulnerability_map.png",
    )

    # 14. 시설 확충 시나리오 그래프
    # 악화 사례가 있으면 보고서용 정책효과로 해석하지 않습니다.
    if worsened == 0:
        save_scenario_chart(
            summary,
            output_dir / "scenario_effect.png",
        )
    else:
        stale_chart = output_dir / "scenario_effect.png"

        if stale_chart.exists():
            stale_chart.unlink()

        LOG.warning(
            "시설 확충 효과 그래프 생성을 생략했습니다. "
            "PCA 방향 문제를 먼저 검토하세요."
        )

    # 15. 실행 완료 메시지
    LOG.info(
        "분석 완료: 행정동=%d, PC1 설명분산비율=%.4f, 결과=%s",
        len(baseline),
        explained,
        output_dir,
    )

    return baseline, details


def main():
    parser = argparse.ArgumentParser(
        description="안산시 AI 복지취약도 분석"
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
    )

    parser.add_argument(
        "--clusters",
        type=int,
        default=4,
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    run(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        k=args.clusters,
    )


if __name__ == "__main__":
    main()
