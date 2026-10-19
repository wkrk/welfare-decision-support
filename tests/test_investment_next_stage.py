import importlib.util
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest
MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'investment_next_stage.py'
spec = importlib.util.spec_from_file_location('investment_next_stage', MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def fixtures():
    d=pd.DataFrame([{'행정동':'A','현재순위':1,'PCA_복지취약도':2.,'노인수':100,'독거노인수':20,'독거노인비율':20,'노인복지시설수':1,'노인천명당_복지시설합계':10},
      {'행정동':'B','현재순위':2,'PCA_복지취약도':1.,'노인수':100,'독거노인수':15,'독거노인비율':15,'노인복지시설수':2,'노인천명당_복지시설합계':20}])
    s=pd.DataFrame([{'행정동':dong,'추가시설':'노인복지시설수','추가개수':n,'시행전_PCA':score,'시행후_PCA':score-n*rate,'취약도점수개선':n*rate,'현재순위':rank} for dong,score,rank,rate in [('A',2.,1,.1),('B',1.,2,.2)] for n in [1,2,3]])
    return d,s

def test_baseline_and_simulation_consistent():
    d,s=fixtures()
    assert len(mod.validate_consistency(d,s))==6

def test_mixed_run_rejected():
    d,s=fixtures()
    s.loc[0,'시행전_PCA']=999
    with pytest.raises(ValueError,match='서로 다른 실행'):
        mod.validate_consistency(d,s)

def test_wrong_improvement_rejected():
    d,s=fixtures()
    s.loc[0,'취약도점수개선']=-1
    with pytest.raises(ValueError,match='산식'):
        mod.validate_consistency(d,s)

def test_exact_five_and_not_mutated():
    d,s=fixtures(); orig=d.copy(deep=True)
    a,_=mod.allocation(d,mod.validate_consistency(d,s),budget=5)
    assert a['배분시설수'].sum()==5
    assert a['배분시설수'].max()<=3
    pd.testing.assert_frame_equal(d,orig)

def test_profiles_has_all_districts():
    d,_=fixtures()
    mem=pd.DataFrame([{'행정동':dong,'군집번호':0 if dong=='A' else 1,'군집수':k} for k in (4,7) for dong in ('A','B')])
    p=mod.cluster_profiles(d,mem)
    assert p.groupby('군집수')['행정동수'].sum().to_dict()=={4:2,7:2}
