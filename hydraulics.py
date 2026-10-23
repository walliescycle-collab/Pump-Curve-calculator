"""Shared calculation engine. No Streamlit dependency. SI internally; L/s at UI.
Head and upper speed remain bounded. Low-speed estimates use a warned zero anchor.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
from functools import lru_cache
import json, math, warnings
import numpy as np
from scipy.optimize import brentq
ROOT=Path(__file__).resolve().parent
G=9.80665
@lru_cache(None)
def load_json(name):return json.loads((ROOT/'data'/name).read_text())
def load_pumps():return {p['name']:p for p in load_json('pumps.json')}
def finite(x,name):
    if not math.isfinite(float(x)):raise ValueError(f'{name} must be finite')
def nonnegative(x,name):
    finite(x,name)
    if x<0:raise ValueError(f'{name} cannot be negative')
def log_interp_extended(q,x,y,exponent=1.85):
    """Log-log interpolation; explicit power-law extensions outside chart range."""
    if q==0:return 0.,False
    x=np.asarray(x);y=np.asarray(y)
    keep=(x>0)&(y>0);x=x[keep];y=y[keep]
    if q<x[0]:return float(y[0]*(q/x[0])**exponent),True
    if q>x[-1]:return float(y[-1]*(q/x[-1])**exponent),True
    return float(np.exp(np.interp(np.log(q),np.log(x),np.log(y)))),False

def column_loss(q_ls,length_m,nominal_mm):
    nonnegative(q_ls,'Yield');nonnegative(length_m,'Column length')
    if nominal_mm not in [40,50,65,80,100,150]:raise ValueError('Unsupported column diameter')
    if length_m==0 or q_ls==0:return 0.,[]
    notes=[];key=str(nominal_mm)
    data=load_json('column_friction.json')
    if key not in data:
        # 150 mm not on supplied charts: scale 100 mm using annular hydraulic
        # diameter and area. Shaft defaults 25 mm and 40 mm, equal f assumption.
        x,y=data['100'];d1,s1,d2,s2=.100,.025,.150,.040
        scale=((d1*d1-s1*s1)/(d2*d2-s2*s2))**2*(d1-s1)/(d2-s2)
        y=[v*scale for v in y];notes.append('150 mm column is an annular scaling estimate, not a supplied CEMO curve')
    else:x,y=data[key]
    rate,ext=log_interp_extended(q_ls*3.6,x,y,2.)
    if ext:notes.append(f'{nominal_mm} mm column friction outside chart range: quadratic extension')
    return rate*length_m/100,notes

def layflat_loss(q_ls,length_m,nominal_mm):
    nonnegative(q_ls,'Yield');nonnegative(length_m,'Hose length')
    if nominal_mm not in [50,65,80,100,150,200]:raise ValueError('Unsupported hose diameter')
    if q_ls==0 or length_m==0:return 0.,[]
    notes=[];data=load_json('layflat_friction.json')
    key=str(nominal_mm if nominal_mm!=200 else 150)
    gpm,psi=data[key]
    # US gallon, psi head / 100 feet -> metres / 100 metres.
    x=np.asarray(gpm)*3.785411784/60
    y=np.asarray(psi)*(6894.757293/(1000*G))*100/30.48
    if nominal_mm==200:
        y=y*(150/200)**4.87
        notes.append('200 mm layflat estimated from 150 mm chart by diameter scaling (D^-4.87)')
    rate,ext=log_interp_extended(q_ls,x,y)
    if ext:notes.append(f'{nominal_mm} mm layflat outside tabulated flow range: Q^1.85 extension')
    return rate*length_m/100,notes

def velocity(q_ls,diameter_mm,shaft_mm=0):
    if diameter_mm<=shaft_mm or shaft_mm<0:raise ValueError('Invalid waterway/shaft diameter')
    return q_ls/1000/(math.pi/4*((diameter_mm/1000)**2-(shaft_mm/1000)**2))

@dataclass
class Installation:
    depth_m:float=100
    column_mm:int=80
    hose_length_m:float=100
    hose_mm:int=100
    elevation_m:float=0
    bore_mm:float=200
    design_full_depth:bool=True
    velocity_warning_ms:float=3
    def validate(self):
        for v,k in [(self.depth_m,'Depth'),(self.hose_length_m,'Hose length'),(self.bore_mm,'Bore diameter')]:nonnegative(v,k)
        finite(self.elevation_m,'Elevation')
        if self.depth_m<=0 or self.bore_mm<=0:raise ValueError('Depth and bore diameter must be positive')
        if self.column_mm not in [40,50,65,80,100,150]:raise ValueError('Unsupported column')
        if self.hose_mm not in [50,65,80,100,150,200]:raise ValueError('Unsupported layflat')
        if self.velocity_warning_ms<=0:raise ValueError('Velocity warning threshold must be positive')
        return self

def system_head(q_ls,installation,water_level_m=None):
    s=installation.validate();nonnegative(q_ls,'Yield')
    if q_ls>60:raise ValueError('Calculation range ends at 60 L/s')
    if water_level_m is not None:
        nonnegative(water_level_m,'Pumping water depth')
        if water_level_m>s.depth_m:raise ValueError('Pumping water level is below the pump installation')
    if not s.design_full_depth and water_level_m is None:raise ValueError('Enter pumping water level for this step')
    lift=s.depth_m if s.design_full_depth else water_level_m
    cf,cn=column_loss(q_ls,s.depth_m,s.column_mm);hf,hn=layflat_loss(q_ls,s.hose_length_m,s.hose_mm)
    shaft={40:13,50:16,65:19,80:22,100:25,150:40}[s.column_mm]
    cv=velocity(q_ls,s.column_mm,shaft);hv=velocity(q_ls,s.hose_mm)
    notes=cn+hn
    if cv>s.velocity_warning_ms:notes.append(f'Column velocity {cv:.1f} m/s exceeds {s.velocity_warning_ms:g} m/s review threshold')
    if hv>s.velocity_warning_ms:notes.append(f'Layflat velocity {hv:.1f} m/s exceeds {s.velocity_warning_ms:g} m/s review threshold')
    if lift+s.elevation_m<0:notes.append('Downhill gravity/siphon regime: full-pipe model may not describe layflat behaviour')
    return {'yield_ls':float(q_ls),'lift_m':float(lift),'column_loss_m':cf,'elevation_m':s.elevation_m,'layflat_loss_m':hf,'head_m':float(lift+cf+s.elevation_m+hf),'column_velocity_ms':cv,'hose_velocity_ms':hv,'notes':notes}

class CurveRangeError(ValueError):pass
class LowRPMEstimateWarning(UserWarning):pass

def low_speed_notes(pump,rpm,kinds=('flow','power')):
    notes=[]
    for kind in kinds:
        lowest=min(c['rpm'] for c in pump[f'{kind}_curves'])
        if 0<rpm<lowest:
            notes.append(f'{kind.title()} at {rpm:g} RPM is a low-RPM estimate below published {lowest:g} RPM: interpolated toward 0 RPM / 0 {"flow" if kind=="flow" else "absorbed kW"} at the same head; verify performance and starting torque')
    return notes

def curve_value(pump,head_m,rpm,kind='flow'):
    finite(head_m,'Head');finite(rpm,'RPM')
    if kind not in ['flow','power']:raise ValueError('Curve kind must be flow or power')
    if head_m<0 or head_m>pump['max_head_m']+1e-7:raise CurveRangeError(f"Head outside 0–{pump['max_head_m']:g} m pump limit")
    curves=sorted(pump['flow_curves' if kind=='flow' else 'power_curves'],key=lambda c:c['rpm'])
    speeds=np.array([c['rpm'] for c in curves])
    if rpm<0 or rpm>speeds[-1]+1e-7:raise CurveRangeError(f'{kind.title()} curve RPM outside 0–{speeds[-1]:g}')
    if rpm<speeds[0]-1e-7:
        base=curve_value(pump,head_m,float(speeds[0]),kind)
        if kind=='flow' and base<=0 and rpm>0:raise CurveRangeError('No positive low-speed flow at this head on the lowest published curve')
        if rpm>0:warnings.warn(low_speed_notes(pump,rpm,(kind,))[0],LowRPMEstimateWarning,stacklevel=2)
        return base*rpm/float(speeds[0])
    idx=int(np.searchsorted(speeds,rpm));indices=sorted(set([max(0,idx-1),min(idx,len(speeds)-1)]))
    # Exact published-speed queries must not inherit an unrelated curve domain.
    exact=np.where(np.isclose(speeds,rpm,atol=1e-7,rtol=0))[0]
    if len(exact):indices=[int(exact[0])]
    vals=[]
    for i in indices:
        c=curves[i];heads=c['head_m'];key='flow_m3h' if kind=='flow' else 'power_kw'
        if head_m<heads[0]-1e-7 or head_m>heads[-1]+1e-7:raise CurveRangeError(f'{kind.title()} data only cover {heads[0]:g}–{heads[-1]:g} m at {c["rpm"]:g} RPM')
        vals.append(float(np.interp(head_m,heads,c[key])))
    value=float(np.interp(rpm,speeds[indices],vals))
    return value/3.6 if kind=='flow' else value

def required_rpm(pump,q_ls,head_m):
    if q_ls<=0:raise ValueError('Yield must be positive')
    finite(q_ls,'Yield')
    speeds=sorted(c['rpm'] for c in pump['flow_curves'])
    qs=[curve_value(pump,head_m,n) for n in speeds]
    if any(b<=a for a,b in zip(qs,qs[1:])):raise ValueError('Non-monotone RPM data; review source')
    if q_ls<qs[0]-1e-7:
        rpm=float(speeds[0]*q_ls/qs[0])
        warnings.warn(low_speed_notes(pump,rpm,('flow',))[0],LowRPMEstimateWarning,stacklevel=2)
        return rpm
    if q_ls>qs[-1]+1e-7:raise CurveRangeError(f'Yield exceeds {qs[-1]:.2f} L/s at maximum {speeds[-1]:g} RPM')
    return float(np.interp(q_ls,qs,speeds))

def operating_point(pump,rpm,installation,water_level_m=None):
    """Bracket only within the common valid head domain; no fabricated roots."""
    # Validate speed independently of available head domain.
    finite(rpm,'RPM')
    if not 0<rpm<=pump['max_rpm']:raise CurveRangeError('Pump RPM must be positive and cannot exceed the published maximum')
    minhead=max(c['head_m'][0] for c in pump['flow_curves'])
    maxhead=min(pump['max_head_m'],min(c['head_m'][-1] for c in pump['flow_curves']))
    hf=lambda q:system_head(q,installation,water_level_m)['head_m']
    h0,h60=hf(0),hf(60)
    if h0>maxhead or h60<minhead:raise CurveRangeError('System head does not enter pump curve domain')
    lo=0 if h0>=minhead else brentq(lambda q:hf(q)-minhead,0,60)
    hi=60 if h60<=maxhead else brentq(lambda q:hf(q)-maxhead,0,60)
    f=lambda q:curve_value(pump,hf(q),rpm)-q
    flo,fhi=f(lo),f(hi)
    if flo*fhi>0:raise CurveRangeError('No intersection within published head range and 0–60 L/s')
    q=brentq(f,lo,hi,xtol=1e-9)
    if q<=0:raise CurveRangeError('No positive-flow operating point')
    return system_head(q,installation,water_level_m)

@dataclass
class Drive:
    pump_rpm_limit:float=1100
    drive_rating_kw:float=60*.745699872
    transmission_efficiency:float=.90
    extra_shaft_kw:float=0
    sizing_margin:float=1.33
    engine_derating:float=.90
    engine_model:str='F3L912'
    def validate(self):
        for key,val in asdict(self).items():
            if key!='engine_model':finite(val,key)
        if not 0<self.transmission_efficiency<=1 or not 0<self.engine_derating<=1:raise ValueError('Efficiency/availability must be between 0 and 1')
        if self.sizing_margin<1 or self.extra_shaft_kw<0 or self.pump_rpm_limit<=0 or self.drive_rating_kw<=0:raise ValueError('Invalid drive settings')
        if self.engine_model not in ENGINES:raise ValueError('Unknown installed engine model')
        return self

# User-confirmed continuous ratings at 2300 engine RPM.
ENGINES={'F3L912':36.,'F4L912':49.,'F5L912':61.,'F6L912':74.,'F6L413FW':102.}
def engine_options(required_kw,drive):
    nonnegative(required_kw,'Required engine power')
    d=drive.validate();out=[]
    for name,gross in ENGINES.items():
        net=gross*d.engine_derating
        out.append({'engine':name,'continuous_kw':gross,'available_kw':net,'required_kw':required_kw,'passes':net>=required_kw,'installed':name==d.engine_model})
    return out

def evaluate(pump,steps,installation,drive,mode='yield',bore_override=None):
    installation.validate();drive.validate();results=[];fail=[];conditions=[]
    for i,step in enumerate(steps,1):
        row={'step':i,'input':step['value'],'water_level_m':step.get('water_level_m')}
        try:
            if mode=='yield':
                r=system_head(float(step['value']),installation,step.get('water_level_m'))
                n=required_rpm(pump,r['yield_ls'],r['head_m'])
            else:
                n=float(step['value']);r=operating_point(pump,n,installation,step.get('water_level_m'))
            row.update(r);row['rpm']=n
            row['notes']=list(r['notes'])+low_speed_notes(pump,n)
            if n>drive.pump_rpm_limit+1e-6:fail.append(f'Step {i}: exceeds drive RPM limit {drive.pump_rpm_limit:g}')
            try:
                power=curve_value(pump,r['head_m'],n,'power');row['pump_kw']=power
                row['hydraulic_kw']=r['yield_ls']/1000*1000*G*r['head_m']/1000
                row['running_torque_nm']=9550*(power+drive.extra_shaft_kw)/n
                row['engine_required_kw']=(power+drive.extra_shaft_kw)/drive.transmission_efficiency*drive.sizing_margin
                if power+drive.extra_shaft_kw>drive.drive_rating_kw:fail.append(f'Step {i}: angle-drive power rating exceeded')
                available=ENGINES[drive.engine_model]*drive.engine_derating
                if row['engine_required_kw']>available:fail.append(f'Step {i}: installed {drive.engine_model} available {available:g} kW is below required {row["engine_required_kw"]:.2f} kW')
            except CurveRangeError as e:conditions.append(f'Step {i}: {e}; engine recommendation unavailable')
            row['error']=''
            for note in row['notes']:
                if 'estimate' in note or 'extension' in note:conditions.append(note)
        except (ValueError,TypeError) as e:
            row['error']=str(e);fail.append(f'Step {i}: {e}')
        results.append(row)
    minbore=bore_override if bore_override is not None else pump['minimum_bore_mm']
    if minbore is None:conditions.append('Minimum bore diameter unavailable: verify pump/centraliser clearance')
    elif installation.bore_mm<minbore:fail.append(f'Bore {installation.bore_mm:g} mm is smaller than minimum {minbore:g} mm')
    if pump['quality']=='provisional source':conditions.append('Provisional pump performance sheet')
    # Source column recommendations are compatibility flags, not invented adapters.
    allowed={'GW1306':65 if installation.depth_m<=200 else 80,'GW2404':65 if installation.depth_m<=150 and max([r.get('yield_ls',0) for r in results],default=0)*3.6<=25 else 80}
    recommended=allowed.get(pump['name'],pump['nominal_column_mm'])
    if installation.column_mm!=recommended:conditions.append(f'Confirm adapter/rod arrangement: source column {recommended} mm; selected {installation.column_mm} mm')
    reqs=[r['engine_required_kw'] for r in results if 'engine_required_kw' in r]
    peak=max(reqs) if reqs and len(reqs)==len(steps) else None
    engine=next((e['engine'] for e in engine_options(peak,drive) if e['passes']),None) if peak is not None else None
    return {'pump':pump['name'],'status':'Not suitable' if fail else ('Conditional' if conditions else 'Suitable for planning'),'reasons':list(dict.fromkeys(fail)),'conditions':list(dict.fromkeys(conditions)),'rows':results,'required_engine_kw':peak,'recommended_engine':engine,'installed_engine':drive.engine_model,'installed_engine_passes':None if peak is None else ENGINES[drive.engine_model]*drive.engine_derating>=peak}

def compare_actual(pump,q_ls,head_m,actual_rpm,tolerance_pct=10):
    nonnegative(tolerance_pct,'Tolerance')
    if actual_rpm<=0:raise ValueError('Actual RPM must be positive')
    expected_rpm=required_rpm(pump,q_ls,head_m)
    expected_q=curve_value(pump,head_m,actual_rpm)
    if expected_q<=0:raise CurveRangeError('No positive expected flow')
    rpm_delta=100*(actual_rpm/expected_rpm-1)
    flow_delta=100*(q_ls/expected_q-1)
    status='Within comparison tolerance' if abs(rpm_delta)<=tolerance_pct else ('Below expected performance' if rpm_delta>0 else 'Above expected performance')
    return {'expected_rpm':expected_rpm,'actual_rpm':actual_rpm,'rpm_difference_pct':rpm_delta,'expected_yield_ls':expected_q,'actual_yield_ls':q_ls,'flow_difference_pct':flow_delta,'status':status,'tolerance_pct':tolerance_pct,'notes':list(dict.fromkeys(low_speed_notes(pump,expected_rpm,('flow',))+low_speed_notes(pump,actual_rpm,('flow',))))}

def terrain_elevations(lat1,lon1,lat2,lon2):
    """Optional online lookup, user-triggered. Manual entry always supported."""
    import requests
    for lat,lon in [(lat1,lon1),(lat2,lon2)]:
        finite(lat,'Latitude');finite(lon,'Longitude')
        if not -60<=lat<=60 or not -180<=lon<=180:raise ValueError('Coordinates outside SRTM coverage')
    r=requests.get('https://api.opentopodata.org/v1/srtm90m',params={'locations':f'{lat1},{lon1}|{lat2},{lon2}'},timeout=12)
    r.raise_for_status();d=r.json()
    if d.get('status')!='OK' or len(d.get('results',[]))!=2:raise ValueError('Elevation service could not resolve both points')
    z=[v['elevation'] for v in d['results']]
    if any(v is None or not math.isfinite(v) for v in z):raise ValueError('No terrain elevation for one or both coordinates')
    return {'borehole_elevation_m':z[0],'outlet_elevation_m':z[1],'difference_m':z[1]-z[0],'dataset':'SRTM90m / Open Topo Data'}
