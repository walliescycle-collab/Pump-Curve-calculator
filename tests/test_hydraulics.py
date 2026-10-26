import sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
import numpy as np
from dataclasses import replace
from hydraulics import *
pytestmark=pytest.mark.filterwarnings('ignore::hydraulics.LowRPMEstimateWarning')

def test_manual_arithmetic():
    assert 60+26*60/100+9*200/100+3==pytest.approx(96.6)

def test_full_depth_and_step_level():
    s=Installation(depth_m=150,elevation_m=10)
    a=system_head(5,s,60);b=system_head(5,replace(s,design_full_depth=False),60)
    assert a['lift_m']==150 and b['lift_m']==60
    assert a['head_m']-b['head_m']==pytest.approx(90)
    assert a['column_loss_m']==b['column_loss_m']

def test_loss_length_and_units():
    # 100 US gpm, 2 inch layflat: 6 psi per 100 feet.
    q=100*3.785411784/60
    loss,notes=layflat_loss(q,30.48,50)
    assert loss==pytest.approx(6*6894.757293/(1000*G))
    assert not notes
    assert column_loss(30/3.6,200,65)[0]==pytest.approx(54)
    assert column_loss(30/3.6,100,65)[0]==pytest.approx(27)

def test_nov_exact_table_points():
    p=load_pumps()['DW2402']
    assert curve_value(p,120,1200)==pytest.approx(22.9/3.6)
    assert curve_value(p,120,1200,'power')==pytest.approx(10.35)
    p=load_pumps()['DW4002']
    assert curve_value(p,100,1200,'power')==pytest.approx(15.95)
    assert curve_value(p,100,1200)==pytest.approx(46.4/3.6)
    assert curve_value(load_pumps()['DW2404'],60,1200,'power')==pytest.approx(7.53)

def test_bounded_interpolation():
    p=load_pumps()['WA16-2']
    assert required_rpm(p,curve_value(p,100,1000),100)==pytest.approx(1000)
    for head,rpm in [(151,1000),(100,-1),(100,1501)]:
        with pytest.raises(CurveRangeError):curve_value(p,head,rpm)
    with pytest.raises(CurveRangeError):curve_value(load_pumps()['WA110-2'],100,1100,'power')
    with pytest.raises(CurveRangeError):curve_value(load_pumps()['GW9602'],151,960)

def test_rpm_system_intersection_roundtrip():
    s=Installation(depth_m=80,column_mm=80,hose_mm=100)
    for name in ['BP40M','GW9002','DW2402','WA30-2']:
        p=load_pumps()[name];rpm=(p['min_rpm']+p['max_rpm'])/2
        r=operating_point(p,rpm,s,60)
        assert required_rpm(p,r['yield_ls'],r['head_m'])==pytest.approx(rpm,abs=1e-5)
        assert r['head_m']==pytest.approx(system_head(r['yield_ls'],s,60)['head_m'])

def test_curve_comparison_sign():
    p=load_pumps()['BP16M'];q=curve_value(p,100,1000)
    assert compare_actual(p,q,100,1000)['rpm_difference_pct']==pytest.approx(0)
    r=compare_actual(p,q,100,1200)
    assert r['status']=='Below expected performance' and r['flow_difference_pct']<0

def test_all_steps_drive_and_bore_limits():
    p=load_pumps()['DW2402'];s=Installation(depth_m=80,column_mm=80,bore_mm=100)
    steps=[{'value':4,'water_level_m':50}]
    r=evaluate(p,steps,s,Drive(pump_rpm_limit=700))
    assert r['status']=='Not suitable'
    assert any('Bore' in x for x in r['reasons'])
    assert any('RPM' in x for x in r['reasons'])
    r=evaluate(p,[{'value':4,'water_level_m':50},{'value':60,'water_level_m':50}],replace(s,bore_mm=200),Drive(pump_rpm_limit=1500))
    assert r['status']=='Not suitable' and any('Step 2' in x for x in r['reasons'])

def test_fixed_engine_ratings_and_v6():
    options=engine_options(100,Drive(engine_model='F6L413F',engine_derating=1))
    assert [x['continuous_kw'] for x in options]==[36,49,61,74,102]
    assert [x['engine'] for x in options if x['passes']]==['F6L413F']
    assert [x['engine'] for x in options if x['installed']]==['F6L413F']
    assert not any(x['passes'] for x in engine_options(103,Drive(engine_derating=1)))
    assert not any(x['passes'] for x in engine_options(100,Drive()))
    available=102*.9
    assert engine_options(available,Drive(engine_model='F6L413F'))[-1]['passes']
    assert not engine_options(available+.001,Drive(engine_model='F6L413F'))[-1]['passes']
    assert Drive().engine_model=='F3L912'
    with pytest.raises(ValueError):Drive(engine_model='unknown').validate()
    with pytest.raises(ValueError):engine_options(float('nan'),Drive())

def test_installed_engine_independent_of_minimum_size():
    pump=load_pumps()['GW25002']
    installation=Installation(depth_m=100,column_mm=150,hose_mm=150,bore_mm=300)
    steps=[{'value':350,'water_level_m':50},{'value':500,'water_level_m':50}]
    small=evaluate(pump,steps,installation,Drive(drive_rating_kw=200),mode='rpm')
    large=evaluate(pump,steps,installation,Drive(drive_rating_kw=200,engine_model='F6L413F'),mode='rpm')
    assert small['recommended_engine']==large['recommended_engine']
    assert small['required_engine_kw']==large['required_engine_kw']
    assert 'installed_engine_passes' not in small
    assert small['status']!='Not suitable' and large['status']!='Not suitable'
    assert small['reasons']==large['reasons']
    assert not any('installed' in r for r in small['reasons']+large['reasons'])
    assert large['required_engine_kw']==max(r['engine_required_kw'] for r in large['rows'])

def test_usable_engine_limit_and_warning_threshold():
    drive=Drive(transmission_efficiency=.8,engine_derating=.75,extra_shaft_kw=2)
    limit=36*.75*.8-2
    assert engine_pump_limit_kw(drive)==pytest.approx(limit)
    assert engine_power_warning(limit,drive) is None
    assert 'Engine power limit exceeded' in engine_power_warning(limit+.01,drive)
    assert engine_pump_limit_kw(replace(drive,sizing_margin=2))==pytest.approx(limit)
    assert engine_pump_limit_kw(replace(drive,extra_shaft_kw=100))<0

@pytest.mark.parametrize('name',list(load_pumps()))
def test_engine_boundary_matches_power_and_flow(name):
    pump=load_pumps()[name];drive=Drive()
    boundary=engine_flow_boundary(pump,drive,samples=25)
    for head,flow,rpm in zip(boundary['head_m'],boundary['yield_ls'],boundary['rpm']):
        if flow is None:
            assert rpm is None
            continue
        assert 0<=rpm<=min(pump['max_rpm'],max(c['rpm'] for c in pump['power_curves']))
        assert curve_value(pump,head,rpm,'power')==pytest.approx(boundary['limit_kw'])
        assert curve_value(pump,head,rpm)==pytest.approx(flow)
        assert head<=pump['max_head_m']

def test_engine_boundary_no_invented_high_speed_and_zero_anchor():
    pump=load_pumps()['BP16M']
    assert all(q is None for q in engine_flow_boundary(pump,Drive(engine_model='F6L413F'))['yield_ls'])
    low=Drive(transmission_efficiency=.5,engine_derating=.5,extra_shaft_kw=8.5)
    boundary=engine_flow_boundary(pump,low)
    assert any(n is not None and 0<n<pump['published_min_rpm'] for n in boundary['rpm'])
    assert all(q is None for q in engine_flow_boundary(pump,replace(low,extra_shaft_kw=100))['yield_ls'])

@pytest.mark.parametrize('name',list(load_pumps()))
def test_sub_100_rpm_zero_anchor_and_roundtrip(name):
    pump=load_pumps()[name];head=60
    n0=pump['published_min_rpm']
    expected=curve_value(pump,head,n0)*50/n0
    with pytest.warns(LowRPMEstimateWarning,match='Flow.*low-RPM estimate'):
        q=curve_value(pump,head,50)
    assert q==pytest.approx(expected) and q>0
    with pytest.warns(LowRPMEstimateWarning):
        assert required_rpm(pump,q,head)==pytest.approx(50)
    p0=min(c['rpm'] for c in pump['power_curves'])
    with pytest.warns(LowRPMEstimateWarning,match='Power.*low-RPM estimate'):
        assert curve_value(pump,head,50,'power')==pytest.approx(curve_value(pump,head,p0,'power')*50/p0)
    installation=Installation(depth_m=60,column_mm=pump['nominal_column_mm'],hose_length_m=0,bore_mm=300)
    result=evaluate(pump,[{'value':50,'water_level_m':60}],installation,Drive(),mode='rpm')
    row=result['rows'][0]
    assert not row['error'] and row['yield_ls']>0 and row['pump_kw']>0
    assert any('low-RPM estimate' in note for note in row['notes'])
    assert any('low-RPM estimate' in note for note in result['conditions'])
    inferred=evaluate(pump,[{'value':row['yield_ls'],'water_level_m':60}],installation,Drive())
    assert inferred['rows'][0]['rpm']==pytest.approx(50,abs=1e-5)
    assert any('low-RPM estimate' in note for note in inferred['conditions'])
    check=compare_actual(pump,q,head,50)
    assert check['notes'] and check['rpm_difference_pct']==pytest.approx(0)

def test_low_speed_does_not_extend_head_or_missing_power():
    with pytest.raises(CurveRangeError):curve_value(load_pumps()['DW1304'],49,50)
    with pytest.raises(CurveRangeError):curve_value(load_pumps()['BP16M'],151,50)
    with pytest.raises(CurveRangeError):curve_value(load_pumps()['WA50-4'],300,50)
    with pytest.raises(CurveRangeError):operating_point(load_pumps()['BP40M'],0,Installation())
    result=evaluate(load_pumps()['WA110-2'],[{'value':1100,'water_level_m':60}],Installation(depth_m=60),Drive(),mode='rpm')
    assert result['required_engine_kw'] is None
    assert result['recommended_engine'] is None and 'installed_engine_passes' not in result
    assert any('engine recommendation unavailable' in c for c in result['conditions'])

def test_validation_and_extensions():
    with pytest.raises(ValueError):system_head(-1,Installation())
    with pytest.raises(ValueError):system_head(5,Installation(),101)
    with pytest.raises(ValueError):system_head(float('nan'),Installation())
    assert column_loss(60,100,150)[1]
    assert layflat_loss(60,100,200)[1]
    assert system_head(60,Installation(column_mm=40))['column_velocity_ms']>3

@pytest.mark.parametrize('name',list(load_pumps()))
def test_all_source_knots_and_validity(name):
    p=load_pumps()[name]
    for kind,key,val in [('flow','flow_curves','flow_m3h'),('power','power_curves','power_kw')]:
        for c in p[key]:
            assert len(c['head_m'])==len(c[val]);assert all(b>a for a,b in zip(c['head_m'],c['head_m'][1:]))
            for h,v in zip(c['head_m'],c[val]):
                if h<=p['max_head_m']:
                    assert curve_value(p,h,c['rpm'],kind)==pytest.approx(v/(3.6 if kind=='flow' else 1))
    assert (ROOT/p['source']).is_file()

def test_friction_positive_monotone():
    for func,sizes in [(column_loss,[40,50,65,80,100,150]),(layflat_loss,[50,65,80,100,150,200])]:
        for d in sizes:
            vals=[func(q,100,d)[0] for q in np.linspace(0,60,300)]
            assert vals[0]==0 and all(b>=a for a,b in zip(vals,vals[1:]))

def test_24_rpm_steps():
    p=load_pumps()['BP40M'];s=Installation(depth_m=80)
    steps=[{'value':float(n),'water_level_m':50} for n in np.linspace(700,1100,24)]
    r=evaluate(p,steps,s,Drive(),mode='rpm')
    assert len(r['rows'])==24 and all(not x['error'] for x in r['rows'])

def test_terrain_response(monkeypatch):
    import requests
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'status':'OK','results':[{'elevation':100},{'elevation':103}]}
    monkeypatch.setattr(requests,'get',lambda *a,**k:Response())
    assert terrain_elevations(-33,18,-33.1,18.1)['difference_m']==3

@pytest.mark.parametrize('name',list(load_pumps()))
def test_power_range(name):
    p=load_pumps()[name];rating=pump_power_range(p)
    c=max(p['power_curves'],key=lambda curve:curve['rpm'])
    valid=[v for h,v in zip(c['head_m'],c['power_kw']) if h<=p['max_head_m']]
    if c['head_m'][0]<=p['max_head_m']<=c['head_m'][-1]:
        valid.append(curve_value(p,p['max_head_m'],c['rpm'],'power'))
    assert rating['minimum_kw']==p['source_chart']['minimum_motor_kw']
    assert rating['maximum_kw']==pytest.approx(max(valid))
    assert rating['power_rpm']==c['rpm']
    if name=='WA110-2':assert rating['power_rpm']==960<p['max_rpm']

def test_failed_yield_keeps_head_for_overload_chart():
    p=load_pumps()['BP16M']
    result=evaluate(p,[{'value':3,'water_level_m':200}],Installation(depth_m=200),Drive())
    assert result['rows'][0]['head_m']>p['max_head_m']
    assert result['rows'][0]['error']
