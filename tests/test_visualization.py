from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from welfare_analysis.visualization import save_map, save_static_map, save_scenario_chart


def test_offline_maps(tmp_path):
    geo = gpd.GeoDataFrame({
        "ADM_NM": ["A", "B"],
        "PCA_복지취약도": [0.5, 1.25],
        "현재순위": [2, 1],
        "독거노인수": [100, 200],
    }, geometry=[box(126.8, 37.3, 126.82, 37.32), box(126.82, 37.3, 126.84, 37.32)], crs="EPSG:4326")
    html, png = tmp_path / "map.html", tmp_path / "map.png"
    save_map(geo, html)
    save_static_map(geo, png)
    body = html.read_text(encoding="utf-8")
    assert "tile.openstreetmap.org" not in body
    assert "basemaps.cartocdn.com" not in body
    assert "tileLayer(" not in body
    assert "PCA_" in body and png.stat().st_size > 1000


def test_scenario_plot(tmp_path):
    path = tmp_path / "scenarios.png"
    save_scenario_chart(pd.DataFrame({"추가개수": [1, 2, 3], "평균점수개선": [0.1, 0.2, 0.3]}), path)
    assert path.stat().st_size > 1000
