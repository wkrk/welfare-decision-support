# 실행 및 재현 안내

## 1. 준비

프로젝트 루트에서 가상환경을 준비하고
pyproject.toml 및 requirements.txt에 따른
의존성을 설치합니다.

Windows CMD:

```cmd
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m pip install pytest
```

원본 공공데이터 및 SHP 구성 파일은 data 폴더에 둡니다.
파일명과 인코딩은 config.py를 참고하세요.

## 2. PCA·군집·데이터 품질 분석

```cmd
.venv\Scripts\python.exe -m welfare_analysis.main --output-dir outputs_policy
```

이 명령은 policy_index.py가 main.py에 연결된
현재 버전을 기준으로 합니다.

## 3. 정책지수 기반 시설 배분

```cmd
.venv\Scripts\python.exe scripts\policy_allocation.py --outputs outputs_policy
```

## 4. 세 가지 배분 대안 및 보고서

```cmd
.venv\Scripts\python.exe scripts\policy_report.py --outputs outputs_policy --data-dir data
```

## 5. 포트폴리오 지도 및 문서 갱신

```cmd
.venv\Scripts\python.exe scripts\finalize_portfolio.py
```

## 6. 테스트

```cmd
.venv\Scripts\python.exe -m pytest -v
```

## 7. HTML 보고서

```cmd
start outputs_policy\policy_decision_report.html
```

주의: 기존 PCA 기반 시설 배분 스크립트의 출력은
최종 정책지수 기반 투자 결과와 구분해야 합니다.
