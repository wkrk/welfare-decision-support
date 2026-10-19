"""Generate district-level HTML/PNG choropleths without map tile services."""
from pathlib import Path

import branca.colormap as cm
import folium
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _validated_map_data(geo):
    required = {"ADM_NM", "geometry", "PCA_복지취약도", "현재순위", "독거노인수"}
    missing = required - set(geo.columns)
    if missing:
        raise ValueError(f"지도 데이터 필수 컬럼 누락: {sorted(missing)}")
    if geo.empty or geo.geometry.isna().any():
        raise ValueError("지도 경계가 없거나 누락되어 있습니다")
    values = geo["PCA_복지취약도"].astype(float)
    if not np.isfinite(values).all():
        raise ValueError("PCA 취약도 점수에 유효하지 않은 값이 있습니다")
    if geo.crs is None:
        raise ValueError("지도 경계에 좌표계(CRS)가 없습니다")
    return geo.to_crs(epsg=4326)


def save_map(geo, filename):
    """Save self-contained district choropleth; no external tiles or API keys.

    GeoJSON, geometry, styles and labels are embedded in HTML. Folium/Leaflet
    JavaScript assets may still be served from CDNs; no background *map tile*
    requests are made. For a wholly offline view use save_static_map PNG.
    """
    geo = _validated_map_data(geo)
    scores = geo["PCA_복지취약도"].astype(float)
    minimum, maximum = float(scores.min()), float(scores.max())
    # Avoid zero-span palettes when all districts have equal scores.
    if minimum == maximum:
        minimum -= 0.5
        maximum += 0.5
    palette = cm.linear.YlOrRd_09.scale(minimum, maximum)
    palette.caption = "PCA 기반 상대적 복지취약도 (높을수록 취약)"

    # tiles=None eliminates any dependency on OpenStreetMap / CartoDB / API keys.
    m = folium.Map(location=[37.3219, 126.8309], zoom_start=11,
                   tiles=None, control_scale=True, prefer_canvas=True)
    folium.GeoJson(
        geo[["ADM_NM", "geometry", "PCA_복지취약도", "현재순위", "독거노인수"]],
        name="행정동별 복지취약도",
        style_function=lambda feature: {
            "fillColor": palette(float(feature["properties"]["PCA_복지취약도"])),
            "color": "#475569", "weight": 1.3, "fillOpacity": 0.85,
        },
        highlight_function=lambda _: {"color": "#111827", "weight": 3, "fillOpacity": 1},
        tooltip=folium.GeoJsonTooltip(
            fields=["ADM_NM", "PCA_복지취약도", "현재순위", "독거노인수"],
            aliases=["행정동", "취약도 점수", "취약도 순위", "독거노인 수"],
            localize=True,
        ),
    ).add_to(m)
    m.fit_bounds([[float(geo.total_bounds[1]), float(geo.total_bounds[0])],
                  [float(geo.total_bounds[3]), float(geo.total_bounds[2])]])
    palette.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(filename))
    html = filename.read_text(encoding="utf-8")
    if "L.tileLayer(" in html or "tile.openstreetmap.org" in html:
        raise RuntimeError("지도 HTML에 외부 배경 타일 요청이 포함되었습니다")


def save_static_map(geo, filename):
    """Create completely offline PNG map, with no API/CDN or tile access."""
    geo = _validated_map_data(geo)
    fig, ax = plt.subplots(figsize=(11, 9))
    geo.plot(column="PCA_복지취약도", cmap="YlOrRd", legend=True, ax=ax,
             edgecolor="#475569", linewidth=0.8,
             legend_kwds={"label": "PCA vulnerability score", "shrink": 0.7})
    ax.set_title("Ansan: relative welfare vulnerability by district")
    ax.set_axis_off()
    ax.set_aspect("equal")
    fig.tight_layout()
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


def save_scenario_chart(summary, filename):
    fig, ax = plt.subplots(figsize=(8, 5))
    x = summary["추가개수"].astype(int).to_numpy()
    ax.bar(x, summary["평균점수개선"].to_numpy(dtype=float))
    ax.set_xticks(x)
    ax.set_xlabel("Added facilities per district")
    ax.set_ylabel("Mean vulnerability score improvement")
    ax.set_title("One-district-at-a-time scenario comparison")
    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)
