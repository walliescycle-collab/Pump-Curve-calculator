import pytest
import streamlit as st
from locations import parse_map_coordinates,validate_coordinates,store_point,map_points,edited_coordinates


@pytest.mark.parametrize('text',[
    '-33.9,18.6',
    'https://www.google.com/maps?q=-33.9,18.6',
    'https://www.google.com/maps/search/?api=1&query=-33.9%2C18.6',
    'https://www.google.com/maps/place/pin/@-32,17,12z/data=!3d-33.9!4d18.6'])
def test_pin_coordinates(text):
    assert parse_map_coordinates(text)==(-33.9,18.6)


@pytest.mark.parametrize('text',['','nan,18','-91,0','0,181',
    'https://maps.app.goo.gl/example','https://example.org/?q=-33,18',
    'https://www.google.com/maps/@-33.9,18.6,10z'])
def test_unsupported_coordinates_are_explicit_errors(text):
    with pytest.raises(ValueError):parse_map_coordinates(text)


def test_browser_location_validation():
    assert validate_coordinates(-33.9,18.6)==(-33.9,18.6)
    with pytest.raises(ValueError):validate_coordinates(float('nan'),18)


def test_ab_pumps_parenthesized_example():
    assert parse_map_coordinates('(-33.955283976316174, 18.702626533523638)')==(
        -33.955283976316174,18.702626533523638)


def test_gps_accuracy_and_manual_edits(monkeypatch):
    monkeypatch.setattr(st,'session_state',{})
    store_point('borehole',-33.95,18.70,12.)
    store_point('outlet',-33.96,18.71)
    points=map_points()
    assert [point['label'] for point in points]==['Borehole','Outlet']
    assert points[0]['accuracy_m']==12 and points[1]['accuracy_m'] is None
    st.session_state['borehole_lat']=-33.94
    edited_coordinates('borehole')
    assert map_points()[0]['latitude']==-33.94
    assert map_points()[0]['accuracy_m'] is None
    store_point('outlet',-33.96,18.71,0.)
    assert map_points()[1]['accuracy_m']==0.


@pytest.mark.parametrize('accuracy',[-1,float('nan'),float('inf')])
def test_invalid_accuracy_is_not_stored(monkeypatch,accuracy):
    monkeypatch.setattr(st,'session_state',{})
    with pytest.raises(ValueError):store_point('borehole',-33.95,18.70,accuracy)
    assert 'terrain_points' not in st.session_state
