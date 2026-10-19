"""Inspect medical address mapping. Run: python scripts/inspect_medical_mapping.py path/to/file.csv"""
import argparse
from pathlib import Path
import sys
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from welfare_analysis.config import ANSAN_DONGS
from welfare_analysis.preprocessing import extract_dong, count_medical_facilities

parser = argparse.ArgumentParser()
parser.add_argument("csv", type=Path)
args = parser.parse_args()
data = pd.read_csv(args.csv, encoding="cp949")
counts, quality = count_medical_facilities(data, ANSAN_DONGS)
print(pd.Series(quality).to_string())
print("\n잠정 매핑 집계 (법정동/행정동 검증 전):")
print(counts.to_string(index=False))
from_addr = data["주소"].map(extract_dong)
from_detail = data["상세주소"].map(extract_dong)
not_mapped = from_addr.fillna(from_detail).isna()
print("\n미매핑 상세주소 예시:")
print(data.loc[not_mapped, ["주소", "상세주소"]].head(20).to_string(index=False))
