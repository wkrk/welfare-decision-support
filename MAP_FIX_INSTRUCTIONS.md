# 배경 지도 API Access 오류 해결

## 문제 원인
이전에 생성한 `vulnerability_map.html`에 `tile.openstreetmap.org` 타일 요청이 남아 있었습니다.

## 해결
1. 이 ZIP을 압축 해제하고 수정된 `src/welfare_analysis/visualization.py`를 사용합니다.
2. 가상환경을 켠 뒤 프로젝트 루트에서 `python -m welfare_analysis.main`을 다시 실행합니다.
3. 브라우저에 열려 있던 기존 HTML 탭을 닫고 **새로 생성된** `outputs/vulnerability_map.html`을 엽니다.
4. HTML 소스에서 `L.tileLayer(` 혹은 `tile.openstreetmap.org`를 검색했을 때 없어야 합니다.

## 업로드한 현재 HTML 즉시 수정 버전
별도 제공하는 `vulnerability_map_no_api.html`은 지금 업로드한 지도를 다시 분석할 필요 없이 타일 요청만 제거한 결과입니다.
행정동 영역, 순위 및 점수는 그대로 남아 있습니다. 바탕은 연한 회색이며 실제 도로·건물 지도는 표시하지 않습니다.

Folium의 JavaScript/CSS는 여전히 CDN에서 가져올 수 있으므로 완전 무인터넷 지도가 필요하면 PNG를 사용하세요.

**별도 데이터 문제**: 업로드된 scenario_summary.csv의 평균점수개선 값은 음수입니다. 지도 타일 문제와 무관합니다. 분석 결과 및 점수 방향을 확인하기 전까지 개선 효과로 단정하지 마세요.
