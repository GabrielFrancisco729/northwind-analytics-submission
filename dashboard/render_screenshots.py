from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'warehouse'/'northwind.db'; OUT=ROOT/'outputs'; SHOTS=ROOT/'dashboard'/'screenshots'
W,H=1600,1200
BG=(244,246,250); CARD=(255,255,255); INK=(21,32,51); MUTED=(110,120,139); LINE=(223,228,236); BLUE=(59,111,216); NAVY=(31,53,97); GOOD=(31,138,99); WARN=(187,123,23); BAD=(179,75,87)
FONT_CANDIDATES = {
    False: ['DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf'],
    True: ['DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf'],
}
def f(sz,b=False):
    for candidate in FONT_CANDIDATES[b]:
        try:
            return ImageFont.truetype(candidate, sz)
        except OSError:
            pass
    return ImageFont.load_default(size=sz)

def money(x):
 x=float(x)
 return f'${x/1e6:.2f}M' if abs(x)>=1e6 else (f'${x/1e3:.0f}k' if abs(x)>=1e3 else f'${x:,.0f}')
def card(draw,box,r=14): draw.rounded_rectangle(box,r,fill=CARD,outline=LINE,width=1)
def text(draw,xy,s,size=14,color=INK,b=False,anchor=None): draw.text(xy,str(s),font=f(size,b),fill=color,anchor=anchor)
def kpi(draw,x,y,w,label,value,note='',value_color=INK):
 card(draw,(x,y,x+w,y+105)); text(draw,(x+18,y+16),label.upper(),11,MUTED,True); text(draw,(x+18,y+42),value,27,value_color,True); text(draw,(x+18,y+79),note,10,MUTED)
def pipeline(draw,df,x,y,w,h):
 card(draw,(x,y,x+w,y+h)); text(draw,(x+22,y+18),'Open growth pipeline by stage',15,INK,True); text(draw,(x+22,y+44),'New Business + Expansion · positive valued amounts',11,MUTED)
 m=df.pipeline_usd.max(); yy=y+78
 for r in df.itertuples():
  text(draw,(x+24,yy),r.stage_asof,11,INK); text(draw,(x+w-24,yy),money(r.pipeline_usd),11,INK,True,anchor='ra'); yy+=21
  draw.rounded_rectangle((x+24,yy,x+w-24,yy+9),5,fill=(237,240,245)); bw=(w-48)*r.pipeline_usd/m; draw.rounded_rectangle((x+24,yy,x+24+bw,yy+9),5,fill=BLUE); yy+=25

def arr_chart(draw,df,x,y,w,h):
 card(draw,(x,y,x+w,y+h)); text(draw,(x+22,y+18),'ARR progression',15,INK,True); text(draw,(x+22,y+44),'Month-end spot FX · billing source of record',11,MUTED)
 vals=df.arr_usd.astype(float).to_list(); lo=min(vals)*.95; hi=max(vals); px=x+58; py=y+75; pw=w-84; ph=h-115
 for frac in [0,.5,1]:
  yy=py+ph*(1-frac); draw.line((px,yy,px+pw,yy),fill=(231,235,242),width=1); text(draw,(px-8,yy),f'${(lo+(hi-lo)*frac)/1e6:.0f}M',10,MUTED,anchor='rm')
 pts=[]
 for i,v in enumerate(vals): pts.append((px+pw*i/(len(vals)-1),py+ph*(hi-v)/(hi-lo)))
 draw.line(pts,fill=BLUE,width=4,joint='curve')
 for p in pts: draw.ellipse((p[0]-4,p[1]-4,p[0]+4,p[1]+4),fill=CARD,outline=BLUE,width=2)
 labs=pd.to_datetime(df.snapshot_date).dt.strftime('%b %y').to_list()
 for i in range(0,len(labs),2): text(draw,(pts[i][0],y+h-24),labs[i],9,MUTED,anchor='ma')

def header(draw,view):
 text(draw,(42,28),'NORTHWIND ANALYTICS · TRUSTED LAYER V1',11,BLUE,True); text(draw,(42,52),'Revenue & Funnel Control Room',28,INK,True); text(draw,(42,89),'As of 2026-06-30 · Billing-sourced ARR · Commercial CRM funnel',12,MUTED)
 tx=1280; draw.rounded_rectangle((tx,37,1556,82),10,fill=(232,236,243));
 if view=='exec': draw.rounded_rectangle((tx+4,41,1416,78),8,fill=CARD); text(draw,(tx+72,59),'Executive / CRO',11,NAVY,True,anchor='mm'); text(draw,(1484,59),'Sales Manager',11,MUTED,anchor='mm')
 else: draw.rounded_rectangle((1418,41,1552,78),8,fill=CARD); text(draw,(tx+72,59),'Executive / CRO',11,MUTED,anchor='mm'); text(draw,(1484,59),'Sales Manager',11,NAVY,True,anchor='mm')

def load():
 c=sqlite3.connect(DB); k=pd.read_sql_query('select * from mart_headline_metrics',c).iloc[0]; ret=pd.read_sql_query('select * from mart_retention_metrics',c).set_index('period_name'); trend=pd.read_sql_query('select snapshot_date,sum(arr_usd) arr_usd,count(*) active_accounts from fct_arr_account_monthly group by snapshot_date order by snapshot_date',c); pipe=pd.read_sql_query('select * from mart_pipeline_by_stage order by stage_order',c); target=pd.read_sql_query('select * from mart_account_360 where targeted_reengagement_candidate=1 order by arr_usd desc',c); hier=pd.read_sql_query('''select p.account_id parent_id,p.account_name parent_name,c.account_id child_id,c.account_name child_name,coalesce(pa.arr_usd,0) parent_arr_usd,coalesce(ca.arr_usd,0) child_arr_usd,c.is_deleted child_is_deleted from dim_account c join dim_account p on c.parent_account_id=p.account_id left join mart_account_360 pa on pa.account_id=p.account_id left join mart_account_360 ca on ca.account_id=c.account_id order by parent_arr_usd+child_arr_usd desc''',c); c.close(); forecast=json.loads((OUT/'pipeline_forecast_summary.json').read_text()); eng=json.loads((OUT/'engagement_summary.json').read_text()); return k,ret,trend,pipe,target,hier,forecast,eng

def executive(k,ret,trend,pipe,target,hier,fc,eng):
 im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im);header(d,'exec'); q2=ret.loc['Q2 2026'];ttm=ret.loc['TTM']; gap=12; x0=42; kw=(1516-5*gap)/6
 vals=[('Active ARR',money(k.active_arr_usd),'296 active accounts',INK),('Q2 Net New ARR',money(q2.net_new_arr_usd),'constant 6/30 FX',GOOD),('TTM NRR',f'{ttm.nrr:.1%}',f'GRR {ttm.grr:.1%}',GOOD),('NB Win Rate',f'{k.ttm_new_business_win_rate:.1%}','126 / 490 decisions',INK),('Growth Pipeline',money(k.open_growth_pipeline_usd),'NB + Expansion',INK),('Q3 Forecast',money(fc['forecast_expected_usd']),f"P10–P90 {money(fc['forecast_p10_usd'])}–{money(fc['forecast_p90_usd'])}",WARN)]
 for i,v in enumerate(vals): kpi(d,x0+i*(kw+gap),120,kw,*v)
 d.rounded_rectangle((42,239,1558,314),12,fill=(255,248,232),outline=(240,217,169)); text(d,(60,258),'85%',29,WARN,True); text(d,(144,254),'March “engagement drop” is a telemetry incident, not a sustained customer drop.',14,INK,True); text(d,(144,279),f"Capture collapses Mar 10–31 and recovers Apr 1. Apr–Jun events/day are {eng['apr_jun_vs_jan_feb_pct']:.1f}% above Jan–Feb.",11,MUTED)
 arr_chart(d,trend,42,331,930,365); pipeline(d,pipe,990,331,568,365)
 card(d,(42,714,760,1118)); text(d,(64,735),'Retention economics',15,INK,True); text(d,(64,761),'Opening cohort · constant period-end FX',11,MUTED)
 mini=[('Q2 GRR',f'{q2.grr:.1%}'),('Q2 NRR',f'{q2.nrr:.1%}'),('Q2 Net New',money(q2.net_new_arr_usd))]
 for i,(lab,val) in enumerate(mini):
  bx=64+i*218; d.rounded_rectangle((bx,790,bx+198,875),10,fill=(247,249,252)); text(d,(bx+14,808),val,20,INK,True); text(d,(bx+14,841),lab.upper(),9,MUTED,True)
 d.rounded_rectangle((64,897,738,1077),9,fill=(255,250,240)); text(d,(82,916),'WATCH GROSS RETENTION',11,WARN,True); text(d,(82,942),f'TTM NRR is {ttm.nrr:.1%}, but TTM GRR is only {ttm.grr:.1%}.',14,INK,True); text(d,(82,970),'Expansion is masking meaningful contraction/churn.',12,MUTED); text(d,(82,1005),'This is a better leadership question than reconciling three ARR totals.',11,MUTED)
 card(d,(778,714,1558,1118)); text(d,(800,735),'Predictive artifact · Q3 growth bookings',15,INK,True); text(d,(800,762),f"Holdout AUC {fc['holdout_auc']:.3f} · Q2 dollar backtest {fc['holdout_error_pct']:.1f}%",11,MUTED); text(d,(800,815),money(fc['forecast_expected_usd']),36,WARN,True); text(d,(800,860),f"P10 {money(fc['forecast_p10_usd'])}   ·   Median {money(fc['forecast_p50_usd'])}   ·   P90 {money(fc['forecast_p90_usd'])}",12,INK); text(d,(800,905),'Use as a conservative outlook and deal-review prioritizer,',12,MUTED); text(d,(800,930),'not as a compensation or board-commit model.',12,MUTED)
 text(d,(42,1168),'Definitions: docs/METRICS.md · Data quality: docs/DATA_QUALITY.md',9,MUTED);return im

def sales(k,ret,trend,pipe,target,hier,fc,eng):
 im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im);header(d,'sales'); gap=12;x0=42;kw=(1516-5*gap)/6
 vals=[('Growth Pipeline',money(k.open_growth_pipeline_usd),'145 open / 144 valued',INK),('Q2 NB Won',money(k.q2_new_business_won_usd),'invalid win $ quarantined',INK),('NB Win Rate',f'{k.ttm_new_business_win_rate:.1%}','TTM count-based',INK),('Targeted Re-engagement',f'{len(target)} accts',money(target.arr_usd.sum())+' ARR',WARN),('Q3 Forecast',money(fc['forecast_expected_usd']),'holdout underpredicted 25.6%',INK),('Coverage','N/A','Q3 target not provided',INK)]
 for i,v in enumerate(vals): kpi(d,x0+i*(kw+gap),120,kw,*v)
 pipeline(d,pipe,42,240,730,360)
 card(d,(790,240,1558,600)); text(d,(812,260),'Accounts worth CS action now',15,INK,True); text(d,(812,286),'Post-recovery decline + Medium/High risk + contract event ≤180d',11,MUTED)
 yy=322
 text(d,(812,yy),'ACCOUNT',9,MUTED,True);text(d,(1180,yy),'ARR',9,MUTED,True);text(d,(1290,yy),'USAGE',9,MUTED,True);text(d,(1395,yy),'RISK',9,MUTED,True);text(d,(1490,yy),'EVENT',9,MUTED,True);yy+=24
 for r in target.itertuples():
  d.line((812,yy-5,1538,yy-5),fill=LINE);text(d,(812,yy),r.account_name,11,INK,True);text(d,(812,yy+17),f'{r.account_id} · {r.region}',9,MUTED);text(d,(1180,yy),money(r.arr_usd),11,INK);text(d,(1290,yy),f'{r.usage_ratio_post_vs_pre:.0%}',11,INK);text(d,(1395,yy),r.renewal_risk,10,BAD if r.renewal_risk=='High' else WARN,True);text(d,(1490,yy),f'{int(r.days_to_contract_event)}d',11,INK);yy+=56
 card(d,(42,620,1030,1118)); text(d,(64,640),'Customer relationship structure',15,INK,True); text(d,(64,666),'CRM parent → child · family ARR for context; signed retention remains at billing-account grain',11,MUTED); yy=705
 text(d,(64,yy),'PARENT',9,MUTED,True);text(d,(495,yy),'CHILD',9,MUTED,True);text(d,(875,yy),'FAMILY ARR',9,MUTED,True); yy+=24
 for r in hier.head(8).itertuples():
  d.line((64,yy-5,1008,yy-5),fill=LINE);text(d,(64,yy),r.parent_name,10,INK,True);text(d,(64,yy+16),r.parent_id,9,MUTED);text(d,(465,yy+6),'→',16,MUTED);text(d,(495,yy),r.child_name,10,INK);text(d,(495,yy+16),f"{r.child_id}{' · deleted' if r.child_is_deleted else ''}",9,MUTED);text(d,(875,yy),money(r.parent_arr_usd+r.child_arr_usd),10,INK,True);yy+=48
 card(d,(1048,620,1558,1118)); text(d,(1070,640),'Why not re-onboard everyone?',15,INK,True); text(d,(1070,670),'Daily boundary check',11,MUTED); text(d,(1070,715),'Mar 1–9',10,MUTED);text(d,(1515,715),f"{eng['pre_incident_daily_events']:,.0f}/day",13,INK,True,anchor='ra'); text(d,(1070,755),'Mar 10–31',10,MUTED);text(d,(1515,755),f"{eng['incident_daily_events']:,.0f}/day",13,BAD,True,anchor='ra'); text(d,(1070,795),'Apr 1–9',10,MUTED);text(d,(1515,795),f"{eng['post_incident_daily_events']:,.0f}/day",13,INK,True,anchor='ra'); d.rounded_rectangle((1070,845,1535,1045),9,fill=(255,248,232));text(d,(1090,865),'TELEMETRY CONCLUSION',10,WARN,True);text(d,(1090,895),f"~{eng['estimated_capture_loss_pct']:.0f}% capture loss",24,WARN,True);text(d,(1090,932),f"~{eng['estimated_missing_events_mar10_mar31']:,} missing events",11,INK);text(d,(1090,970),'Fix instrumentation first.',12,INK,True);text(d,(1090,997),'Pilot CS action only on the 4-account cohort.',11,MUTED)
 text(d,(42,1168),'One dashboard · toggle changes audience, not metric definitions',9,MUTED);return im

def main():
 SHOTS.mkdir(exist_ok=True);data=load();executive(*data).save(SHOTS/'dashboard_cro.png');sales(*data).save(SHOTS/'dashboard_sales_manager.png');print('PIL screenshots generated.')
if __name__=='__main__':main()
