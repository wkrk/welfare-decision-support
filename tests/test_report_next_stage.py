"""기존 코드에 영향 없는 출력 로직의 독립 테스트."""
from pathlib import Path
import importlib.util
import pandas as pd
import pytest
MODULE=Path(__file__).resolve().parents[1]/'scripts'/'report_next_stage.py'
spec=importlib.util.spec_from_file_location('report_next_stage',MODULE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def test_realistic_inputs(tmp_path):
    names=[f'지역{i}' for i in range(25)]
    d=pd.DataFrame({'행정동':names,'현재순위':list(range(1,26)),'PCA_복지취약도':list(range(25,0,-1)),'독거노인수':[100]*25})
    a=pd.concat([d.assign(배분방식=m,배분시설수=[3,2]+[0]*23,모형점수개선=[.3,.2]+[0]*23) for m in ('plain','needs')])
    c=pd.concat([pd.DataFrame({'군집수':k,'군집번호':list(range(k)),'행정동수':[25-(k-1)]+[1]*(k-1),'평균취약도':[0]*k,'평균독거노인비율':[20]*k}) for k in (4,7)])
    for name,frame in [('district_scores',d),('facility_allocation',a),('cluster_profiles',c)]:frame.to_csv(tmp_path/f'{name}.csv',index=False,encoding='utf-8-sig')
    actual=mod.load_and_validate(tmp_path)
    assert len(actual[0])==25
    # 기존 실행 결과를 섞으면 차단해야 함
    a.loc[a.index[0],'PCA_복지취약도'] = -100
    a.to_csv(tmp_path/'facility_allocation.csv',index=False,encoding='utf-8-sig')
    with pytest.raises(ValueError,match='섞인'):mod.load_and_validate(tmp_path)

def test_boundaries_missing(tmp_path):
    with pytest.raises(FileNotFoundError):mod.load_boundaries(tmp_path/'missing.shp', ['사동'])
