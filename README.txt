적용 방법
1. scripts/next_stage.py를 기존 프로젝트의 scripts 폴더에 복사합니다.
2. 프로젝트 폴더에서 .venv\\Scripts\\activate
3. python -m welfare_analysis.main
4. python scripts/next_stage.py --outputs outputs
5. outputs/cluster_stability.csv, cluster_membership.csv, priority_top5.csv 확인

분석 결과의 주의 사항
- 7개 군집의 실루엣 점수가 가장 높더라도 작은 군집, 초기화 민감도를 함께 확인하세요.
- TOP 5는 기존 PCA 취약도 순위이며, 투자비용/주민 이동 거리 등이 반영된 최적 투자 순위가 아닙니다.
- 시설 추가 점수 개선은 모형 내 변화이며 정책 인과효과가 아닙니다.
