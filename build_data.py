"""Reproducible manual curve transcription. Units: m, m3/h, pump rpm, kW.
Graph knots are approximate readings, NOT manufacturer numerical test data.
Edit here and run this script to rebuild the reviewable JSON and CSV datasets.
"""
from pathlib import Path
import json,csv,copy
ROOT=Path(__file__).resolve().parent
pumps=[]
def add(name,brand,hmax,col,shaft,torque,source,rpms,heads,flows,powers,pheads=None,prpms=None,bore=None,notes='',quality='graphical approximation'):
    p={'name':name,'brand':brand,'max_head_m':hmax,'nominal_column_mm':col,'shaft_mm':shaft,'starting_torque_nm':torque,'minimum_bore_mm':bore,'source':source,'quality':quality,'notes':notes,'flow_curves':[],'power_curves':[]}
    for rpm,qs in zip(rpms,flows):p['flow_curves'].append({'rpm':rpm,'head_m':heads,'flow_m3h':qs})
    for rpm,ps in zip(prpms or rpms,powers):p['power_curves'].append({'rpm':rpm,'head_m':pheads or heads,'power_kw':ps})
    pumps.append(p);return p
h=[0,30,60,90,120,150]
# Mono / Orbit: independently inspected manufacturer sheets. Common digitised
# shapes are explicitly reused only where the inspected sheets agree.
q16=[[5.3,4.8,4.4,4.0,3.6,3.3],[7.6,7.1,6.6,6.2,5.8,5.4],[9.9,9.5,9,8.5,8.1,7.7],[12.1,11.7,11.3,10.8,10.3,9.9],[14.4,13.9,13.5,13,12.6,12.2],[16.6,16.1,15.8,15.5,15,14.7]]
p16=[[.6,2.6],[.8,3.6],[1,4.7],[1.3,5.8],[1.6,6.8],[1.8,7.9]]
add('BP16M','Mono',150,65,19,30,'sources/bp16m.png',[500,700,900,1100,1300,1500],h,q16,p16,[0,150])
q23=[[7,6.7,6.4,6,5.2,4.3],[10.9,10.6,10.2,9.7,8.8,7.7],[15,14.7,14.3,13.9,13.2,12],[19,18.7,18.3,17.8,17,16],[23,22.9,22.5,22,21.3,20.5]]
p23=[[.7,3.3],[1.2,5.2],[1.7,7],[2.3,9],[2.7,11]]
add('BP23M','Mono',150,65,19,22,'sources/bp23m.png',[500,750,1000,1250,1500],h,q23,p23,[15,150])
add('GW1302','Orbit',150,65,19,22,'sources/gw1302.png',[500,750,1000,1250,1500],h,q23,p23,[15,150])
add('BP40M','Mono',150,80,22,27,'sources/bp40m.png',[500,700,900,1100,1300,1450],[0,75,150],[[12.2,8.9,4.5],[17,12.9,8.8],[22,18.4,14.5],[27,23.2,19],[32.1,28.4,24.3],[36,32.2,28.6]],[[.5,6.1],[.8,8.6],[1.2,11],[1.5,13.6],[1.9,16],[2.1,18.3]],[0,150])
q50=[[26,23.8,21.7,19.4,16.7,13.7],[34,31.7,29.7,27.2,24.1,22],[42,39.6,37.2,34.7,31.9,29],[50,47.2,45,42.5,40,37]]
p50=[[1,12.5],[1.3,16],[1.6,19.5],[2,23]]
add('BP50M','Mono',150,100,22,36,'sources/bp50m.png',[700,900,1100,1300],h,q50,p50,[0,150])
add('BP50H','Mono',300,100,22,50,'sources/bp50h.png',[500,700,900,1100,1300],[0,75,150,225,300],[[19.2,18.7,17.3,15,11.9],[27,26.5,25,22.8,19.7],[34.7,34.2,33,30.7,27.3],[42.3,41.8,40.5,38.4,35],[50,49.5,48.3,46,42.8]],[[1.5,18.7],[2,26],[2.7,33.8],[3.2,41],[3.8,48.5]],[0,300])
q65=[[17.2,16.6,15.5,13,9.8,6.2],[28.5,27.5,26.3,23.7,20,15.7],[40,39,38,35.7,32,29],[51.2,50,49,46.8,43.5,40],[62.5,61.4,60.3,58,55,52]]
p65=[[.7,9],[1.2,14],[1.9,19],[2.4,24.6],[2.9,29.8]]
add('BP65M','Mono',150,100,22,44,'sources/bp65m.png',[300,500,700,900,1100],h,q65,p65,[0,150])
q90=[[21,20.2,19,17.7,15,12],[44,43,41.8,39.3,36,32],[69.5,68.5,67,65,62.8,60],[92.5,91.5,90.5,89,86.5,84]]
p90=[[1.8,9.8],[2.2,22],[2.8,34],[3.4,47]]
for name,brand in [('BP90M','Mono'),('GW9002','Orbit')]:add(name,brand,150,100,25,42,'sources/'+name.lower()+'.png',[250,500,750,1000],h,q90,p90,[0,150])
add('GW25002','Orbit',150,150,40,160,'sources/gw25002.png',[250,500,750],h,[[57,54,50,44,34,20],[122,120,116,108,97,85],[185,182,178,172,162,150]],[[7,38],[12,69],[18,97]],[10,150],bore=250,notes='150 mm / 40 mm configuration. Other sheet permits 125 mm / 32 mm; not in this app.')
add('GW1306','Orbit',400,65,19,50,'sources/gw1306.jpg',[200,400,600,800,1000,1200],[0,100,200,300,400],[[2.5,2.4,2.3,2,1.7],[5,4.9,4.7,4.4,4],[7.7,7.6,7.4,7.2,7],[10.5,10.3,10.1,10,9.7],[13.2,13,12.9,12.8,12.6],[15.6,15.4,15.3,15.1,15]],[[1,5],[1.8,8.5],[2.6,12.2],[3.5,16],[4.2,20],[5,24]],[40,400],notes='Chart extent 400 m used as calculation limit, not independently certified rating. Above 200 m use 80 mm column / 22 mm shaft.')
add('GW2404','Orbit',300,80,22,52,'sources/gw2404.jpg',[500,700,900,1100,1300,1500],[0,150,300],[[10.6,10.2,9.5],[15.9,15.3,14.5],[21,20.3,19.5],[26.4,25.7,25],[31.5,30.8,30],[36.5,35.8,35]],[[1.5,12.5],[2.3,18],[3,23.5],[3.7,29],[4.5,34.5],[5.2,40]],[30,300],notes='65 mm column permitted to 150 m and 25 m3/h on source sheet; otherwise 80 mm.')
add('GW5406','Orbit',450,100,25,220,'sources/gw5406.jpg',[500,700,900,1100,1200],[0,120,240,360,450],[[29,27,26,22,18],[40,39,36,33,29],[52,51,48,45,41],[62,61,59,56,52],[67,66,64,61,57]],[[12,38],[15,55],[17,72],[19,88],[20,96]],[30,450],notes='EXPECTED PERFORMANCE / FOR INFORMATION ONLY. Column/shaft defaults are provisional; verify actual assembly.',quality='provisional source')
add('GW9602','Orbit',150,100,25,80,'sources/gw9602.jpg',[250,500,750,960],h,[[24,23,22,20,17,14],[55,54,52,49,45,41],[80,79,78,75,71,66],[105,103,101,99,95,90]],[[2,9],[6,23],[9,38],[12,51]],[10,150],bore=200,notes='150 m head cap per user. 25 mm shaft for deeper installations.')
# WASA: source PDF pages 13-23; all models WA16-2 upwards.
add('WA16-2','WASA',150,65,19,30,'sources/wasa_13.png',[500,700,900,1100,1300,1500],h,q16,p16,[0,150],bore=None)
add('WA22-1','WASA',75,65,19,18,'sources/wasa_14.png',[900,1100,1300,1500],[0,37.5,75],[[14,12.5,11],[17,15.5,14],[19.5,18.3,17],[23,21.5,20]],[[.2,4.5],[.4,5.6],[.6,6.7],[.9,7.8]],[0,75])
q22=[[14.5,12.5,10.5],[17.5,15.5,13.5],[20.5,18.5,16.3],[23,21.3,19.8]]
p22=[[1,8],[1.4,10.6],[1.8,13.3],[2.3,16]]
add('WA22-2','WASA',150,65,19,18,'sources/wasa_15.png',[900,1100,1300,1500],[0,75,150],q22,p22,[0,150],bore=None)
add('WA22-3','WASA',225,65,19,18,'sources/wasa_16.png',[900,1100,1300,1500],[0,125,250],q22,p22,[0,250],notes='Printed maximum 225 m overrides graph extent 250 m.')
q30=[[14.7,13.8,13.4,12.7,11.7,11],[18.7,18,17.5,16.5,15.8,15],[22.7,22,21.2,20.5,19.6,19],[26.5,25.9,25.3,24.6,23.9,23],[30.3,29.7,29.1,28.5,27.8,27]]
add('WA30-2','WASA',150,80,22,23,'sources/wasa_17.png',[700,900,1100,1300,1500],h,q30,[[1,7.5],[1.5,9.7],[2,11.8],[2.5,13.9],[3.1,16]],[0,150],bore=None)
add('WA30-4','WASA',300,80,22,23,'sources/wasa_18.png',[700,900,1100,1300,1500],[0,75,150,225,300],[[13.8,13.2,11.5,8.8,5.8],[18,17.3,15.6,13,10.4],[22.3,21.6,19.8,17.3,14.6],[26.8,26.1,24.2,21.7,18.7],[30.6,30,28.3,25.8,22.8]],[[.4,13],[1.2,17.5],[2,22],[2.8,26.5],[3.7,30.5]],[0,300])
add('WA50-2','WASA',150,100,22,30,'sources/wasa_19.png',[700,900,1100,1300],h,q50,p50,[0,150],bore=None)
add('WA50-4','WASA',300,100,25,65,'sources/wasa_20.png',[200,400,600,800,1000,1200],[0,75,150,225,300],[[9,8.5,6.3,2.5,-2],[18,17.3,15.5,12,7],[27,26,23.8,19.3,13],[35.5,34.5,32,27.5,22],[43.8,42.5,40,35,29],[51.5,50,47.2,42.8,36.5]],[[2.5,8],[3.2,17],[4,25.5],[4.8,34],[5.7,43],[6.5,52]],[20,300],notes='200 rpm curve reaches zero flow before 300 m; nonpositive flow is not an operating point.')
add('WA65-2','WASA',150,100,22,40,'sources/wasa_21.png',[300,500,700,900,1100],h,q65,p65,[0,150])
add('WA90-2','WASA',150,100,25,23,'sources/wasa_22.png',[250,500,750,1000],h,q90,p90,[0,150],notes='Source shaft: 22 mm to 100 m; 25 mm from 100-150 m.')
add('WA110-2','WASA',150,100,25,23,'sources/wasa_23.png',[250,500,750,960,1100],h,[[24,23,21.8,20.2,18,15],[56,55,53.3,50,46,41],[80,80,79,76,72,67],[105,104,102,99,95,90],[110,109,107.5,105,101,95]],[[2,10],[4,23],[6,38],[8,51]],[0,150],[250,500,750,960],bore=None,notes='Power only published to 960 rpm. No power extrapolation to 1100 rpm. Source shaft: 22 mm to 100 m; 25 mm above.')
# NOV tables are numerical transcriptions; upper head limits are the printed
# description limits, not the larger extent of the tables.
add('DW1304','NOV Mono 640A',240,65,19,None,'sources/dw1304.jpg',[800,960,1000,1200,1450],[50,100,150,200,250,300],[[6.8,6.6,6.2,5.7,5,4.2],[8.3,8.1,7.7,7.2,6.7,6],[8.7,8.4,8,7.5,6.9,6.2],[10.3,10.2,9.9,9.5,9,8.4],[12.6,12.3,12,11.5,11,10.3]],[[1.54,2.48,3.42,4.36,5.3,6.24],[1.95,3,4.05,5.1,6.15,7.2],[2.03,3.12,4.22,5.31,6.41,7.5],[2.41,3.76,5.1,6.45,7.79,9.14],[2.99,4.71,6.43,8.15,9.87,11.59]],bore=100,quality='published numerical table',notes='DW name per handwritten label. Printed 240 m cap. Table/graph contains speeds beyond plotted labels.')
add('DW2402','NOV Mono 720A',120,80,22,None,'sources/dw2402.jpg',[600,800,1000,1200],[30,60,90,120,150],[[13.4,12.3,10.8,9.1,7],[18.1,17,15.5,13.5,11.2],[22.8,21.6,20,18,15.5],[27.4,26.2,24.7,22.9,20.7]],[[1.87,2.95,4.04,5.12,6.2],[2.5,4,5.5,7,8.5],[3.14,5,6.86,8.71,10.57],[3.9,6.05,8.2,10.35,12.5]],bore=127,quality='published numerical table',notes='Printed 120 m cap. Earlier review misread 120 m power: the correct table value is 10.35 kW at 1200 rpm.')
add('DW2404','NOV Mono 740A',240,80,22,None,'sources/dw2404.jpg',[600,800,1000,1200],[60,120,180,240,300],[[13.7,12.9,11.5,9.7,7.3],[18.5,17.8,16.8,15.6,14.2],[23.3,22.7,21.9,20.8,19.4],[27.8,27.2,26.3,25.2,23.8]],[[3.6,5.4,7.2,9,10.8],[4.51,7.22,9.92,12.63,15.34],[5.85,8.97,12.08,15.2,18.31],[7.53,11.27,15.02,18.76,22.51]],bore=127,quality='published numerical table',notes='Printed 240 m cap.')
add('DW4002','NOV Mono 820',120,100,22,None,'sources/dw4002.jpg',[600,800,1000,1200],[25,50,75,100,125,150],[[25,24.1,22.8,20.9,18.5,15.7],[33.3,32.4,31.2,29.7,28,26.1],[41.6,40.6,39.2,37.5,35.3,32.8],[50.2,49.3,48.1,46.4,44.4,42]],[[3.32,4.79,6.26,7.73,9.2,10.67],[4.56,6.57,8.47,10.38,12.29,14.2],[5.64,8.08,10.51,12.95,15.39,17.83],[6.76,9.83,12.89,15.95,19.01,22.08]],bore=145,quality='published numerical table')
# Source chart ranges/ticks, not calculated operating limits or auto-scaled data.
# head max/major/minor; flow min/max/major/minor; power max/major/minor.
chart_specs={
 'BP16M':(150,30,10,2,18,2,1,8,2,1),
 'BP23M':(150,30,10,0,24,4,1,16,4,2),
 'BP40M':(150,30,10,0,40,5,2.5,20,4,2),
 'BP50M':(150,30,10,10,50,5,2.5,25,5,2.5),
 'BP50H':(300,30,30,10,50,5,5,50,10,10),
 'BP65M':(150,30,10,0,70,10,5,30,10,2.5),
 'BP90M':(150,30,10,0,100,20,5,50,10,5),
 'GW1302':(150,30,10,0,24,4,1,16,4,2),
 'GW1306':(400,100,20,0,20,5,1,25,5,2.5),
 'GW2404':(300,60,20,0,50,10,5,50,10,5),
 'GW5406':(450,60,30,15,70,10,5,105,30,15),
 'GW9002':(150,30,10,0,100,20,5,50,10,5),
 'GW9602':(150,30,10,0,110,10,10,60,10,10),
 'GW25002':(150,30,10,0,200,50,10,100,20,10),
 'WA16-2':(150,30,10,2,18,2,1,8,2,1),
 'WA22-1':(75,25,5,9,23,2,1,8,2,1),
 'WA22-2':(150,50,10,9,23,2,1,16,4,1),
 'WA22-3':(250,50,10,9,23,2,1,16,4,1),
 'WA30-2':(150,30,10,10,35,5,1,20,4,2),
 'WA30-4':(300,100,20,0,55,5,5,32,8,4),
 'WA50-2':(150,30,10,10,50,5,2.5,25,5,2.5),
 'WA50-4':(300,50,10,0,60,10,5,60,20,5),
 'WA65-2':(150,30,10,0,70,10,5,30,10,2.5),
 'WA90-2':(150,30,10,0,100,20,5,50,10,5),
 'WA110-2':(150,30,10,0,120,20,5,60,20,10),
 'DW1304':(300,50,None,0,14,2,None,12,2,None),
 'DW2402':(150,30,None,0,30,5,None,14,2,None),
 'DW2404':(300,60,None,0,30,5,None,25,5,None),
 'DW4002':(150,25,None,0,60,10,None,25,5,None),
}
minimum_motors={'BP16M':4,'BP23M':4,'BP40M':5.5,'BP50M':7.5,'BP50H':11,
 'BP65M':11,'BP90M':11,'GW1302':4,'GW1306':7.5,'GW2404':15,
 'GW5406':15,'GW9002':11,'GW9602':15,'WA22-1':3,'WA22-2':5.5,
 'WA22-3':5.5,'WA30-2':7.5,'WA50-2':7.5,'WA50-4':15,
 'WA90-2':11,'WA110-2':15}
for p in pumps:
 p['published_min_rpm']=min(c['rpm'] for c in p['flow_curves'])
 p['min_rpm']=0;p['max_rpm']=max(c['rpm'] for c in p['flow_curves'])
 p['low_rpm_basis']='Below the lowest published RPM: interpolate toward 0 RPM / 0 flow and 0 absorbed kW at the same head, within the source head domain. Estimate only; verify starting torque and performance.'
 p['pump_diameter_mm']=None
 p['diameter_note']='Pump outside diameter not specified in supplied performance sheet. Column diameter and minimum bore diameter are not pump outside diameters.'
 hm,ht,hn,ql,qh,qt,qn,ph,pt,pn=chart_specs[p['name']]
 nov=p['name'].startswith('DW')
 head_label='Total Head Metres Water' if nov else ('METER HEAD (m)' if p['name'] in ['BP16M','BP40M','BP50M','BP65M','BP90M','WA16-2','WA22-1','WA22-2','WA22-3','WA30-2','WA50-2','WA65-2'] else 'TOTAL HEAD (m)')
 flow_label='Capacity (m³/h)' if nov else ('VLOEITEMPO / FLOW (m³/h)' if p['name'] in ['GW2404','GW5406','GW9602'] else 'FLOWRATE (m³/hr)')
 power_label='kW Absorbed at Pump Shaft' if nov else ('POWER AT PUMP (kW)' if p['name']=='BP50H' else ('DRYWING / POWER (kW)' if p['name'] in ['GW2404','GW5406','GW9602'] else 'POWER (kW)'))
 def axis(label,lo,hi,tick,minor):
  return {'label':label,'range':[lo,hi],'tick':tick,'minor':minor,'grid':not nov}
 p['source_chart']={'head':axis(head_label,0,hm,ht,hn),
                    'flow':axis(flow_label,ql,qh,qt,qn),
                    'power':axis(power_label,0,ph,pt,pn),
                    'rpm_unit':'RPM' if p['name'] in ['BP16M','BP40M','BP50M','BP50H','BP65M','WA16-2','WA22-1','WA22-2','WA22-3','WA30-2','WA50-2','WA65-2'] else 'r/min',
                    'minimum_motor_kw':minimum_motors.get(p['name'])}
 if p['name']=='GW5406':p['source_chart']['flow']['tick0']=20
 if p['name'].startswith('WA22'):p['source_chart']['flow']['tick0']=9
 if p['name']=='DW1304':p['source_chart']['plotted_rpms']=[800,1000,1200,1450]
 p['head_limit_basis']='printed/user confirmed' if p['name'] in ['GW9602','GW2404','GW25002'] or p['name'].startswith(('WA','DW')) else 'plotted domain; verify nameplate'
 p['power_basis']='element absorbed power' if p['name'].startswith('DW') else 'published power curve; installation drive losses not separately specified'
 p['digitisation_note']=('Manual graph readings' if p['quality']!='published numerical table' else 'Numerical table transcription')+'; piecewise linear head and RPM interpolation. Warned zero-anchor low-RPM estimates; no head or upper-RPM extrapolation.'
(ROOT/'data/pumps.json').write_text(json.dumps(pumps,indent=2))
rows=[]
for p in pumps:
 for kind,key,out in [('flow','flow_curves','flow_m3h'),('power','power_curves','power_kw')]:
  for c in p[key]:
   for head,val in zip(c['head_m'],c[out]):rows.append({'pump':p['name'],'kind':kind,'rpm':c['rpm'],'head_m':head,'value':val,'unit':'m3/h' if kind=='flow' else 'kW','source':p['source'],'quality':p['quality']})
with (ROOT/'data/curve_points.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
# CEMO photo: lower plot inherits m3/h from common flow-axis caption.
friction={40:[[0,1,2,3,4,5,6,6.5],[0,2.6,6,10,16,25,37,45]],50:[[0,2,4,6,8,10,12,13.5],[0,3.6,7.5,12,19,26,35,45]],65:[[0,10,20,30,35],[0,5.5,13.5,27,35]],80:[[0,10,20,30,40,50,53],[0,3,6,11,19,31,35]],100:[[0,20,40,60,80,100,110],[0,2,5,10.5,17.5,27,33]]}
(ROOT/'data/column_friction.json').write_text(json.dumps(friction,indent=2))
# Published Rain-Flo LAYFLAT table (not neighbouring rigid PVC tables).
layflat={50:[[40,60,80,100,200],[1.1,2.4,4.1,6,22]],65:[[60,80,100,200,350],[1.4,1.9,2.8,7,22]],80:[[80,100,120,140,160,180,250,580],[1,1.2,1.8,2.2,2.6,3.3,5,22]],100:[[160,180,200,220,280,300,500],[.6,.7,.8,1,1.4,1.6,4]],150:[[280,300,380,420,460,500,580,620],[.2,.2,.4,.5,.6,.7,.9,1]]}
(ROOT/'data/layflat_friction.json').write_text(json.dumps(layflat,indent=2))
# AB legacy limits are empirical operating guidance, not pump curve data.
# Rows are nominal 50,65,80,100 mm; columns are 80,100,120 m depth.
legacy={
'BP16M':[[3,2.7,2.5],[3,2.7,2.7],[3,2.7,2.7],[3,2.7,2.7]],
'GW1302':[[3.6,3.4,2.5],[4.2,4.1,3.8],[4.1,4,3.7],[4.1,4,3.7]],
'WA22-2':[[3.7,3.6,2.5],[4.1,3.8,3.7],[4.1,3.8,3.7],[4.1,3.8,3.7]],
'DW15':[[3.7,3.6,2.5],[4.1,3.8,3.7],[4.1,3.8,3.7],[4.1,3.8,3.7]],
'DW2402':[[None]*3,[6.1,5.5,5],[6.6,6.1,5.5],[6.6,6.1,5.5]],
'DW2404':[[None]*3,[7.2,6.9,6.3],[7.2,6.9,6.3],[7.2,6.9,6.3]],
'WA30-2':[[None]*3,[5.5,5.2,5.2],[5.5,5.5,5.2],[5.5,5.5,5.2]],
'DW4002':[[None]*3,[10,9,6.1],[11.5,11.1,9.7],[12,11.8,11.1]],
'WA50-2':[[None]*3,[8.3,8,6.9],[9,8.3,7.6],[9.7,9,8.3]],
'BP50M':[[None]*3,[9,8.3,6.9],[9,8.3,7.6],[9.7,9,8.3]],
'WA90-2':[[None]*3,[None]*3,[15,15,12.5],[22.2,22.2,19.4]],
'GW9002':[[None]*3,[None]*3,[15,15,12.5],[23.6,22.2,19.4]],
'GW9602':[[None]*3,[None]*3,[None]*3,[25,25,18.33]],
'WA110-2':[[None]*3,[None]*3,[15,15,12.5],[27,25,22]]}
up={'BP16M':[[4.1,4,3.8],[4.1,4,3.8]],'GW1302':[[6.1,5.8,5.7],[6.1,5.8,5.7]],'WA22-2':[[5.8,5.6,5.5],[5.8,5.6,5.5]],'WA30-2':[[7.7,7.6,7.4],[7.7,7.6,7.4]],'WA50-2':[[11.11,11.1,10.41],[11.8,11.11,10.41]],'BP50M':[[11.38,10.41,9.72],[11.8,11.11,10.41]]}
rows=[]
for name,sets in legacy.items():
 for size,vals in zip([50,65,80,100],sets):
  for depth,v in zip([80,100,120],vals):
   alt=up.get(name,[[None]*3]*2)[[80,100].index(size)][[80,100,120].index(depth)] if size in [80,100] else None
   rows.append({'pump':name,'column_mm':size,'depth_m':depth,'base_limit_ls':v,'large_drive_limit_ls':alt,'hose_mm':80 if size<80 else 100,'hose_length_m':100,'elevation_m':0})
with (ROOT/'data/legacy_limits.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
print(len(pumps),'pumps; curve points and friction data written')

# Manual colour-legend transcription of the AB quick chart. V6 remains unknown.
engine_codes={
'DW15':{100:['3S','3L','3L']},'DW2402':{100:['3S','3L','3L']},
'DW2404':{80:['3S','3L','3L'],100:['3S','3L','3L']},
'DW4002':{80:['3L']*3,100:['3S','3L','3L']},
'WA50-2':{80:['3S','3L','3L'],100:['4L']*3},
'BP50M':{80:['3S','3L','3L'],100:['4L']*3},
'WA90-2':{80:['4L','5L','5L'],100:['5L']*3},
'GW9002':{80:['4L','5L','5L'],100:['5L']*3},
'GW9602':{100:['V6']*3},
'WA110-2':{80:['5L','5L','6L'],100:['5L','5L','6L']}}
labels={'3S':'F3L912 / small angle drive','3L':'F3L912 / 60 HP angle drive','4L':'F4L912 / 60 HP angle drive','5L':'F5L912 / 60 HP angle drive','6L':'F6L912 / 60 HP angle drive','V6':'V6 Deutz / model unverified'}
for row in rows:
 code=engine_codes.get(row['pump'],{}).get(row['column_mm'],['3S']*3)[[80,100,120].index(row['depth_m'])]
 row['legacy_engine']=labels[code] if row['base_limit_ls'] is not None else ''
with (ROOT/'data/legacy_limits.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
