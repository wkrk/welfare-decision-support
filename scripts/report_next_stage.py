"""기존 outputs의 검증된 분석 결과로 정적 지도·그림·단일 HTML 보고서를 작성한다.

실행: python scripts/report_next_stage.py --outputs outputs --shp data/BND_ADM_DONG_PG.shp
외부 웹 타일/API 요청 없음. 시설 확충 효과는 PCA 모형 내부의 반사실적 점수 변화이다.
"""
from __future__ import annotations

import argparse
import base64
from html import escape
from pathlib import Path
from io import BytesIO

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_and_validate(outputs: Path):
    def read(name):
        path=outputs/name
        if not path.is_file():
            raise FileNotFoundError(f'{path} 없음. 기존 분석 단계를 먼저 실행하세요.')
        return pd.read_csv(path, encoding='utf-8-sig')

    districts = read('district_scores.csv')
    allocation = read('facility_allocation.csv')
    clusters = read('cluster_profiles.csv')
    required_d = {'행정동','현재순위','PCA_복지취약도','독거노인수'}
    required_a = {'행정동','현재순위','PCA_복지취약도','배분방식','배분시설수','모형점수개선'}
    required_c = {'군집수','군집번호','행정동수','평균취약도','평균독거노인비율'}
    for frame, cols, name in [(districts,required_d,'district_scores.csv'), (allocation,required_a,'facility_allocation.csv'), (clusters,required_c,'cluster_profiles.csv')]:
        missing=cols-set(frame.columns)
        if missing: raise ValueError(f'{name}: 누락 컬럼 {sorted(missing)}')
    if len(districts)!=25 or districts.행정동.isna().any() or districts.행정동.duplicated().any():
        raise ValueError('district_scores.csv: 25개 고유 행정동이어야 합니다.')
    if set(allocation.배분방식) != {'plain','needs'}:
        raise ValueError('배분방식은 plain 및 needs 각각 있어야 합니다.')
    for mode, sub in allocation.groupby('배분방식'):
        if len(sub)!=25 or sub.행정동.duplicated().any() or set(sub.행정동)!=set(districts.행정동):
            raise ValueError(f'{mode}: 행정동 25개가 모두 포함되어야 합니다.')
        expected=sub.merge(districts[['행정동','PCA_복지취약도','현재순위']],on='행정동',suffixes=('_배분','_원본'),validate='one_to_one')
        if not np.allclose(expected['PCA_복지취약도_배분'],expected['PCA_복지취약도_원본'],rtol=0,atol=1e-6):
            raise ValueError(f'{mode}: 현재 PCA 점수가 달라 서로 다른 실행 결과가 섞인 것으로 보입니다.')
        if not (expected['현재순위_배분']==expected['현재순위_원본']).all():
            raise ValueError(f'{mode}: 순위가 달라 서로 다른 실행 결과가 섞였습니다.')
        if not np.isfinite(sub[['배분시설수','모형점수개선']].to_numpy(dtype=float)).all():
            raise ValueError(f'{mode}: 결측/무한대가 있습니다.')
        if not np.allclose(sub.배분시설수,sub.배분시설수.round()) or sub.배분시설수.lt(0).any() or sub.배분시설수.gt(3).any():
            raise ValueError(f'{mode}: 시설 수는 0~3 사이 정수이어야 합니다.')
        if int(sub.배분시설수.sum())!=5:
            raise ValueError(f'{mode}: 시설 총 5개가 아닙니다. 예산 5인 결과로 다시 실행하세요.')
        if (sub.loc[sub.배분시설수.eq(0),'모형점수개선'].abs()>1e-8).any():
            raise ValueError(f'{mode}: 시설 0개 배정 지역에 개선점수가 있습니다.')
        if sub.모형점수개선.lt(-1e-8).any():
            raise ValueError(f'{mode}: 악화 시나리오가 포함되어 별도 검토가 필요합니다.')
    if not clusters.군집수.isin([4,7]).all() or set(clusters.군집수)!={4,7}:
        raise ValueError('군집 특성 파일에 k=4 및 k=7이 필요합니다.')
    for k, group in clusters.groupby('군집수'):
        if group.군집번호.duplicated().any() or int(group.행정동수.sum())!=25:
            raise ValueError(f'k={k} 군집 행정동 수 합이 25가 아닙니다.')
    return districts, allocation, clusters


def load_boundaries(shp: Path, names):
    if not shp.is_file(): raise FileNotFoundError(f'SHP 없음: {shp}')
    geo=gpd.read_file(shp)
    if not {'ADM_CD','ADM_NM','geometry'}.issubset(geo.columns):
        raise ValueError('행정동 SHP에 ADM_CD, ADM_NM, geometry 필수')
    # 원본 자료에서 안산시 행정동으로 확인한 ADM_CD 접두값
    geo=geo[geo.ADM_CD.astype(str).str.startswith('3109')].copy()
    if len(geo)!=25 or geo.ADM_NM.duplicated().any() or set(geo.ADM_NM)!=set(names):
        raise ValueError('SHP에서 안산시 25개 행정동을 정확히 찾지 못했습니다. 경계 버전 확인 필요')
    if geo.crs is None: raise ValueError('SHP 좌표계 정보가 없습니다.')
    return geo.to_crs('EPSG:4326')


def set_korean_font():
    from matplotlib import font_manager
    available={font.name for font in font_manager.fontManager.ttflist}
    for n in ('Malgun Gothic','NanumGothic','Noto Sans CJK KR','Noto Sans KR','AppleGothic'):
        if n in available:
            plt.rcParams['font.family']=n;break
    plt.rcParams['axes.unicode_minus']=False


def save_maps(districts, allocations, geo, target):
    base=geo.merge(districts[['행정동','PCA_복지취약도','현재순위']],left_on='ADM_NM',right_on='행정동',validate='one_to_one')
    fig,axs=plt.subplots(1,3,figsize=(18,7),layout='constrained')
    base.plot(column='PCA_복지취약도',cmap='YlOrRd',edgecolor='#555',linewidth=.5,legend=True,ax=axs[0],legend_kwds={'shrink':.6})
    axs[0].set_title('현재 PCA 취약도 (높을수록 취약)')
    for idx, mode in [(1,'plain'),(2,'needs')]:
        one=allocations[allocations.배분방식.eq(mode)]
        merged=geo.merge(one[['행정동','배분시설수']],left_on='ADM_NM',right_on='행정동',validate='one_to_one')
        merged.plot(column='배분시설수',cmap='YlGnBu',vmin=0,vmax=3,edgecolor='#555',linewidth=.5,ax=axs[idx],legend=True,legend_kwds={'shrink':.6})
        selected=merged[merged.배분시설수.gt(0)]
        for _,r in selected.iterrows():
            point=r.geometry.representative_point()
            axs[idx].text(point.x,point.y,f"{r.ADM_NM}\n+{int(r.배분시설수)}",ha='center',va='center',fontsize=8,fontweight='bold',color='black',bbox={'facecolor':'white','alpha':.80,'edgecolor':'none','pad':1})
        axs[idx].set_title(('점수 개선 최대화' if mode=='plain' else '취약도 가중치 적용')+' (시설 5개)')
    for ax in axs: ax.set_axis_off()
    fig.suptitle('안산시 행정동별 취약도와 시설 배분 비교 — 경계 지도(도로 배경 없음)', fontsize=15)
    path=target/'allocation_maps.png';fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white');plt.close(fig)
    return path


def save_cluster_chart(clusters,target):
    fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    for ax,k in zip(axs,[4,7]):
        sub=clusters[clusters.군집수.eq(k)].sort_values('군집번호')
        x=np.arange(len(sub))
        ax.bar(x,sub.행정동수,color=plt.cm.Set2(np.linspace(0,1,len(sub))))
        ax.set_xticks(x,[f'군집 {v}' for v in sub.군집번호]);ax.set_ylabel('행정동 수');ax.set_title(f'K-Means k={k} 군집 규모')
        for i,v in enumerate(sub.행정동수): ax.text(i,v+.10,str(int(v)),ha='center',fontsize=9)
        ax.set_ylim(0,max(2,sub.행정동수.max()*1.15))
        ax.tick_params(axis='x',rotation=35)
    path=target/'cluster_comparison.png';fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white');plt.close(fig)
    return path


def save_before_after(allocations,target):
    chosen=allocations[allocations.배분시설수.gt(0)].copy()
    chosen['모형상_사후PCA']=chosen['PCA_복지취약도']-chosen['모형점수개선']
    n=len(chosen);xs=np.arange(n)
    fig,ax=plt.subplots(figsize=(max(9,n*1.25),5),layout='constrained')
    ax.bar(xs-.2,chosen['PCA_복지취약도'],width=.4,label='기준 PCA')
    ax.bar(xs+.2,chosen['모형상_사후PCA'],width=.4,label='시설 추가 후 PCA (모형)')
    ax.set_xticks(xs,[f'{m}\n{n} +{int(v)}개' for m,n,v in zip(chosen.배분방식,chosen.행정동,chosen.배분시설수)])
    ax.axhline(0,color='black',linewidth=.6)
    ax.set_ylabel('PCA 취약도 점수')
    ax.set_title('선정 지역별 시설 배분 전후 모형상 점수 비교')
    ax.legend();ax.grid(axis='y',alpha=.2)
    path=target/'allocation_before_after.png';fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white');plt.close(fig)
    return path


def build_report(districts,allocations,clusters,images,target):
    def png_inline(path):
        return 'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode('ascii')
    total=allocations.groupby('배분방식',sort=False).agg(추가시설=('배분시설수','sum'),개선합=('모형점수개선','sum'))
    rows=[]
    for _,r in allocations[allocations.배분시설수.gt(0)].iterrows():
        rows.append(f"<tr><td>{escape(str(r['배분방식']))}</td><td>{escape(str(r['행정동']))}</td><td>{int(r['배분시설수'])}</td><td>{r['PCA_복지취약도']:.4f}</td><td>{r['모형점수개선']:.6f}</td></tr>")
    summary=''.join(f'<tr><td>{escape(str(m))}</td><td>{int(row.추가시설)}</td><td>{row.개선합:.6f}</td></tr>' for m,row in total.iterrows())
    imgs=''.join(f'<section><h2>{escape(title)}</h2><img alt="{escape(title)}" src="{png_inline(path)}"></section>' for title,path in images)
    html=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>안산시 취약지역 및 시설 배분 비교</title><style>
body{{font-family:Arial,'Malgun Gothic',sans-serif;margin:0;background:#f5f7fa;color:#263044;line-height:1.65}} main{{max-width:1160px;margin:auto;padding:28px}} h1{{margin-top:0}}section{{background:white;border:1px solid #e0e5ee;border-radius:14px;padding:22px;margin:20px 0}}img{{width:100%;height:auto}} table{{border-collapse:collapse;width:100%}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #e5e9f1}}th{{background:#eef2f7}}.muted{{color:#637084}}.notice{{border-left:4px solid #aa7a2a;padding:10px 15px;background:#fff9e9}}
</style></head><body><main><h1>안산시 복지취약지역 분석과 시설 배분 시나리오</h1><p class="muted">분석 대상: {len(districts)}개 행정동 · 배분 시설 총량: 방식별 5개</p>
<section><h2>시설 배분 방식별 집계</h2><table><thead><tr><th>방식</th><th>총 시설 수</th><th>모형 점수 개선 합</th></tr></thead><tbody>{summary}</tbody></table></section>
{imgs}
<section><h2>시설 배분 상세</h2><table><thead><tr><th>방식</th><th>행정동</th><th>추가 시설</th><th>기준 PCA</th><th>모형 점수 개선</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section><h2>중요한 해석 한계</h2><div class="notice">본 보고서의 '시설 추가 효과'는 동일한 PCA 모형에서 계산한 점수 변화입니다. 건립 비용, 주민 이동거리, 이용자 수용량, 인접 지역 영향, 실제 복지 효과를 추정하지 않습니다. 잠정 매핑 및 미매핑 자료가 포함된 입력 데이터를 활용하며, 결과는 실제 투자 권고가 아닙니다.</div><p>지도는 SHP 경계로 생성한 오프라인 이미지입니다. 도로·건물 배경지도나 외부 API 호출은 사용하지 않았습니다.</p></section></main></body></html>'''
    path=target/'analysis_report.html';path.write_text(html,encoding='utf-8');return path


def run(outputs: Path,shp: Path):
    outputs=Path(outputs);outputs.mkdir(parents=True,exist_ok=True)
    districts,allocation,profiles=load_and_validate(outputs)
    geo=load_boundaries(Path(shp),districts.행정동)
    set_korean_font()
    images=[('안산시 취약도·시설 배분 지도',save_maps(districts,allocation,geo,outputs)),('군집 규모 비교',save_cluster_chart(profiles,outputs)),('배분 전후 취약도 점수',save_before_after(allocation,outputs))]
    path=build_report(districts,allocation,profiles,images,outputs)
    print('[완료] '+str(path))
    for _,p in images:print('[완료] '+str(p))
    return path

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--outputs',type=Path,default=Path('outputs'));p.add_argument('--shp',type=Path,default=Path('data/BND_ADM_DONG_PG.shp'))
    a=p.parse_args();run(a.outputs,a.shp)
