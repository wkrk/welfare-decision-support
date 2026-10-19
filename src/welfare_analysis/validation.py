"""Independent diagnostics for PCA, K-Means and counterfactual scenarios.

These checks do not silently change PCA scores or turn negative effects positive.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .config import CLUSTER_COLS, PCA_COLS


def evaluate_cluster_counts(districts: pd.DataFrame, k_min: int = 2, k_max: int = 8) -> pd.DataFrame:
    """Compute silhouette for several k values using same features as cluster_districts."""
    if len(districts) < 4:
        raise ValueError("군집 수 비교에는 최소 4개 행정동이 필요합니다")
    x = districts[list(CLUSTER_COLS)].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(x.to_numpy(dtype=float)).all():
        raise ValueError("군집 입력에 결측 또는 무한대가 있습니다")
    standardized = StandardScaler().fit_transform(x)
    candidates = range(max(2, k_min), min(k_max, len(districts) - 1) + 1)
    results = []
    for k in candidates:
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(standardized)
        actual_k = len(np.unique(labels))
        results.append({"군집수": k, "실제군집수": actual_k,
                        "실루엣점수": float(silhouette_score(standardized, labels)) if 2 <= actual_k < len(districts) else np.nan})
    return pd.DataFrame(results)


def evaluate_pca_direction(model) -> pd.DataFrame:
    """원본 변수의 1단위 증가가 PCA 점수에 미치는 방향 계산"""

    facility_features = {
        "노인천명당_복지시설_의료제외",
        "노인천명당_의료기관수",
    }

    signs = np.array([
        -1.0 if col in facility_features else 1.0
        for col in PCA_COLS
    ])

    coefficients = (
        model.pca.components_[0]
        * model.orientation
        * signs
        / model.scaler.scale_
    )

    return pd.DataFrame({
        "변수": list(PCA_COLS),
        "원본단위당취약도변화": coefficients,
        "증가시취약도": np.where(
            coefficients > 1e-12,
            "증가",
            np.where(coefficients < -1e-12, "감소", "불변"),
        ),
    })

def evaluate_scenarios(details: pd.DataFrame, summary: pd.DataFrame, tolerance: float = 1e-9) -> pd.DataFrame:
    """Check exact arithmetic, including whether adding facilities worsens PCA score."""
    required = {"추가개수", "시행전_PCA", "시행후_PCA", "취약도점수개선", "현재순위", "시행후순위", "취약도순위개선"}
    missing = required - set(details.columns)
    if missing:
        raise ValueError(f"시나리오 필수 컬럼 누락: {sorted(missing)}")
    score_delta = details["시행전_PCA"] - details["시행후_PCA"]
    rank_delta = details["시행후순위"] - details["현재순위"]
    if not np.allclose(details["취약도점수개선"], score_delta, atol=tolerance, rtol=0):
        raise ValueError("시나리오 취약도점수개선 계산이 시행전-시행후와 다릅니다")
    if not np.allclose(details["취약도순위개선"], rank_delta, atol=tolerance, rtol=0):
        raise ValueError("시나리오 순위개선 계산이 시행후순위-현재순위와 다릅니다")
    if details.empty:
        raise ValueError("시나리오 분석 결과가 없습니다")
    grouped = details.groupby("추가개수", as_index=False).agg(
        시나리오수=("취약도점수개선", "size"),
        평균점수개선=("취약도점수개선", "mean"),
        점수개선지역수=("취약도점수개선", lambda s: int((s > tolerance).sum())),
        점수악화지역수=("취약도점수개선", lambda s: int((s < -tolerance).sum())),
        점수변화없음=("취약도점수개선", lambda s: int((s.abs() <= tolerance).sum())),
        평균순위개선=("취약도순위개선", "mean"),
        순위개선지역수=("취약도순위개선", lambda s: int((s > 0).sum())),
    )
    if "평균점수개선" in summary and "추가개수" in summary:
        merged = grouped.merge(summary[["추가개수", "평균점수개선"]], on="추가개수", suffixes=("_재계산", "_기존"), validate="one_to_one")
        if len(merged) != len(grouped) or not np.allclose(merged["평균점수개선_재계산"], merged["평균점수개선_기존"], atol=tolerance, rtol=0):
            raise ValueError("시나리오 요약 평균이 상세 데이터와 일치하지 않습니다")
    return grouped


def save_validation_report(districts, model, details, summary, output_dir, chosen_k=4):
    """Write diagnostic CSVs and a report without modifying the original analysis."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    clusters = evaluate_cluster_counts(districts)
    directions = evaluate_pca_direction(model)
    scenarios = evaluate_scenarios(details, summary)
    for filename, data in {
        "validation_cluster_k.csv": clusters,
        "validation_pca_direction.csv": directions,
        "validation_scenarios.csv": scenarios,
    }.items():
        data.to_csv(output / filename, index=False, encoding="utf-8-sig")
    best = clusters.dropna(subset=["실루엣점수"]).sort_values("실루엣점수", ascending=False)
    best_k = int(best.iloc[0]["군집수"]) if len(best) else None
    n_worse = int(scenarios["점수악화지역수"].sum())
    lines = [
        "# 분석 검증 보고서", "",
        f"- 기존 군집 수: {chosen_k}",
        f"- 실루엣 최고 군집 수: {best_k if best_k is not None else '산출 불가'} (참고용; 반드시 이 k를 선택할 필요는 없음)",
        f"- PCA PC1 설명분산비율: {model.pca.explained_variance_ratio_[0]:.4f} (예측 정확도 아님)",
        f"- 점수 악화 시나리오 수: {n_worse}건 (음수를 임의로 양수 처리하지 않음)",
        "- 순위가 동일하더라도 점수는 개선될 수 있습니다.",
        "- 잠정 매핑 및 미매핑 시설이 있어 원자료 검증이 필요합니다.",
        "- PCA는 정책 타당성/효과의 인과적 증거가 아닙니다.", "",
        "시설 관련 두 변수의 '증가시 취약도'가 감소가 아닌 경우, PC1만으로 시설 추가 효과를 해석하지 마세요.",
    ]
    (output / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return clusters, directions, scenarios
