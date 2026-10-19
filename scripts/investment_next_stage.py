"""군집 특성 + 시설 총 5개 배분 시나리오. CMD: python scripts/investment_next_stage.py --outputs outputs

주의: PCA 점수 변화는 실제 접근성/경제적 가치가 아닌 모형 내부의 반사실적 변화.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

NEEDED_DISTRICT = ['행정동','현재순위','PCA_복지취약도','노인수','독거노인수','독거노인비율','노인복지시설수','노인천명당_복지시설합계']
NEEDED_SCENARIO = ['행정동','추가시설','추가개수','시행전_PCA','시행후_PCA','취약도점수개선','현재순위']


def require(frame, fields, fname):
    missing = sorted(set(fields).difference(frame.columns))
    if missing:
        raise ValueError(f'{fname}: 필요한 컬럼 없음: {missing}')


def validate_consistency(districts, details):
    require(districts, NEEDED_DISTRICT, 'district_scores.csv')
    require(details, NEEDED_SCENARIO, 'scenario_details.csv')
    if districts['행정동'].duplicated().any():
        raise ValueError('행정동 중복 데이터')
    if not np.isfinite(districts[['현재순위','PCA_복지취약도','노인수','독거노인수']].to_numpy(dtype=float)).all():
        raise ValueError('행정동 정보에 NaN/무한대 존재')
    if (districts['현재순위'] != districts['PCA_복지취약도'].rank(ascending=False,method='min')).any():
        raise ValueError('현재순위와 취약도 점수 방향이 일치하지 않음')
    welfare = details[details['추가시설'].eq('노인복지시설수')].copy()
    if welfare.empty or welfare.duplicated(['행정동','추가개수']).any():
        raise ValueError('노인복지시설 시나리오가 없거나 중복됨')
    if not set(welfare['행정동']).issubset(set(districts['행정동'])):
        raise ValueError('시나리오 행정동이 원본과 일치하지 않음')
    joined = welfare.merge(districts[['행정동','현재순위','PCA_복지취약도']], on='행정동',suffixes=('_시나리오','_기준'),validate='many_to_one')
    if not np.allclose(joined['시행전_PCA'],joined['PCA_복지취약도'],atol=1e-6):
        raise ValueError('서로 다른 실행의 district_scores와 scenario_details가 혼합된 것으로 보입니다 (기준점수 불일치)')
    if not (joined['현재순위_시나리오']==joined['현재순위_기준']).all():
        raise ValueError('서로 다른 실행의 파일로 보입니다 (기준 순위 불일치)')
    if not np.allclose(joined['시행전_PCA']-joined['시행후_PCA'],joined['취약도점수개선'],atol=1e-7):
        raise ValueError('시뮬레이션의 점수 개선 산식이 맞지 않음')
    return welfare


def cluster_profiles(districts, members, ks=(4,7)):
    require(members,['행정동','군집번호','군집수'],'cluster_membership.csv')
    if members.duplicated(['행정동','군집수']).any():
        raise ValueError('군집 소속 중복')
    frames=[]
    for k in ks:
        chunk=members[members['군집수']==k]
        if len(chunk)!=len(districts) or set(chunk['행정동'])!=set(districts['행정동']):
            raise ValueError(f'k={k} 군집 소속 데이터가 전체 25개 행정동과 일치하지 않습니다')
        merged=chunk.merge(districts,on='행정동',validate='one_to_one')
        grouped=merged.groupby('군집번호').agg(
          행정동수=('행정동','size'), 행정동목록=('행정동',lambda v:', '.join(sorted(v))),
          평균취약도=('PCA_복지취약도','mean'), 평균독거노인비율=('독거노인비율','mean'),
          총독거노인수=('독거노인수','sum'), 평균노인천명당복지시설=('노인천명당_복지시설합계','mean')
        ).reset_index()
        grouped.insert(0,'군집수',k)
        frames.append(grouped)
    return pd.concat(frames,ignore_index=True)


def allocation(districts, welfare, budget=5, max_per_dong=3, weight_mode='plain'):
    """동별 전/후 기준모형 고정된 일회성 반사실 결과로 DP 배분.
    동 간 간섭/전체 재학습 없음, 효과 가산성 가정 필요.
    """
    if not 1 <= budget <= len(districts)*max_per_dong:
        raise ValueError('배분 시설 총수가 잘못되었습니다')
    districts = districts.sort_values('행정동').reset_index(drop=True)
    options=[]
    for _,dong in districts.iterrows():
        sub=welfare[welfare['행정동']==dong['행정동']].set_index('추가개수')
        vals=[0.0]
        for n in range(1,max_per_dong+1):
            if n not in sub.index:
                raise ValueError(f"{dong['행정동']}: 시설 {n}개 시나리오 없음")
            v=float(sub.loc[n,'취약도점수개선'])
            if not np.isfinite(v):
                raise ValueError('점수 개선량에 유효하지 않은 값')
            vals.append(v)
        # 'needs' mode: 의사결정 가중치 설정 가정, 정책적 검증되지 않음.
        weight = 1.0 if weight_mode=='plain' else 1.0 + max(0.0,float(dong['PCA_복지취약도']))
        options.append([(v*weight) for v in vals])
    dp=[(-float('inf'),[]) for _ in range(budget+1)]
    dp[0]=(0.0,[])
    for opts in options:
        nxt=[(-float('inf'),[]) for _ in range(budget+1)]
        for used,(score,plan) in enumerate(dp):
            if not np.isfinite(score): continue
            for n,gain in enumerate(opts):
                if used+n<=budget and score+gain>nxt[used+n][0]+1e-12:
                    nxt[used+n]=(score+gain,plan+[n])
        dp=nxt
    score, plan=dp[budget]
    result=districts[['행정동','현재순위','PCA_복지취약도','노인수','독거노인수']].copy()
    result['배분시설수']=plan
    improvement_lookup={(r['행정동'],int(r['추가개수'])):float(r['취약도점수개선']) for _,r in welfare.iterrows()}
    result['모형점수개선']=[improvement_lookup.get((dong,int(n)),0.0) for dong,n in zip(result['행정동'],plan)]
    result['모형점수개선_가중합기여']=[options[i][n] for i,n in enumerate(plan)]
    result['배분방식']=weight_mode
    assert result['배분시설수'].sum()==budget
    return result,score


def run(outputs, budget=5):
    outputs=Path(outputs)
    district=pd.read_csv(outputs/'district_scores.csv',encoding='utf-8-sig')
    details=pd.read_csv(outputs/'scenario_details.csv',encoding='utf-8-sig')
    members=pd.read_csv(outputs/'cluster_membership.csv',encoding='utf-8-sig')
    welfare=validate_consistency(district,details)
    profile=cluster_profiles(district,members)
    profile.to_csv(outputs/'cluster_profiles.csv',index=False,encoding='utf-8-sig')
    all_results=[]
    for mode in ['plain','needs']:
        res,score=allocation(district,welfare,budget,weight_mode=mode)
        all_results.append(res)
    allocation_df=pd.concat(all_results,ignore_index=True)
    allocation_df.to_csv(outputs/'facility_allocation.csv',index=False,encoding='utf-8-sig')
    report=[f'# 시설 {budget}개 배분 시나리오 보고서','',
    '- 이는 실제 최적 입지 또는 예산 최적화가 아닌 **기존 PCA 모형의 점수 변화**를 합산한 가상 배분입니다.',
    '- 동일한 행정동에 0~3개까지 배분하는 것으로 제한합니다.',
    '- **plain**: 점수 개선량 합계 최대화. **needs**: 점수 개선량 × (1+max(0, 기준 취약도점수))를 최대화하는 임의 정책 가중치입니다.',
    '- 시설 증설 단가, 수용인원, 지리적 이동거리, 동 간 서비스 이동을 반영하지 않았습니다.',
    '- 좌표 잠정 매핑 및 미매핑 시설의 영향을 포함합니다. 결과는 투자 권고가 아닙니다.','']
    for mode in ['plain','needs']:
        p=allocation_df[(allocation_df['배분방식']==mode)&(allocation_df['배분시설수']>0)]
        report.extend([f'## {mode} 배분', '',f"- 총 추가 시설: {int(p['배분시설수'].sum())}개",f"- 모형 점수 개선 합: {p['모형점수개선'].sum():.6f}", ''])
        report += [f"- {r['행정동']}: {int(r['배분시설수'])}개 (점수 개선 {r['모형점수개선']:.6f})" for _,r in p.iterrows()]
        report.append('')
    (outputs/'investment_scenario_report.md').write_text('\n'.join(report),encoding='utf-8')
    print('[완료] cluster_profiles.csv, facility_allocation.csv, investment_scenario_report.md')
    print(allocation_df[allocation_df['배분시설수']>0][['배분방식','행정동','배분시설수','모형점수개선']].to_string(index=False))
    return profile,allocation_df

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--outputs',type=Path,default=Path('outputs'))
    parser.add_argument('--budget',type=int,default=5)
    args=parser.parse_args()
    run(args.outputs,args.budget)
