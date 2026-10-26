from pathlib import Path
from streamlit.testing.v1 import AppTest
import pytest
import json
import streamlit as st
from dataclasses import asdict
from hydraulics import Installation,Drive
pytestmark=pytest.mark.filterwarnings('ignore::hydraulics.LowRPMEstimateWarning')
APP=Path(__file__).resolve().parents[1]/'app.py'
def widget(items,label):return next(x for x in items if x.label==label)
def test_default_and_rpm_24_steps():
    at=AppTest.from_file(str(APP),default_timeout=60).run()
    assert not at.exception
    assert len(at.metric)>=4
    assert widget(at.radio,'Performance curve flow units').value=='L/s'
    for label in ['Pump selection','Pump being tested','Inspect source']:
        assert widget(at.selectbox,label).value=='WA50-2'
    inputs=next(frame.value for frame in at.dataframe if frame.key=='input_yield_4')
    assert inputs['value'].tolist()==[3.,4.,6.,8.]
    widget(at.radio,'Enter test steps as').set_value('Pump-shaft RPM').run()
    assert not at.exception
    widget(at.checkbox,'Enable up to 24 steps').check().run()
    widget(at.number_input,'Number of test steps').set_value(24).run()
    assert not at.exception
    widget(at.radio,'Lift assumption').set_value('Use each step’s pumping water level').run()
    assert not at.exception
    widget(at.selectbox,'Pump selection').set_value('WA110-2').run()
    assert not at.exception
    widget(at.radio,'Field head source').set_value('Enter total differential pump head').run()
    assert not at.exception
    assert len(at.get('download_button'))>=8

def test_engine_selection_table_and_source_graphs():
    at=AppTest.from_file(str(APP),default_timeout=60).run()
    assert not at.exception
    assert widget(at.selectbox,'Installed diesel engine').value=='F3L912'
    table=next(frame.value for frame in at.dataframe if 'Minimum engine size' in frame.value.columns)
    assert 'Pump diameter (mm)' in table and 'Minimum bore (mm)' in table
    assert 'Engine candidate' not in table
    assert table.loc[table.Pump=='DW2402','Minimum bore (mm)'].iloc[0]==127
    assert 'Installed engine adequate' not in table
    assert {'Min motor kW','Max curve kW','Power curve RPM'}<=set(table.columns)
    widget(at.selectbox,'Installed diesel engine').set_value('F6L413F').run()
    widget(at.radio,'Performance curve flow units').set_value('m³/h').run()
    widget(at.selectbox,'Pump selection').set_value('BP16M').run()
    assert not at.exception
    assert widget(at.selectbox,'Installed diesel engine').value=='F6L413F'
    assert at.session_state['engine_model']=='F6L413F'
    specs=[json.loads(chart.proto.spec) for chart in at.get('plotly_chart')]
    source=next(spec for spec in specs if 'source performance curves' in spec['layout'].get('title',{}).get('text',''))
    assert source['layout']['yaxis']['range']==[2,18]
    assert source['layout']['xaxis']['title']['text']=='METER HEAD (m)'
    assert source['layout']['yaxis2']['title']['text']=='POWER (kW)'
    system=[trace for trace in source['data'] if trace['name'].startswith('System')]
    assert len(system)==1 and system[0]['xaxis']=='x' and system[0]['yaxis']=='y'
    assert not any(x.label=='Engine operating speed for sizing (RPM)' for x in at.number_input)

def test_low_rpm_warning_in_ui():
    at=AppTest.from_file(str(APP),default_timeout=60).run()
    widget(at.radio,'Enter test steps as').set_value('Pump-shaft RPM').run()
    at.session_state['restored_steps']=[{'value':50.,'water_level_m':60.}]*4
    at.session_state['restored_mode']='rpm'
    widget(at.selectbox,'Pump selection').set_value('BP40M').run()
    assert not at.exception
    assert any('low-RPM estimate' in warning.value for warning in at.warning)
    details=next(frame.value for frame in at.dataframe if 'engine_required_kw' in frame.value.columns)
    assert all(details.rpm==50) and all(details.pump_kw>0)

def test_advanced_drive_settings_group_and_values():
    at=AppTest.from_file(str(APP),default_timeout=60).run()
    assert not at.exception
    advanced=next(item for item in at.expander if item.label=='Advanced settings')
    assert advanced.proto.expanded is False
    assert {item.label for item in advanced.slider}=={'Transmission efficiency','Available engine power fraction'}
    assert {item.label for item in advanced.number_input}=={'Additional shaft/bearing mechanical loss (kW)','Diesel sizing factor'}
    widget(advanced.slider,'Transmission efficiency').set_value(.85).run()
    widget(at.number_input,'Additional shaft/bearing mechanical loss (kW)').set_value(1.5).run()
    widget(at.number_input,'Diesel sizing factor').set_value(1.4).run()
    widget(at.slider,'Available engine power fraction').set_value(.8).run()
    widget(at.selectbox,'Installed diesel engine').set_value('F6L413F').run()
    assert not at.exception
    assert at.session_state['efficiency']==.85
    assert at.session_state['extra']==1.5
    assert at.session_state['margin']==1.4
    assert at.session_state['derating']==.8

def test_engineering_table_column_headers():
    at=AppTest.from_file(str(APP),default_timeout=60).run()
    assert not at.exception
    detail=next(frame for frame in at.dataframe if 'engine_required_kw' in frame.value.columns)
    reference=next(frame for frame in at.dataframe if 'base_limit_ls' in frame.value.columns)
    detail_config=json.loads(detail.proto.columns)
    reference_config=json.loads(reference.proto.columns)
    assert detail_config['head_m']['label']=='Total Dynamic Head [m]'
    assert detail_config['yield_ls']['label']=='Volumetric Flow Rate [L/s]'
    assert reference_config['column_mm']['label']=='Nominal Column Diameter [mm]'
    assert reference_config['base_limit_ls']['label']=='Reference Flow Limit [L/s]'
    for frame,config in [(detail,detail_config),(reference,reference_config)]:
        for column in frame.value.columns:
            assert config[column]['label'].endswith(']')
            assert '_' not in config[column]['label']
            if column not in ['step','error','pump','legacy_engine']:
                assert config[column]['type_config']['format']=='%.2f'

@pytest.mark.parametrize('legacy',[False,True])
def test_restore_installed_engine_and_legacy_notice(monkeypatch,legacy):
    drive=asdict(Drive(engine_model='F6L413F'))
    if legacy:
        drive.pop('engine_model')
        drive['engine_speed_rpm']=1800
    setup={'version':1 if legacy else 2,'project':'Restored test','installation':asdict(Installation()),
        'drive':drive,'mode':'rpm','steps':[{'value':50.,'water_level_m':60.}]*4,'pump':'BP40M'}
    class Upload:
        def getvalue(self):return json.dumps(setup).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *args,**kwargs:Upload())
    at=AppTest.from_file(str(APP),default_timeout=60).run()
    widget(at.button,'Restore complete setup').click().run()
    assert not at.exception
    assert widget(at.selectbox,'Installed diesel engine').value==('F3L912' if legacy else 'F6L413F')
    assert widget(at.selectbox,'Pump selection').value=='BP40M'
    assert widget(at.radio,'Enter test steps as').value=='Pump-shaft RPM'
    if legacy:
        assert any('fixed continuous ratings at 2300 RPM' in info.value and 'No installed engine was saved' in info.value for info in at.info)
    else:
        assert any(info.value=='Setup restored.' for info in at.info)

def test_simplified_units_and_field_plots():
    at=AppTest.from_file(str(APP),default_timeout=60).run()
    widget(at.selectbox,'Pump selection').set_value('BP40M').run()
    widget(at.selectbox,'Pump being tested').set_value('BP40M').run()
    widget(at.radio,'Performance curve flow units').set_value('L/s').run()
    widget(at.checkbox,'Simplified').check().run()
    assert not at.exception
    assert len(at.tabs)==2
    assert len(at.dataframe)==1 and at.dataframe[0].key.startswith('input_')
    assert not at.metric
    assert not at.get('download_button')
    specs=[json.loads(chart.proto.spec) for chart in at.get('plotly_chart')]
    curves=[spec for spec in specs if 'source performance curves' in spec['layout'].get('title',{}).get('text','')]
    assert len(curves)==2
    assert all(spec['layout']['yaxis']['title']['text']=='YIELD (L/s)' for spec in curves)
    assert any('RPM deviation:' in spec['layout'].get('title',{}).get('text','') for spec in specs)
    assert specs[0]['layout']['title']['text'].startswith('Head contribution')
    widget(at.checkbox,'Simplified').uncheck().run()
    assert not at.exception and len(at.tabs)==4 and len(at.dataframe)>0
    assert widget(at.selectbox,'Pump selection').value=='BP40M'

def test_map_pin_entry_and_stale_elevations(monkeypatch):
    import requests
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'status':'OK','results':[{'elevation':100},{'elevation':110}]}
    monkeypatch.setattr(requests,'get',lambda *args,**kwargs:Response())
    at=AppTest.from_file(str(APP),default_timeout=60).run()
    widget(at.radio,'Terrain entry').set_value('Google Maps / phone location').run()
    assert not at.exception
    widget(at.text_input,'Borehole Google Maps pin / coordinates').set_value('-34, 19').run()
    widget(at.button,'Use borehole pin').click().run()
    assert widget(at.number_input,'Borehole latitude').value==-34
    widget(at.button,'Look up terrain elevations').click().run()
    widget(at.button,'Use this elevation difference').click().run()
    assert widget(at.number_input,'Discharge elevation above borehole (m)').value==10
    widget(at.number_input,'Outlet latitude').set_value(-33.5).run()
    assert not at.exception
    assert not any(item.label=='Use this elevation difference' for item in at.button)
    assert any('Coordinates changed' in item.value for item in at.warning)

def test_restore_old_v6_name(monkeypatch):
    setup={'installation':asdict(Installation()),'drive':dict(asdict(Drive()),engine_model='F6L413FW'),
        'mode':'yield','steps':[{'value':3.,'water_level_m':60.}],'flow_unit':'L/s'}
    class Upload:
        def getvalue(self):return json.dumps(setup).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *args,**kwargs:Upload())
    at=AppTest.from_file(str(APP),default_timeout=60).run()
    widget(at.button,'Restore complete setup').click().run()
    assert not at.exception
    assert widget(at.selectbox,'Installed diesel engine').value=='F6L413F'
    assert widget(at.radio,'Performance curve flow units').value=='L/s'

def test_engine_limit_warnings_in_both_views_and_simplified():
    at=AppTest.from_file(str(APP),default_timeout=60).run()
    widget(at.number_input,'Additional shaft/bearing mechanical loss (kW)').set_value(100.).run()
    assert not at.exception
    warnings=[warning.value for warning in at.warning]
    assert any('Step ' in warning and 'Engine power limit exceeded' in warning for warning in warnings)
    assert any('Field operating point: Engine power limit exceeded' in warning for warning in warnings)
    widget(at.checkbox,'Simplified').check().run()
    assert not at.exception
    assert sum('Engine power limit exceeded' in warning.value for warning in at.warning)>=2
    specs=[json.loads(chart.proto.spec) for chart in at.get('plotly_chart')]
    curves=[spec for spec in specs if 'source performance curves' in spec['layout'].get('title',{}).get('text','')]
    assert len(curves)==2
    assert all(any(trace['name'].startswith('Engine limit') for trace in spec['data']) for spec in curves)
    widget(at.number_input,'Additional shaft/bearing mechanical loss (kW)').set_value(0.).run()
    widget(at.selectbox,'Installed diesel engine').set_value('F6L413F').run()
    assert not at.exception
    assert not any('Engine power limit exceeded' in warning.value for warning in at.warning)
    widget(at.selectbox,'Pump being tested').set_value('WA110-2').run()
    widget(at.number_input,'Measured pump-shaft RPM').set_value(1100.).run()
    assert not at.exception
    assert any('Field engine-power check unavailable' in warning.value for warning in at.warning)
