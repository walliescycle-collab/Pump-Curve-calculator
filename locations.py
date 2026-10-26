"""Coordinate parsing and opt-in browser location, without a Maps API key."""
import re
from urllib.parse import urlparse, parse_qs, unquote
import streamlit as st
from streamlit.components.v2 import component
from hydraulics import finite


def validate_coordinates(latitude,longitude):
    finite(latitude,'Latitude');finite(longitude,'Longitude')
    if not -60<=latitude<=60 or not -180<=longitude<=180:
        raise ValueError('Coordinates outside terrain coverage (60 S to 60 N)')
    return float(latitude),float(longitude)


def parse_map_coordinates(text):
    text=unquote(text.strip())
    pair=r'(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)'
    match=re.fullmatch(pair,text)
    if not match:
        url=urlparse(text)
        if url.scheme not in ('http','https') or not url.hostname:
            raise ValueError('Enter latitude, longitude or a full Google Maps pin URL')
        host=url.hostname.lower()
        if host in ('maps.app.goo.gl','goo.gl'):
            raise ValueError('Open the shortened link in Google Maps and copy the coordinates of the pin')
        if not (host=='google.com' or host.endswith('.google.com') or
                host=='maps.google.co.za' or host=='www.google.co.za'):
            raise ValueError('Use a Google Maps pin URL or paste its latitude, longitude')
        match=re.search(r'!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)',text)
        if not match:
            query=parse_qs(url.query)
            for key in ('q','query','destination'):
                match=re.fullmatch(pair,query.get(key,[''])[0])
                if match:break
        if not match:
            raise ValueError('This link has no explicit pin coordinates. Right-click or hold the pin in Google Maps and copy latitude, longitude (not the map centre)')
    return validate_coordinates(float(match[1]),float(match[2]))


@st.cache_resource
def location_component():
    return component('phone_location',html='''
        <button type="button">Use my current location</button>
        <span role="status" aria-live="polite"></span>''',
        css='''button {background:var(--st-secondary-background-color);color:var(--st-text-color);
            border:1px solid var(--st-text-color);border-radius:8px;padding:8px;cursor:pointer}
            span {display:block;color:var(--st-text-color);margin-top:6px}''',
        js='''
        export default function(component) {
            const {parentElement, setTriggerValue} = component;
            const button = parentElement.querySelector("button");
            const status = parentElement.querySelector("span");
            button.onclick = () => {
                if (!window.isSecureContext || !navigator.geolocation) {
                    status.textContent = "Location requires HTTPS (or localhost) and a supported browser.";
                    setTriggerValue("error", status.textContent);
                    return;
                }
                button.disabled = true;
                status.textContent = "Waiting for location permission...";
                navigator.geolocation.getCurrentPosition(
                    position => {
                        button.disabled = false;
                        status.textContent = "Location received.";
                        setTriggerValue("location", {
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude,
                            accuracy: position.coords.accuracy,
                            target: component.data.target
                        });
                    },
                    error => {
                        button.disabled = false;
                        const messages = {
                            1: "Location permission denied. Allow location in browser settings or enter a pin.",
                            2: "Location unavailable. Enter a Google Maps pin or coordinates.",
                            3: "Location timed out. Try again or enter coordinates."
                        };
                        status.textContent = messages[error.code] || error.message;
                        setTriggerValue("error", status.textContent);
                    },
                    {enableHighAccuracy: true, timeout: 15000, maximumAge: 0}
                );
            };
            return () => {button.onclick = null;};
        }''')


def terrain_controls(terrain_elevations):
    with st.expander('Terrain & location'):
        mode=st.radio('Terrain entry',['Manual elevation','Google Maps / phone location'],key='terrain_mode')
        if mode=='Manual elevation':
            st.caption('Enter discharge elevation in the sidebar.')
            return
        st.caption('Pick borehole and outlet pins in Google Maps, then paste their coordinates or full pin links. Phone location uses your browser permission. Elevation lookup sends only the two coordinate pairs to Open Topo Data.')
        target=st.selectbox('Point to set',['Borehole','Outlet'])
        def receive_location():
            data=st.session_state['phone_location'].get('location')
            if not data:return
            try:
                lat,lon=validate_coordinates(data['latitude'],data['longitude'])
                prefix='borehole' if data['target']=='Borehole' else 'outlet'
                st.session_state[f'{prefix}_lat']=lat;st.session_state[f'{prefix}_lon']=lon
                st.session_state['location_notice']=f"{data['target']} location set (accuracy ±{data['accuracy']:.0f} m)."
            except (ValueError,KeyError,TypeError) as exc:
                st.session_state['location_notice']=f'Location could not be used: {exc}'
        def receive_error():
            st.session_state['location_notice']=st.session_state['phone_location'].get('error')
        location_component()(key='phone_location',data={'target':target},
            on_location_change=receive_location,on_error_change=receive_error)
        if st.session_state.get('location_notice'):st.info(st.session_state['location_notice'])
        for prefix,label,lat,lon in [('borehole','Borehole',-33.90,18.60),('outlet','Outlet',-33.89,18.60)]:
            text=st.text_input(f'{label} Google Maps pin / coordinates',key=f'{prefix}_pin')
            if st.button(f'Use {label.lower()} pin'):
                try:
                    latitude,longitude=parse_map_coordinates(text)
                    st.session_state[f'{prefix}_lat']=latitude;st.session_state[f'{prefix}_lon']=longitude
                except ValueError as exc:st.error(str(exc))
            c=st.columns(2)
            c[0].number_input(f'{label} latitude',-60.,60.,lat,format='%.6f',key=f'{prefix}_lat')
            c[1].number_input(f'{label} longitude',-180.,180.,lon,format='%.6f',key=f'{prefix}_lon')
            st.link_button(f'Open {label.lower()} in Google Maps',
                f"https://www.google.com/maps/search/?api=1&query={st.session_state[f'{prefix}_lat']},{st.session_state[f'{prefix}_lon']}")
        coordinates=tuple(st.session_state[k] for k in ('borehole_lat','borehole_lon','outlet_lat','outlet_lon'))
        if st.button('Look up terrain elevations'):
            try:
                st.session_state['terrain']=terrain_elevations(*coordinates)
                st.session_state['terrain_coordinates']=coordinates
            except (ValueError,TypeError,OSError) as exc:
                st.session_state.pop('terrain',None)
                st.error(f'Lookup unavailable: {exc}. Enter elevation manually.')
        if 'terrain' in st.session_state:
            if st.session_state.get('terrain_coordinates')!=coordinates:
                st.warning('Coordinates changed. Look up elevations again before applying.')
            else:
                t=st.session_state['terrain']
                st.write(f"Borehole {t['borehole_elevation_m']:.1f} m · Outlet {t['outlet_elevation_m']:.1f} m · Difference {t['difference_m']:+.1f} m")
                def apply_elevation():
                    value=st.session_state['terrain']['difference_m']
                    if not -1000<=value<=1000:
                        st.session_state['location_notice']='Elevation difference exceeds the installation input range.'
                        return
                    st.session_state['elevation']=value
                st.button('Use this elevation difference',on_click=apply_elevation)
        st.caption('90 m terrain data is approximate. Verify elevations and route high points on site; enter hose route length separately. Phone location requires HTTPS or localhost.')
