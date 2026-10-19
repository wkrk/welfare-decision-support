"""Configuration and source filenames from the supplied notebook."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
SOURCES = {
    "elder": ("경기도 안산시_노인및독거노인 인구수_20250831.csv", "utf-8-sig"),
    "medical": ("경기도 안산시_의료기관정보_20241220.csv", "cp949"),
    "senior": ("경기도 안산시_노인복지시설현황_20250923.csv", "cp949"),
    "welfare": ("경기도 안산시_사회복지관현황_20260119.csv", "cp949"),
    "health": ("경기도_안산시_보건지소등 현황_20260128.csv", "cp949"),
    "park": ("경기도 안산시_도시공원_20240901.csv", "cp949"),
    "medicine": ("경기도 안산시_안전상비의약품판매업소_20240625.csv", "cp949"),
}
BOUNDARY_FILENAME = "BND_ADM_DONG_PG.shp"
# Administrative names in the original notebook; use boundary codes to prevent namesakes in other cities.
ANSAN_DONGS = (
 "일동", "이동", "사동", "사이동", "해양동", "본오1동", "본오2동", "본오3동",
 "부곡동", "월피동", "성포동", "반월동", "안산동", "와동", "고잔동", "중앙동",
 "호수동", "원곡동", "백운동", "신길동", "초지동", "선부1동", "선부2동", "선부3동", "대부동"
)
FACILITY_COLS = ("의료기관수", "노인복지시설수", "사회복지관수", "보건시설수", "공원수", "상비약판매업소수")
# 기존 전체 시설 합계용 (다른 코드와 호환성 유지)
WELFARE_COLS = (
    "의료기관수",
    "노인복지시설수",
    "사회복지관수",
    "보건시설수",
)

# PCA 분석용: 의료기관 제외
PCA_WELFARE_COLS = (
    "노인복지시설수",
    "사회복지관수",
    "보건시설수",
)

PCA_COLS = (
    "독거노인수",
    "독거노인비율",
    "노인천명당_복지시설_의료제외",
    "노인천명당_의료기관수",
)
CLUSTER_COLS = (
    "노인수",
    "독거노인수",
    "독거노인비율",
) + tuple(
    f"노인천명당_{col}" for col in FACILITY_COLS
)