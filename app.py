"""AB Pumps installation planner. Run: streamlit run app.py"""
from dataclasses import asdict,replace
from io import BytesIO
import json,math
import pandas as pd
import numpy as np
import streamlit as st
from hydraulics import *
from plots import (system_plot,friction_plot,performance_plot,head_contribution_plot,
    rpm_comparison_plot,apply_theme)
from locations import terrain_controls

st.set_page_config(page_title='AB Pumps | Installation planner',page_icon='💧',layout='wide')
st.markdown('''<style>
.block-container {padding-top:2rem;max-width:1450px}
[data-testid="stMetric"] {border:1px solid var(--secondary-background-color);border-radius:10px;padding:14px}
</style>''',unsafe_allow_html=True)
st.title('Test pump installation planner')
st.caption('Open the sidebar (top-left arrow) to change installation details.')
pumps=load_pumps()


def show_plot(fig,filename=None):
    apply_theme(fig,st.context.theme.type or 'light')
    st.plotly_chart(fig,width='stretch',theme=None,config={'displaylogo':False,
        'toImageButtonOptions':{'format':'png','filename':filename or 'AB_Pumps','scale':2}})
    return fig


def restore_setup():
    try:
        data=json.loads(restore.getvalue())
        si=Installation(**data['installation']).validate()
        drive_data=dict(data['drive'])
        old_speed=drive_data.pop('engine_speed_rpm',None)
        missing_engine='engine_model' not in drive_data
        renamed=drive_data.get('engine_model')=='F6L413FW'
        if renamed:drive_data['engine_model']='F6L413F'
        sd=Drive(**drive_data).validate()
        ss=data['steps'];sm=data['mode']
        if sm not in ['yield','rpm'] or not 1<=len(ss)<=24:raise ValueError('Invalid saved steps')
        for step in ss:
            finite(step['value'],'Step value');nonnegative(step['water_level_m'],'Water level')
            if not 0<step['value']<=(60 if sm=='yield' else 3000) or step['water_level_m']>si.depth_m:
                raise ValueError('Invalid saved step values')
        unit=data.get('flow_unit','L/s')
        if unit not in ['m³/h','L/s']:raise ValueError('Invalid saved flow unit')
        if not isinstance(data.get('simplified',False),bool):raise ValueError('Invalid simplified setting')
        fields={'project':data.get('project','Restored installation'),'depth':si.depth_m,
            'bore':si.bore_mm,'column':si.column_mm,'hose':si.hose_mm,
            'length':si.hose_length_m,'elevation':si.elevation_m,
            'lift_basis':'Design: water down to pump' if si.design_full_depth else 'Use each step’s pumping water level',
            'drive_rpm':sd.pump_rpm_limit,'drive_kw':sd.drive_rating_kw,
            'efficiency':sd.transmission_efficiency,'extra':sd.extra_shaft_kw,
            'margin':sd.sizing_margin,'derating':sd.engine_derating,'engine_model':sd.engine_model,
            'expanded':len(ss)>4,'mode_label':'Yield (L/s)' if sm=='yield' else 'Pump-shaft RPM',
            f'count_{len(ss)>4}':len(ss),'restored_steps':ss,'restored_mode':sm,
            'flow_unit':unit,'simplified':data.get('simplified',False)}
        for key in list(st.session_state):
            if key.startswith('input_'):del st.session_state[key]
        for key,val in fields.items():st.session_state[key]=val
        if data.get('pump') in pumps:st.session_state['selected_pump']=data['pump']
        notice='Setup restored.'
        if old_speed is not None:notice+=' Legacy engine-speed setting replaced by fixed continuous ratings at 2300 RPM.'
        if missing_engine:notice+=' No installed engine was saved: F3L912 selected; review the engine power limit.'
        if renamed:notice+=' Legacy F6L413FW name updated to F6L413F (V6), 102 kW.'
        st.session_state['restore_notice']=notice
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        st.session_state['restore_notice']=f'Cannot restore setup: {exc}'


with st.sidebar:
    st.subheader('Installation')
    project=st.text_input('Project / borehole',value='New installation',key='project')
    depth=st.number_input('Pump installation depth (m)',1.,1000.,100.,1.,key='depth')
    bore=st.number_input('Borehole internal diameter (mm)',50.,1000.,200.,1.,key='bore')
    col=st.selectbox('Nominal column diameter (mm)',[40,50,65,80,100,150],index=3,key='column')
    hose=st.selectbox('PVC layflat nominal diameter (mm)',[50,65,80,100,150,200],index=3,key='hose')
    length=st.number_input('Layflat length along route (m)',0.,10000.,100.,10.,key='length')
    elevation=st.number_input('Discharge elevation above borehole (m)',-1000.,1000.,0.,key='elevation')
    full=st.radio('Lift assumption',['Design: water down to pump','Use each step’s pumping water level'],key='lift_basis')=='Design: water down to pump'
    simplified=st.checkbox('Simplified',key='simplified')
    flow_unit=st.radio('Performance curve flow units',['m³/h','L/s'],index=1,horizontal=True,key='flow_unit')
    with st.expander('Diesel drive settings'):
        engine=st.selectbox('Installed diesel engine',list(ENGINES),key='engine_model',
            format_func=lambda name:f'{name}{" (V6)" if name=="F6L413F" else ""} — {ENGINES[name]:g} kW')
        st.caption('Red dashed curves show usable engine power at the pump. Exceeded duties are warned, not rejected solely on engine power. Minimum-engine recommendations remain duty-based.')
        rpmcap=st.number_input('Maximum pump-shaft RPM of drive',1.,3000.,1100.,50.,key='drive_rpm')
        drivekw=st.number_input('Angle-drive power rating (kW)',1.,500.,float(round(60*.745699872,2)),1.,key='drive_kw')
        with st.expander('Advanced settings',expanded=False):
            efficiency=st.slider('Transmission efficiency',.5,1.,.90,.01,key='efficiency')
            extra=st.number_input('Additional shaft/bearing mechanical loss (kW)',0.,100.,0.,.1,key='extra')
            margin=st.number_input('Diesel sizing factor',1.,2.,1.33,.01,key='margin')
            derate=st.slider('Available engine power fraction',.5,1.,.90,.01,key='derating')
            st.caption('Continuous engine ratings apply at 2300 engine RPM. Confirm transmission ratio and starting torque.')
    with st.expander('Save or restore setup'):
        restore=st.file_uploader('Load saved setup JSON',type=['json'])
        st.button('Restore complete setup',on_click=restore_setup,disabled=restore is None)
        if 'restore_notice' in st.session_state:st.info(st.session_state['restore_notice'])
    with st.expander('Calculation assumptions'):
        st.caption('Head = lift + column friction + discharge elevation + layflat friction. Column friction uses full installation depth. Fittings, outlet pressure and discharge velocity head are excluded. Curve and friction estimates require site verification.')

installation=Installation(depth,col,length,hose,elevation,bore,full)
drive=Drive(rpmcap,drivekw,efficiency,extra,margin,derate,engine)
tabs=st.tabs(['Plan & select','Field curve check'] if simplified else
    ['1 · Plan & select','2 · Curves & diesel','3 · Field curve check','4 · Friction & sources'])
with tabs[0]:
    terrain_controls(terrain_elevations)
    a,b,c=st.columns([2,1,1])
    mode_label=a.radio('Enter test steps as',['Yield (L/s)','Pump-shaft RPM'],horizontal=True,key='mode_label')
    mode='yield' if mode_label.startswith('Yield') else 'rpm'
    expanded=b.checkbox('Enable up to 24 steps',key='expanded')
    n=c.number_input('Number of test steps',1,24 if expanded else 4,4,1,key=f'count_{expanded}')
    defaults=np.linspace(3,5.5,n) if mode=='yield' else np.linspace(900,1100,n)
    if mode=='yield' and n==4:defaults=np.array([3.,4.,6.,8.])
    frame=pd.DataFrame({'value':defaults,'water_level_m':[float(depth)]*n})
    if 'restored_steps' in st.session_state and st.session_state.get('restored_mode')==mode:
        frame=pd.DataFrame(st.session_state['restored_steps']).reindex(range(n)).fillna(
            {'value':2. if mode=='yield' else 1000.,'water_level_m':depth})
    edited=st.data_editor(frame,hide_index=False,num_rows='fixed',width='stretch',key=f'input_{mode}_{n}',
        column_config={'value':st.column_config.NumberColumn('Yield (L/s)' if mode=='yield' else 'Pump-shaft RPM',
            min_value=.01 if mode=='yield' else 1.,max_value=60. if mode=='yield' else 3000.,
            step=.01 if mode=='yield' else 1.,required=True),
        'water_level_m':st.column_config.NumberColumn('Pumping water depth (m below ground)',min_value=0.,max_value=float(depth),required=True)})
    steps=edited.to_dict('records')
    group=st.multiselect('Pump families',['WASA','Mono','Orbit','NOV / DW'],default=['WASA','Mono','Orbit','NOV / DW'])
    names=[name for name,p in pumps.items() if ('NOV / DW' if name.startswith('DW') else p['brand']) in group]
    if not names:st.info('Select at least one pump family.');st.stop()
    results={name:evaluate(pumps[name],steps,installation,drive,mode) for name in names}
    summary=[]
    for name,res in results.items():
        power=pump_power_range(pumps[name])
        vals=[r['yield_ls'] for r in res['rows'] if 'yield_ls' in r]
        summary.append({'Pump':name,'Pump diameter (mm)':pumps[name]['pump_diameter_mm'],
            'Minimum bore (mm)':pumps[name]['minimum_bore_mm'],'Result':res['status'],
            'Min motor kW':power['minimum_kw'],'Max curve kW':power['maximum_kw'],
            'Power curve RPM':power['power_rpm'],
            'Minimum engine size':res['recommended_engine'] or ('Above available range' if res['required_engine_kw'] is not None else 'Unavailable'),
            'Required engine kW':res['required_engine_kw'],'Max yield L/s':max(vals) if vals else None,
            'Reason / qualification':'; '.join(res['reasons']+res['conditions'])})
    rank={'Suitable for planning':0,'Conditional':1,'Not suitable':2}
    table=pd.DataFrame(summary).assign(_rank=lambda df:df['Result'].map(rank)).sort_values(
        ['_rank','Required engine kW']).drop(columns='_rank')
    if not simplified:
        st.subheader('Pumps for every test step')
        st.dataframe(table,hide_index=True,width='stretch',column_config={
            key:st.column_config.NumberColumn(format='%.1f') for key in
            ['Min motor kW','Max curve kW','Required engine kW']})
        st.caption('Min motor kW: published motor minimum; blank = not supplied. Max curve kW: highest absorbed kW on the listed highest-RPM power curve, within rated head. These are not diesel ratings.')
    pump_names=list(table['Pump'])
    selection=st.selectbox('Pump selection',pump_names,
        index=pump_names.index('WA50-2') if 'WA50-2' in pump_names else 0,key='selected_pump')
    pump=pumps[selection];result=results[selection]
    if result['reasons']:st.error('\n\n'.join(result['reasons']))
    if result['conditions']:st.warning('\n\n'.join(result['conditions']))
    if any('head_m' in r for r in result['rows']):
        show_plot(head_contribution_plot(pump,result),f'{selection}_head')
    else:st.info('Head contribution unavailable: no test step has a calculated head.')
    sourcefig=show_plot(performance_plot(pump,result,installation,steps,flow_unit,drive=drive),f'{selection}_performance')
    detail=pd.DataFrame(result['rows'])
    if not simplified:
        st.download_button('Download pump performance graphs',sourcefig.to_html(include_plotlyjs=True),f'{selection}_performance.html','text/html')
        st.subheader('Four-part head calculation')
        cols=['step','yield_ls','rpm','water_level_m','lift_m','column_loss_m','elevation_m',
            'layflat_loss_m','head_m','pump_kw','engine_required_kw','error']
        labels={'step':'Test Step [-]','yield_ls':'Volumetric Flow Rate [L/s]',
            'rpm':'Pump-Shaft Rotational Speed [rpm]','water_level_m':'Pumping Water Depth [m]',
            'lift_m':'Static Lift Head [m]','column_loss_m':'Column Friction Head Loss [m]',
            'elevation_m':'Discharge Elevation Difference [m]','layflat_loss_m':'Layflat Friction Head Loss [m]',
            'head_m':'Total Dynamic Head [m]','pump_kw':'Pump Absorbed Power [kW]',
            'engine_required_kw':'Required Engine Power [kW]','error':'Calculation Qualification [-]'}
        st.dataframe(detail.reindex(columns=cols),hide_index=True,width='stretch',
            column_config={key:label if key in ['step','error'] else st.column_config.NumberColumn(label,format='%.2f') for key,label in labels.items()})
        notes=sorted(set(note for row in result['rows'] for note in row.get('notes',[])))
        if notes:
            with st.expander('Flow and friction qualifications'):
                for note in notes:st.write('• '+note)
        st.subheader('AB Pumps quick-reference cross-check')
        legacy=pd.read_csv(ROOT/'data/legacy_limits.csv')
        subset=legacy[(legacy.pump==selection)&(legacy.column_mm==col)]
        reference_labels={'pump':'Pump Model [-]','column_mm':'Nominal Column Diameter [mm]',
            'depth_m':'Pump Installation Depth [m]','base_limit_ls':'Reference Flow Limit [L/s]',
            'large_drive_limit_ls':'Larger-Drive Reference Flow Limit [L/s]',
            'hose_mm':'Nominal Layflat Diameter [mm]','hose_length_m':'Layflat Route Length [m]',
            'elevation_m':'Discharge Elevation Difference [m]','legacy_engine':'Historical Minimum Engine / Drive Guidance [-]'}
        st.dataframe(subset,hide_index=True,width='stretch',column_config={
            key:label if key in ['pump','legacy_engine'] else st.column_config.NumberColumn(label,format='%.2f')
            for key,label in reference_labels.items()})
        st.caption('Historical guidance only: 100 m reference hose, zero elevation, usually 1100 pump RPM. V6 = F6L413F. Confirm the actual installation.')
        exact=subset[subset.depth_m==depth]
        if len(exact) and full and length==100 and elevation==0 and hose==exact.iloc[0].hose_mm:
            ref=exact.iloc[0]
            if pd.notna(ref.base_limit_ls):
                st.info(f"Matching reference installation: {ref.base_limit_ls:g} L/s base limit; {ref.legacy_engine}. Historical guidance does not replace calculated limits.")

if not simplified:
    with tabs[1]:
        st.subheader(f'{selection} · operating plan')
        valid=[r for r in result['rows'] if 'rpm' in r]
        metrics=st.columns(4)
        metrics[0].metric('Peak yield',f"{max([r['yield_ls'] for r in valid],default=0):.2f} L/s")
        metrics[1].metric('Peak total head',f"{max([r['head_m'] for r in valid],default=0):.1f} m")
        metrics[2].metric('Peak pump speed',f"{max([r['rpm'] for r in valid],default=0):.0f} RPM")
        metrics[3].metric('Minimum diesel size',result['recommended_engine'] or 'Not established')
        peakq=max([r['yield_ls'] for r in valid],default=10)
        qmax=st.slider('Chart maximum yield (L/s)',1.,60.,float(min(60,max(10,math.ceil(peakq*1.4)))),1.)
        fig=show_plot(system_plot(pump,installation,steps,result,qmax))
        req=result['required_engine_kw']
        if req is not None:
            options=pd.DataFrame(engine_options(req,drive)).drop(columns='installed')
            st.dataframe(options,hide_index=True,width='stretch')
        with st.expander('Diesel sizing details'):
            st.caption('Required rating = (absorbed kW + mechanical loss) ÷ transmission efficiency × sizing factor. Red engine limit = continuous rating × available fraction × transmission efficiency − mechanical loss, without the sizing margin. Exceeding this limit produces a warning; angle-drive kW and RPM limits still apply.')
            st.write(f"Starting torque: {pump['starting_torque_nm'] if pump['starting_torque_nm'] is not None else 'not supplied'} Nm.")
        c1,c2,c3,c4=st.columns(4)
        export_detail=detail.copy()
        if 'notes' in export_detail:export_detail['notes']=export_detail.notes.apply(lambda value:'; '.join(value) if isinstance(value,list) else '')
        c1.download_button('Download step CSV',export_detail.to_csv(index=False),'AB_Pumps_steps.csv','text/csv')
        b=BytesIO()
        with pd.ExcelWriter(b,engine='openpyxl') as writer:
            export_detail.to_excel(writer,index=False,sheet_name='Test steps')
            table.to_excel(writer,index=False,sheet_name='Pump comparison')
            pd.DataFrame([asdict(installation)]).to_excel(writer,index=False,sheet_name='Installation')
            pd.DataFrame([asdict(drive)]).to_excel(writer,index=False,sheet_name='Drive assumptions')
            pd.DataFrame([{'pump':selection,'source':pump['source'],'quality':pump['quality'],'notes':pump['notes']}]).to_excel(writer,index=False,sheet_name='Source')
            for sheet in writer.sheets.values():
                sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
                for cells in sheet.columns:sheet.column_dimensions[cells[0].column_letter].width=min(60,max(14,max(len(str(cell.value or '')) for cell in cells)+2))
        c2.download_button('Download Excel',b.getvalue(),'AB_Pumps_installation.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        c3.download_button('Download interactive plot',fig.to_html(include_plotlyjs=True),'AB_Pumps_curves.html','text/html')
        config={'version':3,'project':project,'installation':asdict(installation),'drive':asdict(drive),
            'mode':mode,'steps':steps,'pump':selection,'flow_unit':flow_unit,'simplified':simplified}
        c4.download_button('Save setup JSON',json.dumps(config,indent=2),'AB_Pumps_setup.json','application/json')

with tabs[1 if simplified else 2]:
    st.subheader('Field curve check')
    fp=st.selectbox('Pump being tested',list(pumps),index=list(pumps).index(selection),key='field_pump')
    p=pumps[fp]
    c=st.columns(3)
    fq=c[0].number_input('Measured yield (L/s)',.01,60.,5.,.1)
    fn=c[1].number_input('Measured pump-shaft RPM',1.,3000.,1000.,10.)
    tolerance=c[2].number_input('Comparison tolerance (%)',0.,50.,10.,1.)
    fieldbasis=st.radio('Field head source',['Calculate from observed pumping water level','Enter total differential pump head'],horizontal=True)
    fr=None
    if fieldbasis.startswith('Calculate'):
        wl=st.number_input('Observed pumping water depth (m)',0.,float(depth),float(min(60,depth)),1.)
        fr=system_head(fq,replace(installation,design_full_depth=False),wl);fh=fr['head_m']
        st.caption(f'Calculated total head: {fh:.1f} m')
        for note in fr['notes']:st.warning(note)
    else:
        fh=st.number_input('Actual total differential pump head (m)',0.,1000.,100.,1.)
        if not simplified:st.caption('A surface gauge reading alone is not total differential pump head.')
    if fr is not None:
        show_plot(head_contribution_plot(p,{'rows':[dict(fr,step=1)]}))
    field_check=None
    field_power=None
    try:
        field_power=curve_value(p,fh,fn,'power')
        warning=engine_power_warning(field_power,drive)
        if warning:st.warning(f'Field operating point: {warning}')
        for note in low_speed_notes(p,fn,('power',)):st.warning(note)
    except CurveRangeError as exc:
        st.warning(f'Field engine-power check unavailable: {exc}. Power is not extrapolated beyond published limits.')
    try:
        check=compare_actual(p,fq,fh,fn,tolerance)
        field_check=dict(check,head_m=fh,pump_kw=field_power)
    except ValueError as exc:st.info(f'Comparison unavailable: {exc}. Head and upper-RPM limits are not extrapolated.')
    if field_check is not None:
        for note in check['notes']:st.warning(note)
        (st.success if abs(check['rpm_difference_pct'])<=tolerance else st.warning)(check['status'])
        show_plot(performance_plot(p,flow_unit=flow_unit,field_check=field_check,drive=drive),f'{fp}_field_performance')
        show_plot(rpm_comparison_plot(check),f'{fp}_field_rpm')
        if not simplified:
            cc=st.columns(3)
            cc[0].metric('Expected pump speed',f"{check['expected_rpm']:.0f} RPM")
            cc[1].metric('Actual versus expected RPM',f"{check['rpm_difference_pct']:+.1f}%")
            cc[2].metric('Expected yield at actual RPM',f"{check['expected_yield_ls']:.2f} L/s")
            st.caption('Positive RPM deviation means more speed than expected is needed for the measured flow/head. Tolerance is a comparison aid, not permission to exceed ratings or a diagnosis of pump wear.')
            st.download_button('Download field comparison',pd.DataFrame([dict(field_check,pump=fp)]).to_csv(index=False),'AB_Pumps_field_check.csv','text/csv')
    else:
        show_plot(performance_plot(p,flow_unit=flow_unit,drive=drive),f'{fp}_field_performance')

if not simplified:
    with tabs[3]:
        st.subheader('Friction charts')
        show_plot(friction_plot('column'));show_plot(friction_plot('hose'))
        with st.expander('Friction model & limitations'):
            st.caption('Column: approximate CEMO chart; Q² extension outside range; 150 mm scaled from 100 mm. Layflat: Rain-Flo US units converted to metric; Q^1.85 extensions; 200 mm diameter-scaling estimate. Velocity uses nominal waterways and assumed shaft diameters. Verify actual pipe sizes and route.')
        frows=[]
        for q in np.arange(.5,60.01,.5):
            for size in [40,50,65,80,100,150]:
                loss,notes=column_loss(q,100,size);frows.append({'type':'column','diameter_mm':size,'yield_ls':q,'head_loss_m_per_100m':loss,'notes':'; '.join(notes)})
            if q>=1:
                for size in [50,65,80,100,150,200]:
                    loss,notes=layflat_loss(q,100,size);frows.append({'type':'layflat','diameter_mm':size,'yield_ls':q,'head_loss_m_per_100m':loss,'notes':'; '.join(notes)})
        st.download_button('Download metric friction tables',pd.DataFrame(frows).to_csv(index=False),'AB_Pumps_friction_tables.csv','text/csv')
        st.subheader('Pump data and original sheet')
        sourcepump=st.selectbox('Inspect source',list(pumps),index=list(pumps).index(selection));sp=pumps[sourcepump]
        st.write(f"**{sp['quality']}** · {sp['digitisation_note']}")
        with st.expander('Source details'):
            st.write(sp['notes']);st.json({key:value for key,value in sp.items() if key not in ['flow_curves','power_curves']})
        st.image(str(ROOT/sp['source']),width=650)
        st.download_button('Download pump dataset',(ROOT/'data/pumps.json').read_bytes(),'pumps.json','application/json')
        st.download_button('Download curve points CSV',(ROOT/'data/curve_points.csv').read_bytes(),'curve_points.csv','text/csv')
        with st.expander('Original friction and AB quick-reference charts'):
            st.image(str(ROOT/'sources/cemo_friction.jpg'));st.image(str(ROOT/'sources/ab_quick_reference.jpg'))
        st.markdown('[Franklin Mono BP](https://franklin-electric.co.za/products/mono-bp-range/) · [Franklin Orbit GW](https://franklin-electric.co.za/products/orbit-gw-range/) · [Rain-Flo layflat](https://www.rainfloirrigation.com/irrigation/charts-layouts/friction-loss-chart) · [Terrain API](https://www.opentopodata.org/api/)')
