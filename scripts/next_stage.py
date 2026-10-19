"""군집 안정성 및 복지취약지역 TOP 5 분석 (기존 outputs 재사용).

CMD: python scripts/next_stage.py --outputs outputs
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

# 현재 프로젝트 config.py의 군집 피처와 동일한 구성
from welfare_analysis.config import CLUSTER_COLS


def check_columns(frame: pd.DataFrame, required: list[str], label: str) -> None:
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"{label} 필수 컬럼 누락: {sorted(missing)}")


def cluster_stability(districts: pd.DataFrame, k_values=range(3, 8), repeats=20) -> tuple[pd.DataFrame, pd.DataFrame]:
    """반복 초기화 결과의 ARI로 K-Means 분류 안정성 비교."""
    check_columns(districts, list(CLUSTER_COLS) + ["행정동"], "district_scores.csv")
    X = districts[list(CLUSTER_COLS)].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(X.to_numpy(dtype=float)).all():
        raise ValueError("군집 분석 입력에 NaN/무한대 값이 있습니다")
    X = StandardScaler().fit_transform(X)
    quality, members = [], []
    for k in k_values:
        if k >= len(districts):
            continue
        labels_runs = [KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(X)
                       for seed in range(repeats)]
        reference = labels_runs[0]
        ari = [adjusted_rand_score(reference, other) for other in labels_runs[1:]]
        n_groups = len(np.unique(reference))
        silhouette = float(silhouette_score(X, reference)) if 1 < n_groups < len(X) else np.nan
        group_counts = pd.Series(reference).value_counts()
        quality.append({"군집수": k, "실루엣점수": silhouette, "평균_ARI_기준시드대비": float(np.mean(ari)),
                        "최소군집크기": int(group_counts.min()), "최대군집크기": int(group_counts.max()),
                        "단일지역군집수": int((group_counts == 1).sum())})
        for dong, group in zip(districts["행정동"], reference):
            members.append({"군집수": k, "행정동": dong, "군집번호": int(group)})
    return pd.DataFrame(quality), pd.DataFrame(members)


def top_vulnerable(districts: pd.DataFrame, details: pd.DataFrame, n=5) -> pd.DataFrame:
    """기존 PCA 취약도 상위 n곳과 노인복지시설 확충 모형상 변화를 연결."""
    check_columns(districts, ["행정동", "현재순위", "PCA_복지취약도", "노인수", "독거노인수",
                              "노인천명당_복지시설합계"], "district_scores.csv")
    check_columns(details, ["행정동", "추가시설", "추가개수", "취약도점수개선", "취약도순위개선"], "scenario_details.csv")
    base = districts.nsmallest(n, "현재순위")[["행정동", "현재순위", "PCA_복지취약도", "노인수",
        "독거노인수", "노인천명당_복지시설합계"]].copy()
    extra = details[details["추가시설"] == "노인복지시설수"].copy()
    if extra.duplicated(["행정동", "추가개수"]).any():
        raise ValueError("한 행정동/추가개수에 중복 시뮬레이션이 있습니다")
    for count in (1, 2, 3):
        chunk = extra[extra["추가개수"] == count].set_index("행정동")
        base[f"{count}개_점수개선"] = base["행정동"].map(chunk["취약도점수개선"])
        base[f"{count}개_순위개선"] = base["행정동"].map(chunk["취약도순위개선"])
    if base[[f"{i}개_점수개선" for i in (1,2,3)]].isna().any().any():
        raise ValueError("TOP 5 행정동 중 누락된 시뮬레이션 결과가 있습니다")
    base["1개당_모형점수개선"] = base["1개_점수개선"]
    # 투자 비용·수용 인원·접근성 자료가 없어, 실제 비용효과나 최적입지 순위는 제공하지 않음.
    return base


def run(outputs: Path, repeats: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    districts = pd.read_csv(outputs / "district_scores.csv", encoding="utf-8-sig")
    details = pd.read_csv(outputs / "scenario_details.csv", encoding="utf-8-sig")
    stats, members = cluster_stability(districts, repeats=repeats)
    top5 = top_vulnerable(districts, details)
    stats.to_csv(outputs / "cluster_stability.csv", index=False, encoding="utf-8-sig")
    members.to_csv(outputs / "cluster_membership.csv", index=False, encoding="utf-8-sig")
    top5.to_csv(outputs / "priority_top5.csv", index=False, encoding="utf-8-sig")
    print("[완료] 군집 수별 안정성:\n", stats.to_string(index=False))
    print("\n[완료] 취약도 기준 상위 5개 행정동:\n", top5[["행정동", "현재순위", "1개_점수개선"]].to_string(index=False))
    print(f"\n결과 폴더: {outputs.resolve()}")
    return stats, top5


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--outputs", type=Path, default=Path("outputs"))
    parser.add_argument("--repeats", type=int, default=20)
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error("--repeats 는 2 이상이어야 합니다")
    run(args.outputs, args.repeats)
