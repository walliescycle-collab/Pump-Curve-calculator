import sys
from pathlib import Path
import numpy as np
import pytest
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hydraulics import load_pumps,Installation,system_head
from plots import performance_plot

@pytest.mark.parametrize('name',list(load_pumps()))
def test_source_performance_layout_and_knots(name):
    pump=load_pumps()[name];chart=pump['source_chart']
    fig=performance_plot(pump)
    for axis,spec in [('xaxis','head'),('xaxis2','head'),('yaxis','flow'),('yaxis2','power')]:
        actual=fig.layout[axis];expected=chart[spec]
        assert list(actual.range)==expected['range']
        assert actual.autorange is False
        assert actual.title.text==expected['label']
        assert actual.dtick==expected['tick']
        assert actual.showgrid==expected['grid']
        if expected['minor'] and expected['minor']<expected['tick']:
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
