"""Coordinate entry, opt-in GPS and satellite inset without an API key."""
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
    if text.startswith('(') and text.endswith(')'):text=text[1:-1].strip()
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
        <button type="button">Use phone GPS</button>
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
                const target = component.data.target;
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
                            target
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


def store_point(prefix,latitude,longitude,accuracy=None):
    latitude,longitude=validate_coordinates(latitude,longitude)
    if prefix not in ('borehole','outlet'):raise ValueError('Unknown location point')
    if accuracy is not None:
        finite(accuracy,'GPS accuracy')
        if accuracy<0:raise ValueError('GPS accuracy cannot be negative')
    points=dict(st.session_state.get('terrain_points',{}))
    points[prefix]={'latitude':latitude,'longitude':longitude,'accuracy_m':accuracy}
    st.session_state['terrain_points']=points
    st.session_state[f'{prefix}_lat']=latitude
    st.session_state[f'{prefix}_lon']=longitude
    if accuracy is None:st.session_state.pop('location_notice',None)


def edited_coordinates(prefix):
    store_point(prefix,st.session_state[f'{prefix}_lat'],st.session_state[f'{prefix}_lon'])


def map_points():
    points=st.session_state['terrain_points']
    return [dict(points[prefix],label=label,color=color)
        for prefix,label,color in [('borehole','Borehole','#00bcd4'),('outlet','Outlet','#ff9800')]]


@st.cache_resource
def satellite_component():
    return component('terrain_satellite',isolate_styles=False,
        html='''<div class="ab-terrain-map" role="region" aria-label="Borehole and outlet satellite map"></div>
            <div class="ab-map-status" role="status" aria-live="polite"></div>''',
        css='''.ab-terrain-map {height:440px;width:100%;border-radius:8px}
            .ab-map-status {color:var(--st-text-color);padding-top:6px}
            .ab-terrain-map .leaflet-tooltip {color:#111;background:white}
            .ab-terrain-map .leaflet-control-attribution {color:#111;background:rgba(255,255,255,.9)}''',
        js='''
        export default function(component) {
            const root = component.parentElement;
            const container = root.querySelector(".ab-terrain-map");
            const status = root.querySelector(".ab-map-status");
            if (container.abMapCleanup) container.abMapCleanup();
            let map = null;
            let disposed = false;
            let observer = null;
            const cleanup = () => {
                disposed = true;
                if (observer) observer.disconnect();
                if (map) {
                    if (component.data.picker) {
                        const centre = map.getCenter();
                        container.abPickerView = {latitude:centre.lat,longitude:centre.lng,zoom:map.getZoom()};
                    }
                    map.remove(); map = null;
                }
                if (container.abMapCleanup === cleanup) delete container.abMapCleanup;
            };
            container.abMapCleanup = cleanup;
            if (!window.abLeafletLoad) {
                window.abLeafletLoad = new Promise((resolve, reject) => {
                    const css = document.createElement("link");
                    css.rel = "stylesheet";
                    css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
                    document.head.appendChild(css);
                    if (window.L) {resolve(window.L); return;}
                    const script = document.createElement("script");
                    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
                    script.onload = () => resolve(window.L);
                    script.onerror = () => reject(new Error("Map library unavailable. Check internet access and reload."));
                    document.head.appendChild(script);
                }).catch(error => {window.abLeafletLoad = null; throw error;});
            }
            status.textContent = "Loading satellite map...";
            window.abLeafletLoad.then(L => {
                if (disposed) return;
                const first = component.data.points[0];
                map = L.map(container, {scrollWheelZoom:false, maxZoom:19})
                    .setView([first.latitude, first.longitude], 13);
                const imagery = L.tileLayer(
                    "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                    {maxZoom:19, attribution:"Imagery &copy; Esri, Vantor, Earthstar Geographics, and the GIS User Community"}
                ).addTo(map);
                const labels = L.tileLayer(
                    "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
                    {maxZoom:19, maxNativeZoom:18, attribution:"Labels &copy; Esri, HERE, Garmin, OpenStreetMap contributors"}
                ).addTo(map);
                let tileFailed = false;
                for (const layer of [imagery, labels]) {
                    layer.on("tileerror", () => {
                        tileFailed = true;
                        status.textContent = "Some satellite/label tiles could not load. Check internet access or zoom out.";
                    });
                }
                imagery.on("load", () => {
                    if (!tileFailed) status.textContent = "Esri satellite imagery with place labels. Circles show reported GPS accuracy, not survey boundaries.";
                });
                const bounds = L.latLngBounds([]);
                for (const point of component.data.points) {
                    const latlng = [point.latitude, point.longitude];
                    const tooltip = document.createElement("span");
                    tooltip.textContent = point.label;
                    const popup = document.createElement("span");
                    popup.textContent = point.label + ": " + point.latitude.toFixed(6) + ", " +
                        point.longitude.toFixed(6) + (point.accuracy_m === null ? " (pin/manual coordinates)" :
                        " (GPS accuracy ±" + point.accuracy_m.toFixed(0) + " m)");
                    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                    svg.setAttribute("viewBox", "0 0 32 44");
                    svg.setAttribute("width", "32");
                    svg.setAttribute("height", "44");
                    svg.setAttribute("aria-hidden", "true");
                    const body = document.createElementNS(svg.namespaceURI, "path");
                    body.setAttribute("d", "M16 43 C13 38 1 24 1 16 A15 15 0 0 1 31 16 C31 24 19 38 16 43 Z");
                    body.setAttribute("fill", point.color);
                    body.setAttribute("stroke", "#ffffff");
                    body.setAttribute("stroke-width", "2");
                    const centre = document.createElementNS(svg.namespaceURI, "circle");
                    centre.setAttribute("cx", "16");
                    centre.setAttribute("cy", "16");
                    centre.setAttribute("r", "5");
                    centre.setAttribute("fill", "#ffffff");
                    svg.append(body, centre);
                    const icon = L.divIcon({html:svg,className:"ab-location-pin",
                        iconSize:[32,44],iconAnchor:[16,43],
                        popupAnchor:[0,-40],tooltipAnchor:[0,-40]});
                    L.marker(latlng, {icon,alt:point.label + " exact position",title:point.label})
                        .bindTooltip(tooltip,{permanent:true,direction:"top"})
                        .bindPopup(popup).addTo(map);
                    bounds.extend(latlng);
                    if (point.accuracy_m !== null) {
                        const circle = L.circle(latlng, {radius:point.accuracy_m,
                            color:point.color,fillOpacity:.16,weight:2}).addTo(map);
                        bounds.extend(circle.getBounds());
                    }
                }
                map.fitBounds(bounds, {paddingTopLeft:[45,75],paddingBottomRight:[45,35],maxZoom:17});
                const endpoints = component.data.points.map(point => [point.latitude, point.longitude]);
                const distance = map.distance(endpoints[0], endpoints[1]);
                const distanceLabel = document.createElement("span");
                distanceLabel.textContent = "Straight-line distance: " +
                    distance.toLocaleString("en", {minimumFractionDigits:1,maximumFractionDigits:1}) + " m";
                L.polyline(endpoints, {color:"#ffffff",weight:4,opacity:.7,
                    interactive:false,className:"ab-point-path-backing"}).addTo(map);
                L.polyline(endpoints, {color:"#123b70",weight:2,dashArray:"8 6",
                    className:"ab-point-path"}).addTo(map)
                    .bindTooltip(distanceLabel, {permanent:true,direction:"center",
                        className:"ab-distance-label"});
                if (component.data.picker) {
                    const view = container.abPickerView || component.data.view;
                    if (view) map.setView([view.latitude,view.longitude],view.zoom);
                    map.on("moveend", () => {
                        const centre = map.getCenter();
                        container.abPickerView = {latitude:centre.lat,longitude:centre.lng,zoom:map.getZoom()};
                    });
                    let pickTarget = component.data.target;
                    if (pickTarget) map.on("click", event => {
                        if (!pickTarget) return;
                        const centre = map.getCenter();
                        component.setTriggerValue("point", {
                            target:pickTarget,
                            latitude:event.latlng.lat,longitude:event.latlng.lng,
                            view:{latitude:centre.lat,longitude:centre.lng,zoom:map.getZoom()}
                        });
                        pickTarget = null;
                    });
                }
                L.control.scale({imperial:false}).addTo(map);
                observer = new ResizeObserver(() => map.invalidateSize());
                observer.observe(container);
            }).catch(error => {
                if (!disposed) status.textContent = error.message;
            });
            return cleanup;
        }''')


def terrain_controls(terrain_elevations):
    with st.expander('Terrain & location'):
        if st.session_state.get('terrain_mode')=='Google Maps / phone location':
            st.session_state['terrain_mode']='Google Maps pins / coordinates'
        if st.session_state.get('terrain_mode')=='Phone GPS':
            st.session_state['terrain_mode']='Interactive map picker'
        mode=st.radio('Terrain entry',['Manual elevation','Google Maps pins / coordinates','Interactive map picker'],
            index=2,key='terrain_mode')
        if mode!='Interactive map picker':
            st.session_state.pop('map_pick_armed',None)
        if mode=='Manual elevation':
            st.caption('Enter discharge elevation in the sidebar.')
            return
        for prefix,lat,lon in [('borehole',-33.90,18.60),('outlet',-33.89,18.60)]:
            point=st.session_state.get('terrain_points',{}).get(prefix)
            if point is None:
                store_point(prefix,st.session_state.get(f'{prefix}_lat',lat),
                    st.session_state.get(f'{prefix}_lon',lon))
            else:
                for suffix,field in [('lat','latitude'),('lon','longitude')]:
                    st.session_state[f'{prefix}_{suffix}']=point[field]
        def receive_location():
            data=st.session_state['phone_location'].get('location')
            if not data:return
            try:
                if data['target'] not in ('Borehole','Outlet'):raise ValueError('Unknown GPS target')
                prefix='borehole' if data['target']=='Borehole' else 'outlet'
                store_point(prefix,data['latitude'],data['longitude'],data['accuracy'])
                st.session_state.pop('map_pick_armed',None)
                st.session_state['location_notice']=f"{data['target']} location set (accuracy ±{data['accuracy']:.0f} m)."
            except (ValueError,KeyError,TypeError) as exc:
                st.session_state['location_notice']=f'Location could not be used: {exc}'
        def receive_error():
            st.session_state['location_notice']=st.session_state['phone_location'].get('error')
        if mode=='Google Maps pins / coordinates':
            st.caption('Paste latitude, longitude (with or without parentheses), or a full Google Maps pin URL.')
            st.caption('For shortened Google Maps links, open the pin and copy its coordinates; the short URL alone does not contain coordinates.')
        else:
            st.caption('Choose Borehole or Outlet. Set point on map enables one click or tap to place its pin; Use phone GPS sets it to this device’s location with reported accuracy. GPS requires browser permission and HTTPS (or localhost).')
            def cancel_map_pick():
                st.session_state.pop('map_pick_armed',None)
            selection,action,gps=st.columns(3,vertical_alignment='bottom')
            target=selection.selectbox('Point to set',['Borehole','Outlet'],key='map_pick_target',
                on_change=cancel_map_pick)
            if action.button('Set point on map'):
                st.session_state['map_pick_armed']=target
            with gps:
                location_component()(key='phone_location',data={'target':target},
                    on_location_change=receive_location,on_error_change=receive_error)
            if st.session_state.get('map_pick_armed'):
                st.info(f"Click or tap the map to place the {st.session_state['map_pick_armed'].lower()} pin.")
        def receive_map_point():
            data=st.session_state['terrain_satellite'].get('point')
            if not data:return
            try:
                if data['target'] not in ('Borehole','Outlet'):raise ValueError('Unknown map target')
                if mode!='Interactive map picker' or data['target']!=st.session_state.get('map_pick_armed'):
                    raise ValueError('Press Set point on map before placing the selected pin.')
                prefix='borehole' if data['target']=='Borehole' else 'outlet'
                store_point(prefix,data['latitude'],data['longitude'])
                st.session_state['map_picker_view']=data['view']
                st.session_state.pop('map_pick_armed',None)
                st.session_state['location_notice']=f"{data['target']} pin placed on map."
            except (ValueError,KeyError,TypeError) as exc:
                st.session_state['location_notice']=f'Map point could not be used: {exc}'
        if st.session_state.get('location_notice'):st.info(st.session_state['location_notice'])
        for prefix,label,lat,lon in [('borehole','Borehole',-33.90,18.60),('outlet','Outlet',-33.89,18.60)]:
            if mode=='Interactive map picker':continue
            if mode=='Google Maps pins / coordinates':
                text=st.text_input(f'{label} Google Maps pin / coordinates',key=f'{prefix}_pin',
                    placeholder='(-33.955283976316174, 18.702626533523638)')
                if st.button(f'Use {label.lower()} pin'):
                    try:
                        latitude,longitude=parse_map_coordinates(text)
                        store_point(prefix,latitude,longitude)
                    except ValueError as exc:st.error(str(exc))
            accuracy=st.session_state['terrain_points'][prefix]['accuracy_m']
            if accuracy is not None:st.caption(f'{label} GPS accuracy: ±{accuracy:.0f} m')
        coordinates=tuple(st.session_state[k] for k in ('borehole_lat','borehole_lon','outlet_lat','outlet_lon'))
        st.caption('Display map loads Esri satellite imagery/labels and Leaflet from external services. Map requests reveal the viewed area to the tile provider.')
        picker=mode=='Interactive map picker'
        if not picker and st.button('Display points on satellite map'):
            st.session_state['terrain_map_visible']=True
        if picker or st.session_state.get('terrain_map_visible'):
            if not picker and st.button('Hide satellite map'):st.session_state['terrain_map_visible']=False
            else:
                satellite_component()(key='terrain_satellite',data={'points':map_points(),
                    'picker':picker,'target':st.session_state.get('map_pick_armed') if picker else None,
                    'view':st.session_state.get('map_picker_view') if picker else None},
                    on_point_change=receive_map_point,height=500)
        if picker:
            for point in map_points():
                st.write(f"{point['label']} latitude: {point['latitude']:.6f} | Longitude: {point['longitude']:.6f}")
                if point['accuracy_m'] is not None:
                    st.caption(f"{point['label']} GPS accuracy: ±{point['accuracy_m']:.0f} m")
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
        st.caption('SRTM30m terrain data has approximately 30 m grid spacing, not 30 m vertical accuracy. Verify elevations and route high points on site; enter hose route length separately. Phone location requires HTTPS or localhost.')
