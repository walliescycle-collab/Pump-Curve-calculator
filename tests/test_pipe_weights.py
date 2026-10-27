import math

import pytest

from pipe_weights import PIPE_WEIGHTS, installation_pipe_weight


@pytest.mark.parametrize('size',list(PIPE_WEIGHTS))
@pytest.mark.parametrize('length',[3,15,30,45,60,75,90,105,120])
def test_photo_rates_and_pipe_combinations(size,length):
    row=installation_pipe_weight(length+1.5,size)
    assert row.assembly_kg==length/3*PIPE_WEIGHTS[size][1]
    assert row.pipes_6m*6+row.pipes_3m*3==length
    assert row.pipes_3m in (0,1)
    assert row.achieved_depth_m==length+1.5
    assert row.shortfall_m==0


def test_rounding_down_and_water_annulus():
    row=installation_pipe_weight(100,80,pump_weight_kg=50)
    assert (row.pipes_6m,row.pipes_3m)==(16,0)
    assert row.column_length_m==96
    assert row.achieved_depth_m==97.5
    assert row.shortfall_m==2.5
    assert row.assembly_kg==1184
    assert row.dry_total_kg==1234
    assert row.contained_water_kg==pytest.approx(math.pi/4*(.08**2-.022**2)*96*1000)
    assert row.filled_total_kg==pytest.approx(1234+row.contained_water_kg)
    assert installation_pipe_weight(100,80,internal_diameter_mm=75).contained_water_kg<row.contained_water_kg


@pytest.mark.parametrize('depth',[1.5,4.499999999,4.5,7.499999999,7.5,100,1000])
def test_never_exceeds_requested_depth(depth):
    row=installation_pipe_weight(depth,65)
    assert row.achieved_depth_m<=depth
    assert 0<=row.shortfall_m<3


@pytest.mark.parametrize('kwargs',[
    {'depth_m':1}, {'depth_m':0}, {'pump_length_m':0}, {'pump_weight_kg':-1},
    {'column_mm':150}, {'internal_diameter_mm':22}, {'depth_m':float('nan')},
    {'pump_weight_kg':float('inf')},
])
def test_invalid_inputs_report_errors(kwargs):
    args={'depth_m':100,'column_mm':80}
    args.update(kwargs)
    with pytest.raises(ValueError):
        installation_pipe_weight(**args)
