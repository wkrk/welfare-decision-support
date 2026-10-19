"""Load only configured public data and the administrative boundary file."""
from pathlib import Path
import pandas as pd
from .config import SOURCES, BOUNDARY_FILENAME

def load_tables(data_dir: Path) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir)
    results = {}
    missing = [filename for filename, _ in SOURCES.values() if not (data_dir / filename).is_file()]
    if missing:
        raise FileNotFoundError("필수 CSV 누락: " + ", ".join(missing) + "; data/README.md 참고")
    for key, (filename, encoding) in SOURCES.items():
        results[key] = pd.read_csv(data_dir / filename, encoding=encoding)
    return results

def load_boundary(data_dir: Path):
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise ImportError("지도 분석에는 geopandas가 필요합니다.") from exc
    path = Path(data_dir) / BOUNDARY_FILENAME
    if not path.exists():
        raise FileNotFoundError(f"행정동 SHP 누락: {path} (관련 .shx/.dbf/.prj 파일도 필요)")
    return gpd.read_file(path, encoding="cp949")
