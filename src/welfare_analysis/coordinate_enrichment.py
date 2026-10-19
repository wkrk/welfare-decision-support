"""Attach user-supplied geocoded facility coordinates by unambiguous identity.

Never assign a coordinate by approximate name or row order; exact normalized
name matches with duplicates resolved by exact address, otherwise leave blank.
"""
from pathlib import Path
import logging
import re
import pandas as pd

LOG=logging.getLogger(__name__)
SUPPLEMENTS={
 'medical':('의료기관_위도와경도.csv','의료기관명'),
 'senior':('사회복지시설_위도와경도.csv','시설명'),
 'welfare':('사회복지관_위도와경도.csv','사업장명'),
 'health':('보건지소_위도와경도.csv','시설명'),
 'park':('공원_위도와경도.csv','도시공원명칭'),
 'medicine':('구급약품_위도와경도.csv','판매점포명'),
}

def norm(value):
 if pd.isna(value):return ''
 return re.sub(r'\s+', '',str(value)).casefold()

def enrich_tables(tables:dict, data_dir:Path):
 for kind,(filename,namecol) in SUPPLEMENTS.items():
  path = Path(data_dir) / filename
  if not path.is_file():
   # Older exports were saved by Windows with an automatic (1) suffix.
   alternate = Path(data_dir) / filename.replace('.csv', '(1).csv')
   if alternate.is_file():
    path = alternate
   else:
    LOG.warning('좌표 보조자료 없음: %s (또는 %s)', filename, alternate.name)
    continue
  lookup=pd.read_csv(path,encoding='utf-8-sig')
  src=tables[kind].reset_index(drop=True).copy()
  lookname='시설명' if '시설명' in lookup.columns else namecol
  if namecol not in src or lookname not in lookup:
   LOG.warning('%s 시설명 컬럼이 없어 좌표 연결 건너뜀',kind);continue
  lookup=lookup.copy();lookup['_k']=lookup[lookname].map(norm)
  src['_k']=src[namecol].map(norm)
  # Connect only names uniquely identifying one facility on both sides;
  # duplicate names are NOT safely resolved by the normalized name alone.
  s_counts=src['_k'].value_counts(); l_counts=lookup['_k'].value_counts()
  uniquely_identified=src['_k'].ne('') & src['_k'].map(s_counts).eq(1) & src['_k'].map(l_counts).eq(1)
  match=lookup.drop_duplicates('_k').set_index('_k')
  src['위도']=pd.to_numeric(src.get('위도',pd.Series(index=src.index,dtype=float)),errors='coerce')
  src['경도']=pd.to_numeric(src.get('경도',pd.Series(index=src.index,dtype=float)),errors='coerce')
  for col in ('위도','경도'):
   if col in match:
    candidate=pd.to_numeric(src['_k'].map(match[col]),errors='coerce')
    src.loc[uniquely_identified & src[col].isna(),col]=candidate
  # Preserve supplied ADM_NM separately. It is not verified when lat/lon missing.
  if 'ADM_NM' in match:
   src['보조자료_행정동']=src['_k'].map(match['ADM_NM']).where(uniquely_identified)
  LOG.info('%s 보조 좌표: 원본 %d, 이름 일대일 연결 %d, 유효 좌표 %d',
           kind,len(src),int(uniquely_identified.sum()),int((src['위도'].between(33,39)&src['경도'].between(124,132)).sum()))
  tables[kind]=src.drop(columns='_k')
 return tables
