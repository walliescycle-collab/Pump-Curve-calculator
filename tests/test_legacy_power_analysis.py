import pandas as pd
import pytest

from hydraulics import load_pumps, curve_value, system_head, Installation
from legacy_power_analysis import photo_cases, calculate_case, export_analysis


def test_photo_variants_and_hose_sizes():
    cases = photo_cases()
    assert len(cases)==162
    assert set(cases[cases.column_mm==65].hose_mm)=={100}
    assert set(cases[cases.column_mm==50].hose_mm)=={80}
    assert cases.not_advised.sum()==3
    pair = cases[(cases.pump=='BP16M') & (cases.column_mm==80) & (cases.depth_m==80)]
    assert pair.drive.tolist()==['small','large']
    assert pair.yield_ls.tolist()==[3,4.1]
    assert pair.engine.tolist()==['F3L912','F3L912']
    assert set(cases[cases.pump=='GW9602'].static_lift_m)=={150}
    corrected = cases[(cases.pump=='GW1302') & (cases.column_mm==100) &
        (cases.depth_m==120) & (cases.photo_variant=='italic')]
    assert corrected.yield_ls.iloc[0]==5.8


def test_calculated_power_matches_curves_and_engine_conversion():
    case = photo_cases().iloc[0].to_dict()
    pumps = load_pumps()
    row = calculate_case(case,pumps)
    head = system_head(case['yield_ls'],Installation(depth_m=80,column_mm=50,hose_mm=80))
    assert row['total_head_m']==pytest.approx(head['head_m'])
    assert curve_value(pumps[case['pump']],row['total_head_m'],row['required_rpm'])==pytest.approx(case['yield_ls'])
    assert row['engine_required_kw']==pytest.approx(row['pump_absorbed_kw']/.9)
    assert row['implied_min_fraction']==pytest.approx(row['engine_required_kw']/36)


def test_unavailable_cases_and_not_advised_remain_visible():
    cases = photo_cases()
    pumps = load_pumps()
    for name in ['DW15','GW9602']:
        for case in cases[cases.pump==name].to_dict('records'):
            row = calculate_case(case,pumps)
            assert row['error'] and row['pump_absorbed_kw'] is None
            assert not row['summary_eligible']
    for case in cases[cases.not_advised].to_dict('records'):
        assert not calculate_case(case,pumps)['summary_eligible']


def test_export_and_summary(tmp_path):
    details, summary = export_analysis(tmp_path)
    assert len(details)==len(photo_cases())
    assert len(pd.read_excel(tmp_path/'legacy_power_analysis.xlsx',sheet_name='Duty calculations'))==len(details)
    assert (tmp_path/'legacy_power_details.csv').exists()
    for row in summary[summary.eligible_cases>0].to_dict('records'):
        valid = details[(details.engine==row['engine']) & (details.drive==row['drive']) & details.summary_eligible]
        assert row['max_required_engine_kw']==valid.engine_required_kw.max()
        assert row['max_implied_min_fraction']==valid.implied_min_fraction.max()


def test_missing_power_keeps_rpm_and_limit_cases_are_excluded():
    cases = photo_cases()
    pumps = load_pumps()
    case = cases[(cases.pump=='WA110-2') & (cases.column_mm==100) & (cases.depth_m==80)].iloc[0].to_dict()
    row = calculate_case(case,pumps)
    assert row['required_rpm']>960
    assert row['pump_absorbed_kw'] is None
    assert 'Power curve RPM' in row['error']
    assert not row['summary_eligible']
    details = pd.DataFrame([calculate_case(c,pumps) for c in cases.to_dict('records')])
    assert details.rpm_limit_exceeded.any()
    assert not details[details.rpm_limit_exceeded].summary_eligible.any()
