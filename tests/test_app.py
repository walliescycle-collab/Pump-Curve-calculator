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
    widget(at.radio,'Enter test steps as').set_value('Pump-shaft RPM').run()
    assert not at.exception
    widget(at.checkbox,'Enable up to 24 steps').check().run()
    widget(at.number_input,'Number of test steps').set_value(24).run()
    assert not at.exception
    widget(at.radio,'Lift assumption').set_value('Use each step’s pumping water level').run()
    assert not at.exception
    widget(at.selectbox,'Pump to inspect').set_value('WA110-2').run()
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
    widget(at.selectbox,'Installed diesel engine').set_value('F6L413FW').run()
    widget(at.selectbox,'Pump to inspect').set_value('BP16M').run()
    assert not at.exception
    assert widget(at.selectbox,'Installed diesel engine').value=='F6L413FW'
    assert at.session_state['engine_model']=='F6L413FW'
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
    widget(at.selectbox,'Pump to inspect').set_value('BP40M').run()
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
    widget(at.selectbox,'Installed diesel engine').set_value('F6L413FW').run()
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
    drive=asdict(Drive(engine_model='F6L413FW'))
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
    assert widget(at.selectbox,'Installed diesel engine').value==('F3L912' if legacy else 'F6L413FW')
    assert widget(at.selectbox,'Pump to inspect').value=='BP40M'
    assert widget(at.radio,'Enter test steps as').value=='Pump-shaft RPM'
    if legacy:
        assert any('fixed continuous ratings at 2300 RPM' in info.value and 'No installed engine was saved' in info.value for info in at.info)
    else:
        assert any(info.value=='Setup restored.' for info in at.info)
