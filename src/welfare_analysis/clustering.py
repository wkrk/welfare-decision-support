"""K-Means cluster assignment; descriptive grouping, not ground-truth validation."""
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from .config import CLUSTER_COLS

def cluster_districts(df, k=4):
    if not 2 <= k < len(df):
        raise ValueError("군집 수 k는 2 이상, 행정동 수 미만이어야 합니다")
    x = df[list(CLUSTER_COLS)].copy()
    if not x.notna().all().all():
        raise ValueError("군집화 입력에 결측치가 있습니다")
    scaled = StandardScaler().fit_transform(x)
    model = KMeans(n_clusters=k, n_init=10, random_state=42)
    result = df.copy()
    result["cluster"] = model.fit_predict(scaled)
    return result, result.groupby("cluster")[list(CLUSTER_COLS)].mean().round(2)
