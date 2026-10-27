from dataclasses import replace
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from hydraulics import (system_head,curve_value,CurveRangeError,column_loss,layflat_loss,
    engine_pump_limit_kw,engine_flow_boundary,ENGINES)
COLORS=['#057f8d','#d88920','#6750a4','#3074bc','#ba4b5b','#65852d']

def performance_plot(pump,result=None,installation=None,steps=None,flow_unit='m³/h',field_check=None,drive=None,engine_fraction_range=None):
    """Recreate source axes without auto-scaling or inventing extra source knots."""
    chart=pump['source_chart']
    if engine_fraction_range is not None:
        lower,upper=engine_fraction_range
        if drive is None or not 0<lower<upper<=1:
            raise ValueError('Engine fraction range requires a drive and 0 < lower < upper <= 1')
    if flow_unit not in ['m³/h','L/s']:raise ValueError('Unsupported flow unit')
    factor=1 if flow_unit=='m³/h' else 1/3.6
    fig=make_subplots(rows=2,cols=1,row_heights=[.69,.31],vertical_spacing=.12)
    for row,kind,key,value in [(1,'flow','flow_curves','flow_m3h'),(2,'power','power_curves','power_kw')]:
        yspec=dict(chart[kind]);xspec=dict(chart['head'],tick=25,minor=None,grid=True)
        if kind=='flow':
            yspec.update(range=[v*factor for v in yspec['range']],tick=yspec['tick']*factor,
                minor=yspec['minor']*factor if yspec['minor'] else None,label=f'YIELD ({flow_unit})')
        scale=factor if kind=='flow' else 1
        for c in pump[key]:
            if 'plotted_rpms' in chart and c['rpm'] not in chart['plotted_rpms']:continue
            label=f"{c['rpm']:g} {chart['rpm_unit']}"
            fig.add_trace(go.Scatter(x=c['head_m'],y=[v*scale for v in c[value]],mode='lines',
                name=f'{kind.title()} · {label}',line=dict(color='#222222',width=2),
                showlegend=False,hovertemplate=f'{label}<br>Head: %{{x:g}} m<br>%{{y:.2f}} {flow_unit if kind=="flow" else "kW"}<extra></extra>'),row=row,col=1)
            x=min(c['head_m'][-1],xspec['range'][1])-.025*(xspec['range'][1]-xspec['range'][0])
            if x>=c['head_m'][0]:
                y=float(np.interp(x,c['head_m'],c[value]))*scale
                if yspec['range'][0]<=y<=yspec['range'][1]:
                    fig.add_annotation(x=x,y=y,text=label,showarrow=False,xanchor='right',
                        yanchor='bottom',font=dict(size=11,color='#222222'),row=row,col=1)
        for axis,spec in [('x',xspec),('y',yspec)]:
            minor=spec['minor']
            settings=dict(title_text=spec['label'],range=spec['range'],autorange=False,
                tick0=spec.get('tick0',0),dtick=spec['tick'],ticks='outside',
                showline=True,mirror=True,linecolor='#222222',linewidth=1.5,
                showgrid=spec['grid'],gridcolor='#6e6e6e',gridwidth=1,
                zeroline=False,fixedrange=False)
            if minor and minor<spec['tick']:
                settings['minor']=dict(dtick=minor,tick0=0,showgrid=spec['grid'],gridcolor='#c3c3c3',gridwidth=.5)
            (fig.update_xaxes if axis=='x' else fig.update_yaxes)(row=row,col=1,**settings)
        if pump['max_head_m']<xspec['range'][1]:
            fig.add_vline(x=pump['max_head_m'],line_dash='dash',line_color='#ba4b5b',
                annotation_text=f"Operating limit {pump['max_head_m']:g} m",row=row,col=1)
        for r in (result or {}).get('rows',[]):
            if 'rpm' not in r or (kind=='power' and 'pump_kw' not in r):continue
            y=r['yield_ls']*3.6*factor if kind=='flow' else r['pump_kw']
            fig.add_trace(go.Scatter(x=[r['head_m']],y=[y],mode='markers',
                name=f"Step {r['step']}",showlegend=False,
                marker=dict(size=9,color='#d88920',line=dict(width=1,color='white')),
                hovertemplate=f"Step {r['step']} · {r['rpm']:.1f} RPM<br>Head: %{{x:.1f}} m<br>%{{y:.2f}}<extra></extra>"),row=row,col=1)
    if installation is not None:
        if steps is None:raise ValueError('Test steps are required for the system-curve overlay')
        qmax=min(60.,chart['flow']['range'][1]/3.6)
        qgrid=np.linspace(0,qmax,300)
        seen=set()
        for step in steps:
            wl=step.get('water_level_m')
            lift=installation.depth_m if installation.design_full_depth else wl
            if lift in seen:continue
            seen.add(lift)
            heads=[system_head(float(q),installation,wl)['head_m'] for q in qgrid]
            fig.add_trace(go.Scatter(x=heads,y=qgrid*3.6*factor,mode='lines',
                name=f'System · lift {lift:g} m',showlegend=True,
                line=dict(color=COLORS[(len(seen)-1)%len(COLORS)],width=3,dash='dash'),
                customdata=qgrid,
                hovertemplate=f'System · lift {lift:g} m<br>Head: %{{x:.2f}} m<br>Flow: %{{y:.2f}} {flow_unit}<extra></extra>'),row=1,col=1)
    if field_check is not None:
        h=field_check['head_m'];actual=field_check['actual_rpm'];expected=field_check['expected_rpm']
        for q,rpm,label,color,symbol in [
            (field_check['actual_yield_ls'],actual,'Measured','#d88920','circle'),
            (field_check['expected_yield_ls'],actual,'Expected at actual RPM','#3074bc','diamond')]:
            fig.add_trace(go.Scatter(x=[h],y=[q*3.6*factor],mode='markers',name=f'{label} · {rpm:.0f} RPM',
                marker=dict(size=13,color=color,symbol=symbol,line=dict(width=1,color='white')),
                hovertemplate=f'{label}<br>Head: %{{x:.1f}} m<br>Flow: %{{y:.2f}} {flow_unit}<extra></extra>'),row=1,col=1)
        fig.add_annotation(x=h,y=field_check['actual_yield_ls']*3.6*factor,
            text=f"Expected {expected:.0f} / actual {actual:.0f} RPM<br>{field_check['rpm_difference_pct']:+.1f}%",
            showarrow=True,arrowhead=2,ax=0,ay=-55,row=1,col=1)
        # A valid measured point must not disappear outside the source's display bounds.
        low,high=[v*factor for v in chart['flow']['range']]
        measured=[field_check['actual_yield_ls']*3.6*factor,field_check['expected_yield_ls']*3.6*factor]
        fig.update_yaxes(range=[min(low,min(measured)*.9),max(high,max(measured)*1.1)],row=1,col=1)
        power=field_check.get('pump_kw')
        if power is not None:
            fig.add_trace(go.Scatter(x=[h],y=[power],mode='markers',name='Estimated power at actual RPM',
                marker=dict(size=13,color='#d88920',line=dict(width=1,color='white')),
                hovertemplate='Estimated absorbed power at actual RPM<br>Head: %{x:.1f} m<br>%{y:.2f} kW<extra></extra>'),row=2,col=1)
    if drive is not None:
        limits=[]
        fractions=[('',drive.engine_derating)] if engine_fraction_range is None else list(zip(
            ['Lower wear limit','Upper wear limit'],engine_fraction_range))
        for index,(qualifier,fraction) in enumerate(fractions):
            limit_drive=replace(drive,engine_derating=fraction)
            limit=engine_pump_limit_kw(limit_drive)
            limits.append(limit)
            label=f'{drive.engine_model} · {limit:.2f} kW usable ({fraction:.0%} of {ENGINES[drive.engine_model]:g} kW engine)'
            if qualifier:label=f'{qualifier} · {label}'
            red='#ef4444' if index==0 else '#f97373'
            fig.add_hline(y=limit,line_dash='dash',line_color=red,line_width=2,
                annotation_text=label,annotation_position='bottom right' if qualifier and index==0 else 'top right',row=2,col=1)
            boundary=engine_flow_boundary(pump,limit_drive)
            boundary_flows=[q*3.6*factor for q in boundary['yield_ls'] if q is not None]
            fig.add_trace(go.Scatter(x=boundary['head_m'],
                y=[q*3.6*factor if q is not None else None for q in boundary['yield_ls']],
                customdata=boundary['rpm'],mode='lines',connectgaps=False,
                name=f'Engine limit · {label}',line=dict(color=red,width=2,dash='dash'),
                hovertemplate=f'{label}<br>Head: %{{x:.1f}} m<br>Flow: %{{y:.2f}} {flow_unit}<br>%{{customdata:.0f}} RPM<extra></extra>'),row=1,col=1)
            if boundary_flows:
                low,high=fig.layout.yaxis.range
                fig.update_yaxes(range=[min(low,min(boundary_flows)*.9),
                    max(high,max(boundary_flows)*1.1)],row=1,col=1)
            else:
                message='Engine limit above published power curves' if limit>0 else 'No positive pump power available'
                fig.add_annotation(x=.02,y=.98-index*.14,xref='x domain',yref='y domain',
                    text=f'{label}<br>{message}; no equal-power boundary',showarrow=False,xanchor='left')
        power_values=[v for trace in fig.data if trace.yaxis=='y2' for v in trace.y if v is not None]
        low,high=chart['power']['range']
        fig.update_yaxes(range=[min(low,0,min(limits)*1.1),
            max(high,max(power_values,default=0)*1.1,max(limits)+max(1,abs(max(limits))*.12))],row=2,col=1)
    minimum=chart['minimum_motor_kw']
    if minimum is not None:
        fig.add_annotation(x=.025,y=.98,xref='x2 domain',yref='y2 domain',
            text=f'MIN MOTOR SIZE<br>{minimum:g} kW',showarrow=False,xanchor='left',
            yanchor='top',bgcolor='white',bordercolor='#aaaaaa',borderpad=5)
    fig.update_layout(template='plotly_white',height=980,title=f"{pump['name']} · source performance curves",
        margin=dict(t=55,b=100,l=90,r=35),font=dict(color='#222222'),plot_bgcolor='white',
        legend=dict(orientation='h',y=-.08))
    return fig

def head_contribution_plot(pump,result):
    """Signed head terms, expressed as a fraction of the pump's rated head."""
    rows=[r for r in result['rows'] if 'head_m' in r]
    if not rows:raise ValueError('No calculated head values are available')
    rated=pump['max_head_m']
    fig=go.Figure()
    labels=[f"Step {r['step']}" for r in rows]
    terms=[('lift_m','Lift'),('column_loss_m','Column friction'),
        ('elevation_m','Discharge elevation'),('layflat_loss_m','Layflat friction')]
    for i,(key,label) in enumerate(terms):
        values=[r[key] for r in rows];pct=[100*v/rated for v in values]
        fig.add_trace(go.Bar(y=labels,x=values,orientation='h',name=label,
            marker_color=COLORS[i],customdata=pct,
            text=[f'{v:.1f}%' if abs(v)>=2 else '' for v in pct],textposition='inside',
            insidetextfont=dict(color='white'),
            hovertemplate=f'{label}<br>%{{x:.2f}} m · %{{customdata:.1f}}% of rated head<extra></extra>'))
    for label,r in zip(labels,rows):
        remaining=rated-r['head_m']
        text=f"Total {r['head_m']:.1f} m ({100*r['head_m']/rated:.1f}%)"
        text+=f" · {'Spare' if remaining>=0 else 'Overload'} {abs(remaining):.1f} m"
        breakdown=' · '.join(f'{label} {100*r[key]/rated:.1f}%' for key,label in terms)
        fig.add_annotation(x=0,y=label,xref='paper',text=f'{text}<br>{breakdown}',
            showarrow=False,xanchor='left',yshift=32,font=dict(size=11),align='left')
    positive=max(sum(max(0,r[k]) for k,_ in terms) for r in rows)
    negative=min(sum(min(0,r[k]) for k,_ in terms) for r in rows)
    fig.add_vline(x=rated,line_dash='dash',line_color='#ba4b5b',
        annotation_text=f'Rated {rated:g} m',annotation_position='top right')
    fig.update_layout(template='plotly_white',barmode='relative',height=max(270,130+90*len(rows)),
        title='Head contribution · % of rated pump head',xaxis_title='Head (m)',
        legend=dict(orientation='h',y=-.25),margin=dict(t=65,b=90),bargap=.5)
    fig.update_xaxes(dtick=25,tick0=0,range=[25*np.floor(negative/25),25*np.ceil(max(rated,positive)/25)+25])
    fig.update_yaxes(autorange='reversed')
    return fig

def rpm_comparison_plot(check):
    values=[check['expected_rpm'],check['actual_rpm']]
    fig=go.Figure(go.Bar(x=['Expected','Actual'],y=values,marker_color=[COLORS[0],COLORS[1]],
        text=[f'{v:.0f} RPM' for v in values],textposition='outside',cliponaxis=False))
    fig.update_layout(template='plotly_white',title=f"RPM deviation: {check['rpm_difference_pct']:+.1f}%",
        yaxis_title='Pump-shaft RPM',height=350,margin=dict(t=65,b=35))
    fig.update_yaxes(range=[0,max(values)*1.2])
    return fig

def apply_theme(fig,theme='light'):
    dark=theme=='dark'
    foreground='#f0f2f6' if dark else '#222222'
    background='#0e1117' if dark else '#ffffff'
    grid='#4a5260' if dark else '#b7bec7'
    fig.update_layout(template='plotly_dark' if dark else 'plotly_white',
        font=dict(color=foreground),paper_bgcolor=background,plot_bgcolor=background)
    fig.update_xaxes(linecolor=foreground,gridcolor=grid,minor_gridcolor=grid)
    fig.update_yaxes(linecolor=foreground,gridcolor=grid,minor_gridcolor=grid)
    for trace in fig.data:
        if hasattr(trace,'line') and trace.line.color=='#222222':trace.line.color=foreground
    for annotation in fig.layout.annotations:
        annotation.font.color=foreground
        if annotation.bgcolor=='white':annotation.bgcolor=background
    return fig

def system_plot(pump,installation,steps,result,qmax=30):
    fig=go.Figure();qgrid=np.linspace(0,qmax,240)
    seen=set()
    for i,step in enumerate(steps):
        wl=step.get('water_level_m');lift=installation.depth_m if installation.design_full_depth else wl
        if lift in seen:continue
        seen.add(lift)
        try:heads=[system_head(q,installation,wl)['head_m'] for q in qgrid]
        except ValueError:continue
        fig.add_trace(go.Scatter(x=qgrid,y=heads,name=f'System · lift {lift:g} m',line=dict(width=3,color=COLORS[i%len(COLORS)])))
    for j,c in enumerate(pump['flow_curves']):
        hs=np.linspace(c['head_m'][0],min(pump['max_head_m'],c['head_m'][-1]),160)
        qs=np.array([curve_value(pump,h,c['rpm']) for h in hs]);valid=(qs>=0)&(qs<=qmax)
        fig.add_trace(go.Scatter(x=qs[valid],y=hs[valid],name=f"{pump['name']} · {c['rpm']:g} RPM",line=dict(width=1.5,dash='dash')))
    for row in result['rows']:
        if 'rpm' not in row:continue
        q,h,n=row['yield_ls'],row['head_m'],row['rpm']
        fig.add_trace(go.Scatter(x=[q],y=[h],mode='markers+text',text=[str(row['step'])],textposition='top center',marker=dict(size=12,color='#d88920',line=dict(width=2,color='white')),name=f"Step {row['step']} · {n:.0f} RPM",hovertemplate=f'{q:.2f} L/s<br>{h:.1f} m<br>{n:.0f} RPM<extra></extra>'))
    fig.update_layout(template='plotly_white',height=560,xaxis_title='Yield (L/s)',yaxis_title='Total head (m)',legend=dict(orientation='h',y=-.2),margin=dict(t=25,b=100),title=f"{pump['name']} · pump and installation curves")
    fig.update_xaxes(range=[0,qmax]);fig.update_yaxes(range=[0,max(pump['max_head_m']*1.1,max([r.get('head_m',0) for r in result['rows']],default=0)*1.1)])
    return fig

def friction_plot(kind):
    fig=go.Figure();qs=np.linspace(.5 if kind=='column' else 1,60,240)
    sizes=[40,50,65,80,100,150] if kind=='column' else [50,65,80,100,150,200]
    fn=column_loss if kind=='column' else layflat_loss
    for size in sizes:
        vals=[fn(q,100,size)[0] for q in qs]
        fig.add_trace(go.Scatter(x=qs,y=vals,name=f'{size} mm'))
    fig.update_layout(template='plotly_white',height=430,xaxis_title='Yield (L/s)',yaxis_title='Head loss (m per 100 m)',yaxis_type='log',title='Shaft-driven column losses' if kind=='column' else 'PVC layflat losses')
    return fig
