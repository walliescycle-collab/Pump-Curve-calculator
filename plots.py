import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from hydraulics import system_head,curve_value,CurveRangeError,column_loss,layflat_loss
COLORS=['#057f8d','#d88920','#6750a4','#3074bc','#ba4b5b','#65852d']

def performance_plot(pump,result=None,installation=None,steps=None):
    """Recreate source axes without auto-scaling or inventing extra source knots."""
    chart=pump['source_chart']
    fig=make_subplots(rows=2,cols=1,row_heights=[.69,.31],vertical_spacing=.12)
    for row,kind,key,value in [(1,'flow','flow_curves','flow_m3h'),(2,'power','power_curves','power_kw')]:
        yspec=chart[kind];xspec=chart['head']
        for c in pump[key]:
            if 'plotted_rpms' in chart and c['rpm'] not in chart['plotted_rpms']:continue
            label=f"{c['rpm']:g} {chart['rpm_unit']}"
            fig.add_trace(go.Scatter(x=c['head_m'],y=c[value],mode='lines',
                name=f'{kind.title()} · {label}',line=dict(color='#222222',width=2),
                showlegend=False,hovertemplate=f'{label}<br>Head: %{{x:g}} m<br>%{{y:.2f}} {"m³/h" if kind=="flow" else "kW"}<extra></extra>'),row=row,col=1)
            x=min(c['head_m'][-1],xspec['range'][1])-.025*(xspec['range'][1]-xspec['range'][0])
            if x>=c['head_m'][0]:
                y=float(np.interp(x,c['head_m'],c[value]))
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
            y=r['yield_ls']*3.6 if kind=='flow' else r['pump_kw']
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
            fig.add_trace(go.Scatter(x=heads,y=qgrid*3.6,mode='lines',
                name=f'System · lift {lift:g} m',showlegend=True,
                line=dict(color=COLORS[(len(seen)-1)%len(COLORS)],width=3,dash='dash'),
                customdata=qgrid,
                hovertemplate=f'System · lift {lift:g} m<br>Head: %{{x:.2f}} m<br>Flow: %{{y:.2f}} m³/h (%{{customdata:.2f}} L/s)<extra></extra>'),row=1,col=1)
    minimum=chart['minimum_motor_kw']
    if minimum is not None:
        fig.add_annotation(x=.025,y=.98,xref='x2 domain',yref='y2 domain',
            text=f'MIN MOTOR SIZE<br>{minimum:g} kW',showarrow=False,xanchor='left',
            yanchor='top',bgcolor='white',bordercolor='#aaaaaa',borderpad=5)
    fig.update_layout(template='plotly_white',height=980,title=f"{pump['name']} · source performance curves",
        margin=dict(t=55,b=100,l=90,r=35),font=dict(color='#222222'),plot_bgcolor='white',
        legend=dict(orientation='h',y=-.08))
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
