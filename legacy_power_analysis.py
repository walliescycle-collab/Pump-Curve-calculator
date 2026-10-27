"""Reproduce the legacy-photo duty analysis without changing application settings."""
from pathlib import Path
import warnings

import pandas as pd

from hydraulics import (
    ROOT, ENGINES, CurveRangeError, Installation, LowRPMEstimateWarning,
    curve_value, load_pumps, low_speed_notes, required_rpm, system_head,
)

TRANSMISSION_EFFICIENCY = .90
LARGE_DRIVE_KW = 60 * .745699872
PHOTO_MAX_RPM = {
    'BP16M':1500, 'GW1302':1500, 'WA22-2':1500, 'DW15':1200,
    'DW2402':1200, 'DW2404':1200, 'WA30-2':1500, 'DW4002':1200,
    'WA50-2':1300, 'BP50M':1300, 'WA90-2':1000, 'GW9002':1000,
    'GW9602':960, 'WA110-2':1100,
}


def photo_cases():
    """Keep photo-specific corrections separate from the app's legacy dataset."""
    source = pd.read_csv(ROOT / 'data' / 'legacy_limits.csv')
    cases = []
    for row in source.to_dict('records'):
        if pd.isna(row['base_limit_ls']):
            continue
        dual = pd.notna(row['large_drive_limit_ls'])
        label = row['legacy_engine']
        engine = label.split()[0]
        base_drive = 'small' if dual or 'small' in label else 'large'
        variants = [('non-italic', row['base_limit_ls'], base_drive, False)]
        if dual:
            alternate = row['large_drive_limit_ls']
            if row['pump']=='WA50-2' and row['column_mm']==80 and row['depth_m']==100:
                alternate = 11.1  # Photo reads 11.1, not 11.11.
            if row['pump']=='GW1302' and row['column_mm']==100 and row['depth_m']==120:
                alternate = 5.8
            variants.append(('italic', alternate, 'large', False))
        if row['pump'] in ('WA90-2','GW9002','WA110-2') and row['column_mm']==80 and row['depth_m']==80:
            variants.append(('parenthesised 18 L/s', 18., base_drive, True))
        for variant, flow, drive, not_advised in variants:
            cases.append({
                'pump':row['pump'], 'column_mm':row['column_mm'],
                'depth_m':row['depth_m'], 'hose_mm':80 if row['column_mm']==50 else 100,
                'hose_length_m':100, 'outlet_elevation_m':0,
                'static_lift_m':150 if row['pump']=='GW9602' else row['depth_m'],
                'yield_ls':flow, 'photo_variant':variant, 'drive':drive,
                'engine':engine, 'engine_rated_kw':ENGINES[engine],
                'not_advised':not_advised,
                'photo_rpm_limit':min(PHOTO_MAX_RPM[row['pump']],1100) if drive=='small' else PHOTO_MAX_RPM[row['pump']],
            })
    return pd.DataFrame(cases)


def calculate_case(case, pumps):
    result = dict(case)
    notes = []
    if case['not_advised']:
        notes.append('Photo marks 18 L/s with 3-inch column as not advised; excluded from engine summary.')
    if case['pump']=='GW9602':
        notes.append('150 m static lift per confirmed assumption, plus friction at listed column length.')
    installation = Installation(
        depth_m=case['depth_m'], column_mm=case['column_mm'],
        hose_mm=case['hose_mm'], hose_length_m=100,
    )
    head = system_head(case['yield_ls'], installation)
    result.update({
        'column_loss_m':head['column_loss_m'], 'layflat_loss_m':head['layflat_loss_m'],
        'total_head_m':case['static_lift_m']+head['column_loss_m']+head['layflat_loss_m'],
        'hydraulic_kw':case['yield_ls']*.00980665*(case['static_lift_m']+head['column_loss_m']+head['layflat_loss_m']),
        'required_rpm':None, 'pump_absorbed_kw':None, 'engine_required_kw':None,
        'implied_min_fraction':None, 'implied_min_fraction_pct':None,
        'rpm_limit_exceeded':False, 'large_drive_power_exceeded':False,
        'summary_eligible':False, 'status':'unavailable', 'error':'',
        'transmission_efficiency':TRANSMISSION_EFFICIENCY,
    })
    notes.extend(head['notes'])
    pump = pumps.get(case['pump'])
    if pump is None:
        result['error'] = 'No built-in performance curve for this pump; no substitute assumed.'
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', LowRPMEstimateWarning)
                rpm = required_rpm(pump, case['yield_ls'], result['total_head_m'])
                result['required_rpm'] = rpm
                result['rpm_limit_exceeded'] = rpm > case['photo_rpm_limit'] + 1e-7
                power = curve_value(pump, result['total_head_m'], rpm, 'power')
            notes.extend(low_speed_notes(pump, rpm))
            result['pump_absorbed_kw'] = power
            result['engine_required_kw'] = power / TRANSMISSION_EFFICIENCY
            fraction = result['engine_required_kw'] / case['engine_rated_kw']
            result['implied_min_fraction'] = fraction
            result['implied_min_fraction_pct'] = fraction * 100
            result['large_drive_power_exceeded'] = case['drive']=='large' and power>LARGE_DRIVE_KW
            result['summary_eligible'] = not (
                case['not_advised'] or result['rpm_limit_exceeded'] or
                result['large_drive_power_exceeded'] or low_speed_notes(pump, rpm)
            )
            result['status'] = 'calculated' if result['summary_eligible'] else 'calculated; review limits'
            if result['rpm_limit_exceeded']:
                notes.append('Required RPM exceeds photo drive/pump speed limit; excluded from engine summary.')
            if result['large_drive_power_exceeded']:
                notes.append('Pump power exceeds 60 HP large-drive rating; excluded from engine summary.')
            if fraction>1:
                notes.append('Required engine power exceeds confirmed continuous engine rating.')
        except CurveRangeError as exc:
            result['error'] = str(exc)
    result['notes'] = ' | '.join(notes)
    return result


def engine_summary(details):
    rows = []
    for engine, rated in ENGINES.items():
        for drive in ('small','large'):
            group = details[(details.engine==engine) & (details.drive==drive)]
            valid = group[group.summary_eligible]
            row = {
                'engine':engine, 'drive':drive, 'rated_kw':rated,
                'photo_cases':len(group), 'calculated_cases':int(group.pump_absorbed_kw.notna().sum()),
                'eligible_cases':len(valid), 'excluded_cases':len(group)-len(valid),
                'min_required_engine_kw':None, 'median_required_engine_kw':None,
                'max_required_engine_kw':None, 'max_implied_min_fraction':None,
                'controlling_setup':'',
                'interpretation':'Lower-bound estimate only; maximum available engine power is not identified by these duties.',
            }
            if len(valid):
                controlling = valid.loc[valid.engine_required_kw.idxmax()]
                row.update({
                    'min_required_engine_kw':valid.engine_required_kw.min(),
                    'median_required_engine_kw':valid.engine_required_kw.median(),
                    'max_required_engine_kw':controlling.engine_required_kw,
                    'max_implied_min_fraction':controlling.implied_min_fraction,
                    'controlling_setup':f"{controlling.pump}, {controlling.column_mm} mm column, {controlling.depth_m} m, {controlling.yield_ls:g} L/s",
                })
            rows.append(row)
    return pd.DataFrame(rows)


def export_analysis(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pumps = load_pumps()
    details = pd.DataFrame([calculate_case(case,pumps) for case in photo_cases().to_dict('records')])
    summary = engine_summary(details)
    assumptions = pd.DataFrame([
        ('Purpose','Pump/engine duty requirements and implied minimum available fractions, not measured maximum engine output.'),
        ('Head','Static lift = installation depth; zero outlet elevation; full-depth column friction plus 100 m layflat friction.'),
        ('Layflat','50 mm column uses 80 mm hose; 65/80/100 mm columns use 100 mm hose, per photo footer.'),
        ('GW9602','150 m static lift plus listed column and hose friction. No head extrapolation; unavailable cases retained.'),
        ('Engine conversion','Engine required kW = pump absorbed kW / 0.90. No extra mechanical loss or sizing margin.'),
        ('Engine ratings',str(ENGINES)),
        ('Dual cells','Non-italic = small drive; italic = large drive. Both use the cell engine colour. White italic entries use F3L912 large drive.'),
        ('Single cells','Drive follows colour legend: white small drive, coloured cells large (60 HP) drive.'),
        ('18 L/s','Parenthesised 18 L/s cases retained separately but not advised and excluded from summaries.'),
        ('Curve limits','No upper-RPM or head extrapolation. Out-of-domain results remain blank with an explicit error.'),
        ('Summary','Maximum of eligible required power is a lower bound only, not a recommended availability setting. Includes duties potentially limited by flow/RPM.'),
        ('Small drive','Power rating not supplied. Only its 1100 RPM cap can be checked; small-drive power capacity remains unverified.'),
        ('Data quality','Built-in manual graph digitisation; approximate curve readings. DW15 has no built-in curve.'),
        ('Photo correction','WA50-2, 80 mm column, 100 m depth, italic yield transcribed as 11.1 L/s. Existing app data unchanged.'),
        ('Photo correction 2','GW1302, 100 mm column, 120 m depth, italic yield transcribed as 5.8 L/s rather than existing 5.7.'),
    ], columns=['assumption','value'])
    details.to_csv(output_dir/'legacy_power_details.csv',index=False)
    summary.to_csv(output_dir/'legacy_engine_summary.csv',index=False)
    assumptions.to_csv(output_dir/'legacy_power_assumptions.csv',index=False)
    with pd.ExcelWriter(output_dir/'legacy_power_analysis.xlsx',engine='openpyxl') as writer:
        for name, frame in [('Duty calculations',details),('Engine summary',summary),('Assumptions',assumptions)]:
            frame.to_excel(writer,sheet_name=name,index=False)
            sheet = writer.sheets[name]
            sheet.freeze_panes = 'A2'
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = min(75,max(14,len(str(column[0].value))+2))
            for row in sheet.iter_rows(min_row=2):
                for cell in row:
                    if isinstance(cell.value,float):
                        cell.number_format = '0.000'
    return details, summary


if __name__=='__main__':
    details, summary = export_analysis(ROOT/'analysis_results')
    print(f"Exported {len(details)} photo duties to {ROOT / 'analysis_results'}")
    print(details.status.value_counts().to_string())
    print(summary[summary.photo_cases>0].to_string(index=False))
