"""Installation quantities from the supplied column/shaft/bobbin weight sheet."""
from dataclasses import dataclass
import math

from hydraulics import finite, nonnegative


# Nominal column mm: (shaft mm, combined assembly kg per 3 m).
PIPE_WEIGHTS = {40:(13,15),50:(16,20),65:(19,25),80:(22,37),100:(22,49)}


@dataclass(frozen=True)
class PipeWeightResult:
    pipes_6m: int
    pipes_3m: int
    column_length_m: float
    achieved_depth_m: float
    shortfall_m: float
    assembly_kg: float
    dry_total_kg: float
    contained_water_kg: float
    filled_total_kg: float


def installation_pipe_weight(depth_m, column_mm, pump_length_m=1.5, pump_weight_kg=0.,
                             internal_diameter_mm=None):
    nonnegative(depth_m,'Installation depth')
    nonnegative(pump_length_m,'Pump length')
    nonnegative(pump_weight_kg,'Pump weight')
    if depth_m<=0 or pump_length_m<=0:
        raise ValueError('Installation depth and pump length must be positive')
    if pump_length_m>depth_m:
        raise ValueError('Pump length exceeds the requested installation depth')
    if column_mm not in PIPE_WEIGHTS:
        raise ValueError(f'No photo weight data for {column_mm} mm column; choose 40, 50, 65, 80 or 100 mm in the sidebar')
    shaft_mm,kg_per_3m=PIPE_WEIGHTS[column_mm]
    diameter=column_mm if internal_diameter_mm is None else internal_diameter_mm
    finite(diameter,'Internal diameter')
    if diameter<=shaft_mm:
        raise ValueError('Internal diameter must exceed the shaft diameter')
    sections=math.floor((depth_m-pump_length_m)/3)
    pipes_6m,pipes_3m=divmod(sections,2)
    length=sections*3.
    achieved=length+pump_length_m
    assembly=sections*kg_per_3m
    dry=assembly+pump_weight_kg
    water=math.pi/4*((diameter/1000)**2-(shaft_mm/1000)**2)*length*1000
    return PipeWeightResult(pipes_6m,pipes_3m,length,achieved,depth_m-achieved,
        assembly,dry,water,dry+water)
