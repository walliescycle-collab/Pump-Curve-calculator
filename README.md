# AB Pumps installation planner

A Streamlit planning app and editable Jupyter notebook sharing one calculation engine. Includes 29 pump models, four to 24 test steps, yield and pump-shaft RPM input, diesel sizing, measured-versus-expected performance, terrain lookup, system curves, and CSV/Excel/HTML exports.

## Run locally

Use Python 3.12 or newer. Extract the complete folder and open a terminal inside it:

### Windows PowerShell

Use a short virtual-environment path to avoid Windows path-length limits, especially when the project itself is in a deeply nested folder. Run these commands from the project folder:

```powershell
$venv = "$env:USERPROFILE\.venvs\ab-pumps"
python -m venv "$venv"
& "$venv\Scripts\python.exe" -m pip install -r requirements.txt
& "$venv\Scripts\python.exe" -m streamlit run app.py
```

These commands use the environment's Python directly: activation, PATH changes, and PowerShell execution-policy changes are unnecessary. In a new terminal, set `$venv` again before running the app. In VS Code, use **Python: Select Interpreter** to select this environment's `Scripts\python.exe`.

If an earlier installation reported a long-path error followed by `No module named 'streamlit.proto'`, Streamlit was only partially installed. Install into the short-path environment above rather than using the incomplete user-wide installation. A line beginning with `#` is a comment, not an activation command; creating a virtual environment alone does not make subsequent `python` commands use it.

For the notebook and tests, in the same PowerShell terminal:

```powershell
& "$venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
& "$venv\Scripts\python.exe" -m notebook AB_Pumps_Installation_Planner.ipynb
& "$venv\Scripts\python.exe" -m pytest tests -q
```

### macOS/Linux

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

For the notebook and tests:

```sh
python -m pip install -r requirements-dev.txt
python -m notebook AB_Pumps_Installation_Planner.ipynb
python -m pytest tests -q
```

The notebook is already executed with an example installation. Edit its installation, drive and step cells, then run all cells. Both interfaces import `hydraulics.py`; calculations are not duplicated.

## Operator workflow

1. Enter project, borehole clearance, installation depth, column and layflat sizes, route length, and discharge elevation difference. Optional terrain lookup estimates the two endpoint elevations; verify small differences on site.
2. Enter four planned yields, or enable up to 24 steps. Each step has a pumping water level. The default design lift remains the full installation depth; switch lift assumption to use the individual levels.
3. Inspect the shortlist. A pump must meet every step with the installed engine; rejected pumps explain why. The minimum engine size is a duty requirement, not a pump/engine pairing. Conditional means a specification, compatibility check or estimate still needs review. Known minimum bore sizes are separate from pump outside diameters; unknown outside diameters stay blank.
4. Select a pump to view digital source-style flow-versus-head and absorbed-kW-versus-head graphs in Plan & select. The stacked graphs retain source bounds, units, grids and RPM labels using the existing digitised knots. Flow is shown in m³/h to match the sources; other app results remain L/s. Orange dots are planned steps, clipped to the original chart bounds. Source minimum-motor labels are not diesel assignments. Download the interactive performance graphs, or use Curves & diesel for the pump/system overlay. Select the actual engine under Diesel drive settings and confirm transmission ratio, actual angle-drive rating and additional mechanical losses. Minimum engine sizing considers the largest power requirement across all steps, including the maximum-yield step.
5. Export results and save the complete setup JSON. On site, compare measured yield, head and pump-shaft RPM against the selected pump curve.

## Calculation model

The Four-part head calculation and AB Pumps quick-reference cross-check tables use formal engineering column labels with units in square brackets (`[-]` for non-physical fields). Physical quantities display two decimal places; test-step numbers remain integers. Headers retain Streamlit's native bold-weight styling and interactive sorting; underlying precision, field names and exported data are unchanged.

The source-style performance chart in Plan & select overlays dashed coloured system curves on the upper flow-versus-head panel, retaining head on the horizontal axis and flow in m³/h on the vertical axis. Full-depth mode shows one system curve; individual-level mode shows one per distinct pumping water level. The overlay is included in the performance-graph HTML download. Original axis bounds remain fixed, so out-of-bounds curve sections are clipped. There is no system curve on the absorbed-power panel: required head versus flow does not independently define pump absorbed kW.

Total head = pumping lift + column friction + surface discharge elevation difference + layflat friction. Pipe friction always uses the full installed column length. In conservative design mode pumping lift equals installation depth. No fittings, outlet pressure or discharge velocity head are included, as requested. Negative elevation is allowed but downhill/siphon cases are flagged.

The included pumps are positive-displacement pumps. Flow and power use piecewise-linear head/RPM interpolation, **not centrifugal affinity laws**. Yield mode solves required RPM at system head; RPM mode solves the pump/system intersection. Positive pump speeds below 100 RPM are accepted. Below the lowest published flow or power speed, the confirmed estimation convention interpolates toward a synthetic 0 RPM / 0 flow / 0 absorbed-kW anchor at the same head. This is a qualified low-speed estimate, not published performance or a guarantee of starting torque, sealing or minimum stable flow. Warnings appear in planning conditions, step/export notes, field comparisons and direct Python calls (`LowRPMEstimateWarning`). Nonpositive flow remains invalid. Head limits, source head domains and upper flow/power RPM limits are not extended. Source-style plots preserve the original axes, even where these estimates lie below their visible bounds.

Hydraulic kW is distinct from pump absorbed kW. Required engine output = (pump absorbed kW + additional mechanical loss) / transmission efficiency × sizing factor. The fixed continuous engine ratings supplied for 2300 engine RPM are F3L912 **36 kW**, F4L912 **49 kW**, F5L912 **61 kW**, F6L912 **74 kW**, and F6L413FW (V6) **102 kW**. Lower-engine-speed interpolation has been removed; these ratings must not be interpreted as available at arbitrary engine speeds. Engine choice is independent of pump model. The minimum size is the smallest engine whose rating × available-power fraction meets the peak requirement over every step. The installed engine is selected separately in Diesel drive settings (default F3L912); insufficient installed power makes that operating plan unsuitable, even if a larger engine is recommended.

Default transmission efficiency is 90%, sizing factor 1.33 and available-power fraction 90%. These are editable planning assumptions, not measured losses or an automatic altitude correction. The default angle drive is 60 HP with a 1100 pump-RPM cap. Select actual drive limits before use. Running torque is reported; starting torque and rod mechanical design are not certified by this model. Saved setups and Excel exports include the installed engine. Restoring an older setup discards its obsolete engine-speed setting and explicitly reports the default F3L912 when no engine was saved.

## Data review and limitations

In the sidebar, **Diesel drive settings > Advanced settings** expands the transmission efficiency, additional shaft/bearing mechanical loss, diesel sizing factor and available engine power fraction controls. This section is collapsed by default; collapsing it does not reset the values or disable their effect on calculations.

- `data/pumps.json` retains source, quality and model notes. `data/curve_points.csv` exposes every digitized knot. Source scans and retrieved manufacturer sheets are in `sources/`. Graph readings are approximate; numerical NOV tables are transcribed. Review against the full source sheets before operational release.
- Included WASA models: WA16-2, WA22-1, WA22-2, WA22-3, WA30-2, WA30-4, WA50-2, WA50-4, WA65-2, WA90-2 and WA110-2. Handwritten DW aliases are retained. DW15 appears only in the legacy comparison because no corresponding performance curve was available.
- GW9602 is capped at 150 m as instructed. GW5406 retains its provisional source status. WA110-2 flow extends to 1100 RPM but power data end at 960 RPM: higher-speed duties cannot receive a complete engine recommendation.
- Unknown minimum bore diameters and pump outside diameters remain unknown. The supplied performance sheets do not specify actual pump outside diameters; column sizes and known minimum bore sizes are not substituted. The comparison includes both columns. Add verified outside diameters to `build_data.py` and rebuild when specifications become available. Pump outside diameter is not treated as guaranteed installation clearance. Adapter/column/rod differences require confirmation.
- CEMO column losses are read from the supplied shaft-and-bearing chart for 40–100 mm. The lower 40/50 mm panel is interpreted using the sheet's m³/h flow convention. The missing 150 mm curve is an explicitly labelled annular scaling estimate. Outside chart flow limits, losses use a labelled quadratic extension.
- PVC layflat uses Rain-Flo's published inch-size friction table mapped to nominal metric 50/65/80/100/150 mm. The missing 200 mm curve is estimated by diameter scaling. Flow extensions use Q^1.85 and are flagged. Actual hose internal diameter and deformation can change losses. These are not manufacturer-certified metric hose curves.
- Velocity uses nominal diameters and assumed shaft diameters (13/16/19/22/25/40 mm respectively). A 3 m/s review threshold is used. This is a warning, not a universal permissible velocity.
- The old AB quick chart is retained for matching its exact depths, columns and hose arrangements. Its engine colours are typical historical pairings, not a replacement for power calculations. The unqualified “V6 Deutz” entry is not assumed to mean F6L912.
- The manual example contains an arithmetic error: 26 m/100 m × 60 m = 15.6 m, not 43 m; using its stated inputs the total is 96.6 m, not 124 m. The software uses the corrected arithmetic, with its chosen friction sources.
- No automatic 10% pump limit overrun is permitted. The configurable field comparison tolerance describes a measurement comparison only; it does not raise operating limits or diagnose the cause of poor performance.
- Terrain lookup uses Open Topo Data SRTM90m, depends on internet availability and may be inaccurate for small height differences. Manual entry always works. Endpoint elevations do not determine hose route length or route high points.

## Sources

- Franklin Electric Mono BP range: https://franklin-electric.co.za/products/mono-bp-range/
- Franklin Electric Orbit GW range: https://franklin-electric.co.za/products/orbit-gw-range/
- Individual manufacturer PDF and rendered chart copies are included in `sources/`; each pump record identifies its local source image.
- WASA catalogue, NOV/DW tables, CEMO chart and AB manual/quick chart: supplied project documents; copies of the relevant pump and friction sources are included.
- Deutz 912 continuous output: https://www.deutz.com.au/wp-content/uploads/2016/09/DEUTZ-DRIVE-The-New-Power-Pack-Series.pdf
- PVC layflat friction: https://www.rainfloirrigation.com/irrigation/charts-layouts/friction-loss-chart
- Terrain API: https://www.opentopodata.org/api/

`build_data.py` rebuilds the reviewed data files from the documented transcription. Edit that script when correcting source readings, then regenerate and run the tests. Keep original sheets unchanged.

## Public deployment

This package is deployable source, not an already published service. Put its contents in a GitHub repository and deploy `app.py` with Streamlit Community Cloud using Python 3.12+ and the included requirements. Keep `data/` and `sources/` alongside the script. Review permission to redistribute the supplied charts before making the repository public. Do not commit secrets or project-specific saved setups. The app uses session state rather than a shared database; downloaded JSON preserves a setup between sessions.

## Verification

Automated tests cover unit conversion, four-part head calculations, interpolation domains, warned sub-100-RPM yield/RPM round trips for every pump, limits across all steps, fixed diesel ratings and independently selected installed engines, source-style plot bounds/grids/knots, source coverage, terrain error handling, and Streamlit interaction through 24 steps. These checks validate software behaviour; they do not establish the accuracy of an approximate digitization or replace installation commissioning.
