import pytest
from locations import parse_map_coordinates,validate_coordinates


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
