# 다음 단계: 시각화 및 HTML 보고서

기존 프로젝트의 소스와 테스트를 변경하지 않는 **추가 스크립트**입니다.

## 설치

1. `scripts/report_next_stage.py`를 기존 프로젝트 `scripts/`에 복사합니다.
2. `tests/test_report_next_stage.py`를 기존 프로젝트 `tests/`에 복사합니다.
3. 기존 `data/`에 `BND_ADM_DONG_PG.{shp,shx,dbf,prj,cpg}`가 있어야 합니다.

## CMD 실행

```cmd
cd /d C:\Users\ljh\Downloads\welfare-analysis-refactored\welfare-analysis
.venv\Scripts\activate
python -m welfare_analysis.main
python scripts\next_stage.py --outputs outputs
python scripts\investment_next_stage.py --outputs outputs --budget 5
python scripts\report_next_stage.py --outputs outputs --shp data\BND_ADM_DONG_PG.shp
pytest -q
explorer outputs
```

## 추가 출력
- `outputs/allocation_maps.png`: 기준 취약도 / plain / needs 배분 지도 (행정동 경계만 있는 오프라인 지도)
- `outputs/cluster_comparison.png`: k=4 및 k=7 군집 크기
- `outputs/allocation_before_after.png`: 배분 지역의 기존 PCA 및 모형상 사후 PCA
- `outputs/analysis_report.html`: 앞의 이미지가 내장된 오프라인 HTML 보고서

지도는 외부 API/타일 사용이 없습니다. 도로 배경이 필요하다면 별도 지도 타일 공급자를 검토해야 합니다. 보고서에서 확충 효과는 PCA 모형상 점수 변화이며, 정책 효익·지리적 최적 입지를 뜻하지 않습니다.
