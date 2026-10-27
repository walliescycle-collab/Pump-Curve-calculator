import sys
from pathlib import Path
import numpy as np
import pytest
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hydraulics import load_pumps,Installation,system_head
from plots import performance_plot,head_contribution_plot,rpm_comparison_plot,apply_theme
from hydraulics import compare_actual,curve_value
from hydraulics import Drive,engine_pump_limit_kw
from hydraulics import ENGINE_POWER_FRACTIONS, ENGINES

@pytest.mark.parametrize('name',list(load_pumps()))
def test_source_performance_layout_and_knots(name):
    pump=load_pumps()[name];chart=pump['source_chart']
    fig=performance_plot(pump)
    for axis,spec in [('xaxis','head'),('xaxis2','head'),('yaxis','flow'),('yaxis2','power')]:
        actual=fig.layout[axis];expected=chart[spec]
        assert list(actual.range)==expected['range']
        assert actual.autorange is False
        assert actual.title.text==('YIELD (m³/h)' if spec=='flow' else expected['label'])
        assert actual.dtick==(25 if spec=='head' else expected['tick'])
        assert actual.showgrid==(True if spec=='head' else expected['grid'])
        if spec!='head' and expected['minor'] and expected['minor']<expected['tick']:
            assert actual.minor.dtick==expected['minor']
    curves=[(c,key) for collection,key in [('flow_curves','flow_m3h'),('power_curves','power_kw')]
        for c in pump[collection] if 'plotted_rpms' not in chart or c['rpm'] in chart['plotted_rpms']]
    assert len(fig.data)==len(curves)
    for trace,(curve,key) in zip(fig.data,curves):
        np.testing.assert_allclose(trace.x,curve['head_m'])
        np.testing.assert_allclose(trace.y,curve[key])
        assert f"{curve['rpm']:g} {chart['rpm_unit']}" in trace.name
    assert pump['pump_diameter_mm'] is None or pump['pump_diameter_mm']>0
    assert pump['published_min_rpm']>0 and pump['min_rpm']==0

def test_source_scales_are_not_operating_limits():
    pumps=load_pumps()
    assert list(performance_plot(pumps['BP16M']).layout.yaxis.range)==[2,18]
    assert list(performance_plot(pumps['BP50M']).layout.yaxis.range)==[10,50]
    for name,bound,limit in [('WA22-3',250,225),('DW2402',150,120),('DW1304',300,240)]:
        fig=performance_plot(pumps[name])
        assert list(fig.layout.xaxis.range)==[0,bound]
        assert any(shape.x0==limit and shape.x1==limit for shape in fig.layout.shapes)
    power=performance_plot(pumps['WA110-2']).select_traces(selector=dict(xaxis='x2'))
    assert not any('1100' in trace.name for trace in power)

@pytest.mark.parametrize('full,expected_count',[(True,1),(False,2)])
def test_source_system_overlay_axes_units_and_levels(full,expected_count):
    pump=load_pumps()['BP40M']
    installation=Installation(depth_m=100,design_full_depth=full,elevation_m=3)
    steps=[{'value':3,'water_level_m':40},{'value':4,'water_level_m':70},{'value':5,'water_level_m':40}]
    fig=performance_plot(pump,installation=installation,steps=steps)
    overlays=[trace for trace in fig.data if trace.name.startswith('System')]
    assert len(overlays)==expected_count
    for trace,wl in zip(overlays,[40,70]):
        assert trace.xaxis=='x' and trace.yaxis=='y'
        assert trace.line.dash=='dash' and trace.showlegend
        qs=np.asarray(trace.y)/3.6
        np.testing.assert_allclose(trace.x,[system_head(q,installation,wl)['head_m'] for q in qs])
        np.testing.assert_allclose(trace.customdata,qs)
        assert max(qs)<=60
    assert list(fig.layout.xaxis.range)==pump['source_chart']['head']['range']
    assert list(fig.layout.yaxis.range)==pump['source_chart']['flow']['range']
    assert json.dumps(overlays[0].name)[1:-1] in fig.to_html(include_plotlyjs=False)

def test_source_system_overlay_requires_steps_and_valid_levels():
    pump=load_pumps()['BP40M']
    with pytest.raises(ValueError,match='Test steps'):
        performance_plot(pump,installation=Installation())
    with pytest.raises(ValueError,match='below the pump'):
        performance_plot(pump,installation=Installation(depth_m=100,design_full_depth=False),
            steps=[{'value':3,'water_level_m':101}])

@pytest.mark.parametrize('name',list(load_pumps()))
def test_performance_flow_unit_conversion(name):
    p=load_pumps()[name]
    a=performance_plot(p);b=performance_plot(p,flow_unit='L/s')
    for x,y in zip(a.data,b.data):
        np.testing.assert_allclose(x.x,y.x)
        np.testing.assert_allclose(np.asarray(x.y)/(3.6 if x.xaxis=='x' else 1),y.y)
    np.testing.assert_allclose(np.array(a.layout.yaxis.range)/3.6,b.layout.yaxis.range)
    assert b.layout.xaxis.dtick==25
    assert b.layout.yaxis.title.text=='YIELD (L/s)'

def test_head_bar_percentages_signed_and_overload():
    p=load_pumps()['BP16M']
    rows=[dict(step=1,lift_m=100,column_loss_m=30,elevation_m=-20,layflat_loss_m=5,head_m=115),
        dict(step=2,lift_m=140,column_loss_m=30,elevation_m=10,layflat_loss_m=5,head_m=185)]
    fig=head_contribution_plot(p,{'rows':rows})
    assert fig.layout.barmode=='relative' and fig.layout.xaxis.dtick==25
    assert fig.data[2].x[0]==-20 and fig.data[2].customdata[0]==pytest.approx(-20/150*100)
    assert sum(trace.customdata[0] for trace in fig.data)==pytest.approx(115/150*100)
    assert any('Overload 35.0 m' in annotation.text for annotation in fig.layout.annotations)
    assert fig.layout.shapes[0].x0==150
    assert fig.layout.xaxis.range[0]<=-20 and fig.layout.xaxis.range[1]>=185

@pytest.mark.parametrize('theme',['light','dark'])
def test_field_points_rpm_deviation_and_theme(theme):
    p=load_pumps()['BP40M'];h=100;q=curve_value(p,h,900)
    check=compare_actual(p,q,h,1000)
    fig=apply_theme(performance_plot(p,flow_unit='L/s',field_check=dict(check,head_m=h)),theme)
    points=[trace for trace in fig.data if trace.name.startswith(('Measured','Expected at'))]
    assert len(points)==2
    assert points[0].y[0]==pytest.approx(q) and points[0].x[0]==h
    assert points[1].y[0]==pytest.approx(check['expected_yield_ls'])
    assert fig.layout.font.color==('#f0f2f6' if theme=='dark' else '#222222')
    assert all(trace.line.color!='#222222' for trace in fig.data) if theme=='dark' else True
    rpm=rpm_comparison_plot(check)
    assert list(rpm.data[0].y)==[900,1000]
    assert '+11.1%' in rpm.layout.title.text

@pytest.mark.parametrize('unit',['L/s','m³/h'])
@pytest.mark.parametrize('theme',['light','dark'])
def test_engine_limit_on_both_performance_panels(unit,theme):
    pump=load_pumps()['WA50-2'];drive=Drive()
    fig=apply_theme(performance_plot(pump,drive=drive,flow_unit=unit),theme)
    limit=engine_pump_limit_kw(drive)
    line=next(shape for shape in fig.layout.shapes if shape.yref=='y2')
    assert line.y0==pytest.approx(limit) and line.y1==pytest.approx(limit)
    assert line.line.dash=='dash' and line.line.color=='#ef4444'
    assert fig.layout.yaxis2.range[1]>limit
    boundary=next(trace for trace in fig.data if trace.name.startswith('Engine limit'))
    assert boundary.xaxis=='x' and boundary.yaxis=='y'
    assert boundary.line.dash=='dash' and boundary.line.color=='#ef4444'
    for h,q,n in zip(boundary.x,boundary.y,boundary.customdata):
        if q is not None:
            assert curve_value(pump,h,n,'power')==pytest.approx(limit)
            assert q==pytest.approx(curve_value(pump,h,n)*(3.6 if unit=='m³/h' else 1))

def test_engine_line_visible_above_source_power_axis():
    pump=load_pumps()['BP16M'];drive=Drive(engine_model='F6L413F')
    fig=performance_plot(pump,drive=drive)
    assert fig.layout.yaxis2.range[1]>engine_pump_limit_kw(drive)>pump['source_chart']['power']['range'][1]
    assert any('no equal-power boundary' in annotation.text for annotation in fig.layout.annotations)

@pytest.mark.parametrize('engine',list(ENGINE_POWER_FRACTIONS))
@pytest.mark.parametrize('unit',['L/s','m³/h'])
@pytest.mark.parametrize('theme',['light','dark'])
def test_engine_wear_range_boundaries(engine,unit,theme):
    pump=load_pumps()['WA50-2']
    drive=Drive(engine_model=engine,extra_shaft_kw=1,transmission_efficiency=.85)
    fractions=ENGINE_POWER_FRACTIONS[engine]
    fig=apply_theme(performance_plot(pump,drive=drive,flow_unit=unit,
        engine_fraction_range=fractions),theme)
    lines=[shape for shape in fig.layout.shapes if shape.yref=='y2']
    boundaries=[trace for trace in fig.data if trace.name.startswith('Engine limit')]
    assert len(lines)==len(boundaries)==2
    for line,trace,fraction in zip(lines,boundaries,fractions):
        limit=ENGINES[engine]*fraction*.85-1
        assert line.y0==line.y1==pytest.approx(limit)
        assert line.line.dash=='dash'
        assert fig.layout.yaxis2.range[0]<=limit<fig.layout.yaxis2.range[1]
        for head,q,rpm in zip(trace.x,trace.y,trace.customdata):
            if q is not None:
                assert curve_value(pump,head,rpm,'power')==pytest.approx(limit)
                assert q==pytest.approx(curve_value(pump,head,rpm)*(3.6 if unit=='m³/h' else 1))
    assert 'Lower wear limit' in boundaries[0].name
    assert 'Upper wear limit' in boundaries[1].name

def test_engine_wear_range_requires_valid_drive_and_bounds():
    pump=load_pumps()['WA50-2']
    with pytest.raises(ValueError,match='Engine fraction range'):
        performance_plot(pump,engine_fraction_range=(.6,.66))
    with pytest.raises(ValueError,match='Engine fraction range'):
        performance_plot(pump,drive=Drive(),engine_fraction_range=(.7,.6))

def test_low_engine_boundary_and_field_power_marker_visible():
    pump=load_pumps()['BP16M']
    drive=Drive(transmission_efficiency=.5,engine_derating=.5,extra_shaft_kw=8.5)
    head=100;rpm=900;q=curve_value(pump,head,rpm)
    check=dict(compare_actual(pump,q,head,rpm),head_m=head,
        pump_kw=curve_value(pump,head,rpm,'power'))
    fig=performance_plot(pump,field_check=check,drive=drive,flow_unit='L/s')
    boundary=next(trace for trace in fig.data if trace.name.startswith('Engine limit'))
    flows=[q for q in boundary.y if q is not None]
    assert fig.layout.yaxis.range[0]<=min(flows)<pump['source_chart']['flow']['range'][0]/3.6
    marker=next(trace for trace in fig.data if trace.name=='Estimated power at actual RPM')
    assert marker.yaxis=='y2' and marker.y[0]==pytest.approx(check['pump_kw'])
    assert fig.layout.yaxis2.range[1]>marker.y[0]
