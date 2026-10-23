"""AB Pumps test-installation planner. Run: streamlit run app.py"""
from pathlib import Path
from dataclasses import asdict,replace
from io import BytesIO
import json,math
import pandas as pd
import numpy as np
import streamlit as st
from hydraulics import *
from plots import system_plot,friction_plot,performance_plot
st.set_page_config(page_title='AB Pumps | Installation planner',page_icon='💧',layout='wide')
st.markdown('''<style>
.stApp {background:#f6f8fa} .block-container {padding-top:2rem;max-width:1450px}
h1,h2,h3 {color:#173647} [data-testid="stMetric"]{background:white;border:1px solid #dce6eb;border-radius:10px;padding:14px}
[data-testid="stSidebar"]{background:#eaf1f5}.eyebrow{color:#057f8d;font-weight:700;letter-spacing:.16em;font-size:.8rem}
</style><div class="eyebrow">AB PUMPS · FIELD ENGINEERING</div>''',unsafe_allow_html=True)
st.title('Test pump installation planner')
st.caption('Plan the installation • compare pumps • set the test steps • check field performance')
pumps=load_pumps();legacy=pd.read_csv(ROOT/'data/legacy_limits.csv')
with st.sidebar:
    st.subheader('Installation')
    project=st.text_input('Project / borehole',value='New installation',key='project')
    depth=st.number_input('Pump installation depth (m)',min_value=1.,max_value=1000.,value=100.,step=1.,key='depth')
    bore=st.number_input('Borehole internal diameter (mm)',min_value=50.,max_value=1000.,value=200.,step=1.,key='bore')
    col=st.selectbox('Nominal column diameter (mm)',[40,50,65,80,100,150],index=3,key='column')
    hose=st.selectbox('PVC layflat nominal diameter (mm)',[50,65,80,100,150,200],index=3,key='hose')
    length=st.number_input('Layflat length along route (m)',min_value=0.,max_value=10000.,value=100.,step=10.,key='length')
    elevation=st.number_input('Discharge elevation above borehole (m)',min_value=-1000.,max_value=1000.,value=0.,key='elevation')
    full=st.radio('Lift assumption',['Design: water down to pump','Use each step’s pumping water level'],index=0,key='lift_basis')=='Design: water down to pump'
    st.caption('Design lift uses the full installation depth. Pipe friction always uses the full column length. Fittings, outlet pressure and discharge velocity head are excluded.')
    with st.expander('Diesel drive settings'):
        engine=st.selectbox('Installed diesel engine',list(ENGINES),key='engine_model',format_func=lambda name:f'{name}{" (V6)" if name=="F6L413FW" else ""} — {ENGINES[name]:g} kW')
        st.caption(f'Continuous rating: {ENGINES[engine]:g} kW at 2300 engine RPM. Engine choice is independent of pump model; the comparison reports the minimum engine size for the planned duty.')
        rpmcap=st.number_input('Maximum pump-shaft RPM of drive',1.,3000.,1100.,50.,key='drive_rpm')
        drivekw=st.number_input('Angle-drive power rating (kW)',1.,500.,float(round(60*.745699872,2)),1.,key='drive_kw')
        st.caption('44.74 kW represents a 60 HP angle drive. Enter its actual rating for a small drive; the old sheet gives no small-drive kW rating.')
        with st.expander('Advanced settings',expanded=False):
            efficiency=st.slider('Transmission efficiency',.5,1.,.90,.01,key='efficiency')
            extra=st.number_input('Additional shaft/bearing mechanical loss (kW)',0.,100.,0.,.1,key='extra')
            margin=st.number_input('Diesel sizing factor',1.,2.,1.33,.01,key='margin')
            derate=st.slider('Available engine power fraction',.5,1.,.90,.01,key='derating')
            st.caption('Fixed continuous ratings are for 2300 engine RPM, not pump RPM. Confirm a suitable transmission ratio. The availability fraction allows for fan, site and engine condition losses; it is not an automatic altitude correction.')
    with st.expander('Save or restore setup'):
        restore=st.file_uploader('Load saved setup JSON',type=['json'])
        def restore_setup():
            try:
                data=json.loads(restore.getvalue())
                si=Installation(**data['installation']).validate()
                drive_data=dict(data['drive'])
                old_speed=drive_data.pop('engine_speed_rpm',None)
                missing_engine='engine_model' not in drive_data
                sd=Drive(**drive_data).validate()
                ss=data['steps'];sm=data['mode']
                if sm not in ['yield','rpm'] or not 1<=len(ss)<=24:raise ValueError('Invalid saved steps')
                for step in ss:
                    finite(step['value'],'Step value');nonnegative(step['water_level_m'],'Water level')
                    if not 0<step['value']<=(60 if sm=='yield' else 3000) or step['water_level_m']>si.depth_m:raise ValueError('Invalid saved step values')
                fields={'project':data.get('project','Restored installation'),'depth':si.depth_m,'bore':si.bore_mm,'column':si.column_mm,'hose':si.hose_mm,'length':si.hose_length_m,'elevation':si.elevation_m,'lift_basis':'Design: water down to pump' if si.design_full_depth else 'Use each step’s pumping water level','drive_rpm':sd.pump_rpm_limit,'drive_kw':sd.drive_rating_kw,'efficiency':sd.transmission_efficiency,'extra':sd.extra_shaft_kw,'margin':sd.sizing_margin,'derating':sd.engine_derating,'engine_model':sd.engine_model,'expanded':len(ss)>4,'mode_label':'Yield (L/s)' if sm=='yield' else 'Pump-shaft RPM',f'count_{len(ss)>4}':len(ss),'restored_steps':ss,'restored_mode':sm}
                for key in list(st.session_state):
                    if key.startswith('input_'):del st.session_state[key]
                for key,val in fields.items():st.session_state[key]=val
                if data.get('pump') in pumps:st.session_state['selected_pump']=data['pump']
                st.session_state['restore_notice']='Setup restored.'
                if old_speed is not None:st.session_state['restore_notice']+=' Legacy engine-speed setting replaced by fixed continuous ratings at 2300 RPM.'
                if missing_engine:st.session_state['restore_notice']+=' No installed engine was saved: F3L912 selected; review diesel settings.'
            except Exception as e:st.session_state['restore_notice']=f'Cannot restore setup: {e}'
        st.button('Restore complete setup',on_click=restore_setup,disabled=restore is None)
        if 'restore_notice' in st.session_state:st.info(st.session_state['restore_notice'])

installation=Installation(depth,col,length,hose,elevation,bore,full)
drive=Drive(rpmcap,drivekw,efficiency,extra,margin,derate,engine)
tabs=st.tabs(['1 · Plan & select','2 · Curves & diesel','3 · Field curve check','4 · Friction & sources'])
with tabs[0]:
    with st.expander('Operator guide & terrain elevation'):
        st.markdown('**Prepare:** confirm project, borehole diameter/depth, planned yields and discharge route. **Plan:** choose columns and hose, calculate all steps, then select a pump and drive. **On site:** confirm rods, bearings, adapters, guards and actual pump RPM; measure flow and water level, then use the field curve check.')
        st.caption('Terrain lookup is optional and sends only the two entered coordinate pairs to Open Topo Data. Approximate 90 m terrain data can miss small elevation differences and route high points. Confirm the elevation on site; hose route length is entered separately.')
        c=st.columns(4)
        lat1=c[0].number_input('Borehole latitude',-60.,60.,-33.90,format='%.6f')
        lon1=c[1].number_input('Borehole longitude',-180.,180.,18.60,format='%.6f')
        lat2=c[2].number_input('Outlet latitude',-60.,60.,-33.89,format='%.6f')
        lon2=c[3].number_input('Outlet longitude',-180.,180.,18.60,format='%.6f')
        if st.button('Look up terrain elevations'):
            try:st.session_state['terrain']=terrain_elevations(lat1,lon1,lat2,lon2)
            except Exception as e:st.warning(f'Lookup unavailable: {e}. Enter the elevation difference manually.')
        if 'terrain' in st.session_state:
            t=st.session_state['terrain'];st.write(f"Borehole: {t['borehole_elevation_m']:.1f} m · Outlet: {t['outlet_elevation_m']:.1f} m · Difference: {t['difference_m']:+.1f} m")
            def apply_elevation():st.session_state['elevation']=st.session_state['terrain']['difference_m']
            st.button('Use this elevation difference',on_click=apply_elevation)
    a,b,c=st.columns([2,1,1])
    mode_label=a.radio('Enter test steps as',['Yield (L/s)','Pump-shaft RPM'],horizontal=True,key='mode_label')
    mode='yield' if mode_label.startswith('Yield') else 'rpm'
    expanded=b.checkbox('Enable up to 24 steps',key='expanded')
    n=c.number_input('Number of test steps',min_value=1,max_value=24 if expanded else 4,value=4,step=1,key=f'count_{expanded}')
    key=f'input_{mode}_{n}'
    defaults=np.linspace(3,5.5,n) if mode=='yield' else np.linspace(900,1100,n)
    frame=pd.DataFrame({'value':defaults,'water_level_m':[float(depth)]*n})
    if 'restored_steps' in st.session_state and st.session_state.get('restored_mode')==mode:
        ss=st.session_state['restored_steps'];frame=pd.DataFrame(ss).reindex(range(n)).fillna({'value':2. if mode=='yield' else 1000.,'water_level_m':depth})
    edited=st.data_editor(frame,hide_index=False,num_rows='fixed',width='stretch',key=key,column_config={'value':st.column_config.NumberColumn('Yield (L/s)' if mode=='yield' else 'Pump-shaft RPM',min_value=.01 if mode=='yield' else 1.,max_value=60. if mode=='yield' else 3000.,step=.01 if mode=='yield' else 1.,required=True),'water_level_m':st.column_config.NumberColumn('Pumping water depth (m below ground)',min_value=0.,max_value=float(depth),required=True)})
    st.caption('Each row is a test step. Water levels are retained per row; they change head only when “Use each step’s pumping water level” is selected. The design assumption remains full depth by default.')
    steps=edited.to_dict('records')
    group=st.multiselect('Pump families',['WASA','Mono','Orbit','NOV / DW'],default=['WASA','Mono','Orbit','NOV / DW'])
    names=[name for name,p in pumps.items() if ('NOV / DW' if name.startswith('DW') else p['brand']) in group]
    if not names:st.info('Select at least one pump family.');st.stop()
    results={name:evaluate(pumps[name],steps,installation,drive,mode) for name in names}
    summary=[]
    for name,res in results.items():
        vals=[r.get('yield_ls',float('nan')) for r in res['rows']]
        summary.append({'Pump':name,'Pump diameter (mm)':pumps[name]['pump_diameter_mm'],'Minimum bore (mm)':pumps[name]['minimum_bore_mm'],'Result':res['status'],'Minimum engine size':res['recommended_engine'] or ('Above available range' if res['required_engine_kw'] is not None else 'Unavailable'),'Required engine kW':res['required_engine_kw'],'Installed engine adequate':res['installed_engine_passes'],'Max yield L/s':max(vals),'Reason / qualification':'; '.join(res['reasons']+res['conditions'])})
    table=pd.DataFrame(summary)
    rank={'Suitable for planning':0,'Conditional':1,'Not suitable':2}
    table=table.assign(_rank=table['Result'].map(rank)).sort_values(['_rank','Required engine kW']).drop(columns='_rank')
    st.subheader('Pumps for every test step')
    st.dataframe(table,hide_index=True,width='stretch',column_config={'Pump diameter (mm)':st.column_config.NumberColumn(format='%.0f'),'Minimum bore (mm)':st.column_config.NumberColumn(format='%.0f'),'Required engine kW':st.column_config.NumberColumn(format='%.1f'),'Max yield L/s':st.column_config.NumberColumn(format='%.2f')})
    st.caption('Unknown pump outside diameters are left blank, not inferred from column size or minimum bore clearance. Conditional means a stated check or estimate remains. Below-source RPM uses a warned zero-anchor estimate; head and upper-RPM limits remain unchanged. The manual’s 10% overrun wording does not permit exceeded limits.')
    selection=st.selectbox('Pump to inspect',list(table['Pump']),key='selected_pump')
    pump=pumps[selection];result=results[selection]
    if result['reasons']:st.error('\n\n'.join(result['reasons']))
    if result['conditions']:st.warning('\n\n'.join(result['conditions']))
    sourcefig=performance_plot(pump,result,installation,steps)
    st.plotly_chart(sourcefig,width='stretch',config={'displaylogo':False,'toImageButtonOptions':{'format':'png','filename':f'{selection}_performance','scale':2}})
    st.caption('Digital source layout: yield above, absorbed kW below, with head on both horizontal axes. Dashed coloured lines on the upper graph show the installation system curve, one per distinct pumping water level in individual-level mode. Source units (m³/h), axis bounds, grids and RPM labels are retained. Lines use the existing digitised knots, not a new tracing. Orange dots mark planned steps; curves and points outside the original graph bounds are clipped. The system curve relates flow to head, not absorbed power, so it is shown only on the upper graph. Minimum motor labels belong to the source sheet, not to a fixed diesel/pump pairing. Low-RPM estimates may lie below the visible source axes.')
    st.download_button('Download pump performance graphs',sourcefig.to_html(include_plotlyjs=True),f'{selection}_performance.html','text/html')
    st.subheader('Four-part head calculation')
    cols=['step','yield_ls','rpm','water_level_m','lift_m','column_loss_m','elevation_m','layflat_loss_m','head_m','pump_kw','engine_required_kw','error']
    detail=pd.DataFrame(result['rows'])
    st.dataframe(detail.reindex(columns=cols),hide_index=True,width='stretch',column_config={
        'step':'Test Step [-]',
        'yield_ls':st.column_config.NumberColumn('Volumetric Flow Rate [L/s]',format='%.2f'),
        'rpm':st.column_config.NumberColumn('Pump-Shaft Rotational Speed [rpm]',format='%.2f'),
        'water_level_m':st.column_config.NumberColumn('Pumping Water Depth [m]',format='%.2f'),
        'lift_m':st.column_config.NumberColumn('Static Lift Head [m]',format='%.2f'),
        'column_loss_m':st.column_config.NumberColumn('Column Friction Head Loss [m]',format='%.2f'),
        'elevation_m':st.column_config.NumberColumn('Discharge Elevation Difference [m]',format='%.2f'),
        'layflat_loss_m':st.column_config.NumberColumn('Layflat Friction Head Loss [m]',format='%.2f'),
        'head_m':st.column_config.NumberColumn('Total Dynamic Head [m]',format='%.2f'),
        'pump_kw':st.column_config.NumberColumn('Pump Absorbed Power [kW]',format='%.2f'),
        'engine_required_kw':st.column_config.NumberColumn('Required Engine Power [kW]',format='%.2f'),
        'error':'Calculation Qualification [-]'})
    st.caption('All head terms are metres; yield is L/s; power is kW. Mechanical shaft/bearing loss is an engine-sizing allowance, separate from the hydraulic losses already included in the column chart.')
    notes=sorted(set(n for r in result['rows'] for n in r.get('notes',[])))
    if notes:
        with st.expander('Flow and friction qualifications',expanded=True):
            for note in notes:st.write('• '+note)
    st.subheader('AB Pumps quick-reference cross-check')
    subset=legacy[(legacy.pump==selection)&(legacy.column_mm==col)]
    st.dataframe(subset,hide_index=True,width='stretch',column_config={
        'pump':'Pump Model [-]',
        'column_mm':st.column_config.NumberColumn('Nominal Column Diameter [mm]',format='%.2f'),
        'depth_m':st.column_config.NumberColumn('Pump Installation Depth [m]',format='%.2f'),
        'base_limit_ls':st.column_config.NumberColumn('Reference Flow Limit [L/s]',format='%.2f'),
        'large_drive_limit_ls':st.column_config.NumberColumn('Larger-Drive Reference Flow Limit [L/s]',format='%.2f'),
        'hose_mm':st.column_config.NumberColumn('Nominal Layflat Diameter [mm]',format='%.2f'),
        'hose_length_m':st.column_config.NumberColumn('Layflat Route Length [m]',format='%.2f'),
        'elevation_m':st.column_config.NumberColumn('Discharge Elevation Difference [m]',format='%.2f'),
        'legacy_engine':'Historical Minimum Engine / Drive Guidance [-]'})
    st.caption('Legacy table assumes 100 m of 80 mm hose with 50/65 mm columns, or 100 m of 100 mm hose with 80/100 mm columns, zero elevation, good-condition pumps and usually 1100 pump RPM. Parenthesised limits use a larger drive. Engine colours are historical minimum-size guidance only, not fixed engine/pump pairings. The historical “V6” model is unverified; the separately supplied F6L413FW rating is selectable in diesel settings. DW15 has no supplied performance sheet and appears only here.')
    exact=subset[subset.depth_m==depth]
    if len(exact) and full and length==100 and elevation==0 and hose==exact.iloc[0].hose_mm:
        ref=exact.iloc[0];mx=max([r.get('yield_ls',0) for r in result['rows']],default=0)
        if pd.notna(ref.base_limit_ls):st.info(f"Matching legacy installation: {ref.base_limit_ls:g} L/s base limit; {ref.legacy_engine}. Planned peak {mx:.2f} L/s. Legacy guidance is not a substitute for calculated limits.")
    else:st.caption('Current installation does not exactly match a legacy reference cell; no legacy limit is imposed.')
with tabs[1]:
    st.subheader(f'{selection} · operating plan')
    valid=[r for r in result['rows'] if 'rpm' in r]
    metrics=st.columns(4)
    metrics[0].metric('Peak yield',f"{max([r['yield_ls'] for r in valid],default=0):.2f} L/s")
    metrics[1].metric('Peak total head',f"{max([r['head_m'] for r in valid],default=0):.1f} m")
    metrics[2].metric('Peak pump speed',f"{max([r['rpm'] for r in valid],default=0):.0f} RPM")
    metrics[3].metric('Minimum diesel size',result['recommended_engine'] or 'Not established')
    st.write(f"Installed diesel: **{drive.engine_model} · {ENGINES[drive.engine_model]:g} kW continuous**; available after allowance: **{ENGINES[drive.engine_model]*drive.engine_derating:g} kW**.")
    peakq=max([r['yield_ls'] for r in valid],default=10)
    qmax=st.slider('Chart maximum yield (L/s)',1.,60.,float(min(60,max(10,math.ceil(peakq*1.4)))),1.)
    fig=system_plot(pump,installation,steps,result,qmax)
    st.plotly_chart(fig,width='stretch',config={'displaylogo':False,'toImageButtonOptions':{'format':'png','filename':'AB_Pumps_curves','scale':2}})
    st.caption('Numbered dots are the calculated steps. Each different pumping water depth produces a separate system curve in water-level mode; the full-depth design uses one curve. Pump curves are drawn only inside the source head domain.')
    req=result['required_engine_kw']
    if req is not None:
        st.dataframe(pd.DataFrame(engine_options(req,drive)),hide_index=True,width='stretch')
        maxrow=max((r for r in valid if 'engine_required_kw' in r),key=lambda r:r['engine_required_kw'],default=None)
        if maxrow:st.write(f"Engine sizing is governed by step {maxrow['step']}: {maxrow['yield_ls']:.2f} L/s at {maxrow['head_m']:.1f} m. All requested steps are checked, including the maximum-yield step.")
    st.caption('Fixed continuous ratings at 2300 engine RPM: F3L912 36 kW, F4L912 49 kW, F5L912 61 kW, F6L912 74 kW, F6L413FW (V6) 102 kW, per supplied ratings. Minimum size is calculated for the duty, independently of the installed engine. Required rating = (pump absorbed kW + additional mechanical loss) ÷ transmission efficiency × diesel sizing factor. Available power = continuous rating × availability fraction. Low-RPM power estimates remain qualified. Confirm actual engine/drive and starting torque.')
    st.write(f"Published minimum starting torque: {pump['starting_torque_nm'] if pump['starting_torque_nm'] is not None else 'not supplied'} Nm. Running torque is included in the exported results.")
    c1,c2,c3,c4=st.columns(4)
    export_detail=detail.copy()
    if 'notes' in export_detail:export_detail['notes']=export_detail.notes.apply(lambda v:'; '.join(v) if isinstance(v,list) else '')
    c1.download_button('Download step CSV',export_detail.to_csv(index=False),'AB_Pumps_steps.csv','text/csv')
    b=BytesIO()
    with pd.ExcelWriter(b,engine='openpyxl') as writer:
        export_detail.to_excel(writer,index=False,sheet_name='Test steps');table.to_excel(writer,index=False,sheet_name='Pump comparison')
        pd.DataFrame([asdict(installation)]).to_excel(writer,index=False,sheet_name='Installation');pd.DataFrame([asdict(drive)]).to_excel(writer,index=False,sheet_name='Drive assumptions')
        pd.DataFrame([{'pump':selection,'source':pump['source'],'quality':pump['quality'],'notes':pump['notes']}]).to_excel(writer,index=False,sheet_name='Source')
        for sheet in writer.sheets.values():
            sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
            for cells in sheet.columns:sheet.column_dimensions[cells[0].column_letter].width=min(60,max(14,max(len(str(c.value or '')) for c in cells)+2))
    c2.download_button('Download Excel',b.getvalue(),'AB_Pumps_installation.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    c3.download_button('Download interactive plot',fig.to_html(include_plotlyjs=True),'AB_Pumps_curves.html','text/html')
    config={'version':2,'project':project,'installation':asdict(installation),'drive':asdict(drive),'mode':mode,'steps':steps,'pump':selection}
    c4.download_button('Save setup JSON',json.dumps(config,indent=2),'AB_Pumps_setup.json','application/json')
with tabs[2]:
    st.subheader('Is the pump performing on its curve?')
    st.write('Compare the observed pump-shaft RPM with the RPM expected for the measured yield and total head. This is a performance comparison, not a diagnosis of the cause of a shortfall.')
    fp=st.selectbox('Pump being tested',list(pumps),index=list(pumps).index(selection),key='field_pump');p=pumps[fp]
    c=st.columns(3)
    fq=c[0].number_input('Measured yield (L/s)',.01,60.,5.,.1)
    fn=c[1].number_input('Measured pump-shaft RPM',1.,3000.,1000.,10.)
    tolerance=c[2].number_input('Comparison tolerance (%)',0.,50.,10.,1.)
    fieldbasis=st.radio('Field head source',['Calculate from observed pumping water level','Enter total differential pump head'],horizontal=True)
    if fieldbasis.startswith('Calculate'):
        wl=st.number_input('Observed pumping water depth (m)',0.,float(depth),float(min(60,depth)),1.)
        fr=system_head(fq,replace(installation,design_full_depth=False),wl);fh=fr['head_m']
        st.write(f'Estimated actual total head: **{fh:.1f} m**. Uses the same pipe/hose lengths and elevation as the installation.')
        for note in fr['notes']:st.caption(note)
    else:
        fh=st.number_input('Actual total differential pump head (m)',0.,1000.,100.,1.)
        st.caption('A surface discharge-gauge reading alone is not total differential head across the downhole pump.')
    try:
        check=compare_actual(p,fq,fh,fn,tolerance)
        for note in check['notes']:st.warning(note)
        cc=st.columns(3);cc[0].metric('Expected pump speed',f"{check['expected_rpm']:.0f} RPM");cc[1].metric('Actual versus expected RPM',f"{check['rpm_difference_pct']:+.1f}%");cc[2].metric('Expected yield at actual RPM',f"{check['expected_yield_ls']:.2f} L/s")
        (st.success if abs(check['rpm_difference_pct'])<=tolerance else st.warning)(check['status'])
        st.write(f"Measured yield deviation: {check['flow_difference_pct']:+.1f}%. Positive RPM deviation means the pump needs more RPM than expected to deliver the measured flow at this head.")
        import plotly.graph_objects as go
        cc=p['flow_curves'];hg=np.linspace(max(c['head_m'][0] for c in cc),p['max_head_m'],150)
        qg=[curve_value(p,h,fn) for h in hg]
        ff=go.Figure(go.Scatter(x=qg,y=hg,name=f'Expected at {fn:g} RPM'))
        ff.add_trace(go.Scatter(x=[fq],y=[fh],mode='markers',marker=dict(size=13,color='#d88920'),name='Measured'))
        ff.update_layout(template='plotly_white',xaxis_title='Yield (L/s)',yaxis_title='Total head (m)',height=380)
        st.plotly_chart(ff,width='stretch')
        st.download_button('Download field comparison',pd.DataFrame([dict(check,pump=fp,head_m=fh)]).to_csv(index=False),'AB_Pumps_field_check.csv','text/csv')
    except ValueError as e:st.info(f'Comparison unavailable: {e}. Head and upper-RPM limits are not extrapolated.')
    st.caption('10% is an editable comparison tolerance, not a manufacturer acceptance test or permission to exceed rated RPM. Check measured flow, water level, RPM and pipe losses before attributing deviation to pump wear.')
with tabs[3]:
    st.subheader('Friction charts')
    st.plotly_chart(friction_plot('column'),width='stretch');st.plotly_chart(friction_plot('hose'),width='stretch')
    st.caption('Column: approximate CEMO shaft-and-bearing chart readings for 40–100 mm. Beyond the chart: Q² extension. 150 mm uses an annular scaling estimate from 100 mm. Layflat: Rain-Flo chart in US GPM and psi/100 ft converted to metric; nominal mapping 2/2½/3/4/6 inch → 50/65/80/100/150 mm. 200 mm is a diameter-scaling estimate. Outside tabulated flows uses Q^1.85. All estimates are flagged in results. Velocity assumes nominal waterway diameter and standard rod diameter, so is approximate.')
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
    st.write(sp['notes']);st.json({k:v for k,v in sp.items() if k not in ['flow_curves','power_curves']})
    st.image(str(ROOT/sp['source']),width=650)
    st.download_button('Download pump dataset',(ROOT/'data/pumps.json').read_bytes(),'pumps.json','application/json')
    st.download_button('Download curve points CSV',(ROOT/'data/curve_points.csv').read_bytes(),'curve_points.csv','text/csv')
    with st.expander('Original friction and AB quick-reference charts'):
        st.image(str(ROOT/'sources/cemo_friction.jpg'));st.image(str(ROOT/'sources/ab_quick_reference.jpg'))
    st.markdown('[Franklin Mono BP](https://franklin-electric.co.za/products/mono-bp-range/) · [Franklin Orbit GW](https://franklin-electric.co.za/products/orbit-gw-range/) · [Rain-Flo layflat chart](https://www.rainfloirrigation.com/irrigation/charts-layouts/friction-loss-chart) · [Deutz continuous-power brochure](https://www.deutz.com.au/wp-content/uploads/2016/09/DEUTZ-DRIVE-The-New-Power-Pack-Series.pdf) · [Terrain API](https://www.opentopodata.org/api/)')
    st.caption('No database or login is required. Calculation inputs live in this session; download a setup file to keep them. The catalogue is bundled with the app. Public deployment does not automatically publish saved user scenarios.')
