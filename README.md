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

New sessions default to **L/s**, **WA50-2** in planning, field checks and source inspection, and four test yields of **3, 4, 6 and 8 L/s**. Saved setups and subsequent user selections override these defaults. Older setups without a flow-unit setting use L/s.

1. Enter project, borehole clearance, installation depth, column and layflat sizes, route length, and discharge elevation difference. Optional terrain lookup estimates the two endpoint elevations; verify small differences on site.
2. Enter four planned yields, or enable up to 24 steps. Each step has a pumping water level. The default design lift remains the full installation depth; switch lift assumption to use the individual levels.
3. Inspect the shortlist and choose **Pump selection**. Every step is checked against pump, bore and angle-drive limits. Exceeding the selected engine's usable pump-shaft power produces a warning/Conditional qualification, not an engine-only rejection. Minimum-engine recommendations remain duty-based. Unknown bore sizes and outside diameters remain blank.
4. The four-part head contribution bars appear immediately above the performance curves; the detailed head table remains below the curves. Every segment is labelled as a percentage of the selected pump's maximum rated head, not the requested duty head. Head grids use 25 m intervals across pumps. The rated-head line and total/spare/overload labels show capacity usage. Downhill elevation is a signed negative contribution, not hidden or clamped.
5. Use the sidebar **Performance curve flow units** selector for m³/h or L/s in both planning and field-check performance plots. Inputs, detail tables and CSV results remain in L/s. Source knots, RPM labels and head bounds are retained; field-check flow bounds expand if necessary to keep measured points visible.
6. **Min motor kW** is the source sheet's minimum motor rating; blank means not supplied. **Max curve kW** is the peak absorbed power on the highest published RPM power curve, within the rated head domain, without diesel margins. **Power curve RPM** identifies that speed. For WA110-2 this is 960 RPM, not the 1100 RPM flow-only curve; no missing power curve is extrapolated.
7. Enable **Simplified** directly under **Lift assumption** to keep inputs, pump selection, head-percentage bars and performance/field RPM plots, while hiding comparison/detail tables, diesel/system panels, exports and source material. Essential calculation and operating-limit messages remain visible.
8. Streamlit's native Light/Dark setting controls the app and plot themes. Downloaded charts use the theme and flow units selected when generated.
9. In normal mode, export results and save the setup JSON (including flow units and simplified setting). On site, **Field curve check** uses the same source-style performance plot as planning, with measured and expected-at-actual-RPM flow points. A separate Expected/Actual RPM chart labels `(actual - expected) / expected × 100`. Measured-head mode does not invent a four-part split.

### Google Maps and phone location (no API key)

Open **Terrain & location**, switch from **Manual elevation** to **Google Maps / phone location**, and set the borehole and outlet pins. Open Google Maps using the provided links; right-click (or long-press on a phone) to copy a pin's latitude/longitude, or paste a full pin link containing `q=`, `query=`, or `!3d...!4d...` coordinates. Shortened links and map-centre-only URLs are rejected explicitly: open the link in Google Maps and copy the actual pin coordinates. No Google API key or billing is needed; there is no embedded Google map.

Choose **Point to set**, then **Use my current location** to request that device's browser location. This is opt-in, requires browser permission and HTTPS (or localhost), and reports the accuracy estimate. To use a phone's location, open the deployed app on that phone. Permission denial, unavailable location and timeouts are shown explicitly; manual pin entry always remains available.

Only **Look up terrain elevations** sends the two coordinate pairs to Open Topo Data. Apply the resulting elevation difference explicitly; changing either coordinate disables the old result until a new lookup. Terrain is approximate 90 m data, not a survey, and does not calculate route length or route high points. A fresh location does not silently overwrite the installation elevation.

### Selected-engine limit on performance curves

Both planning and field-check performance displays include a **red dashed horizontal line** on the absorbed-kW panel and a corresponding **red dashed equal-power boundary** on the yield/head panel. Usable pump power = selected engine continuous kW × available-power fraction × transmission efficiency − additional shaft/bearing loss. The diesel sizing margin is deliberately excluded from this physical power limit; minimum-engine recommendations still include it. Angle-drive limits remain separate.

The flow boundary solves the existing piecewise-linear power/RPM model at each head, then uses that RPM on the flow curve. It is drawn only within overlapping published head/RPM domains, with the existing low-speed zero-anchor convention. Flow display bounds expand if needed to show a supported engine boundary. No upper-speed or missing power curves are invented (notably WA110-2 above 960 RPM). If available engine power exceeds every published power curve, the upper panel explicitly reports that there is no equal-power boundary; the lower limit line remains visible by expanding the power axis. Negative available power means mechanical losses alone exceed engine availability.

Warnings trigger only when a calculated planned step or the estimated absorbed power at measured field head/actual RPM exceeds the limit, not just because a displayed source curve crosses it. Exact equality is not an overload. Field power is a source-curve estimate, not a measured shaft-power reading; unavailable power domains are reported explicitly. Limits and warnings remain in Simplified mode, both flow units, light/dark themes and performance HTML exports.

## Calculation model

The Four-part head calculation and AB Pumps quick-reference cross-check tables use formal engineering column labels with units in square brackets (`[-]` for non-physical fields). Physical quantities display two decimal places; test-step numbers remain integers. Headers retain Streamlit's native bold-weight styling and interactive sorting; underlying precision, field names and exported data are unchanged.

The source-style performance chart overlays dashed system curves on the upper flow-versus-head panel, retaining head on the horizontal axis and the selected flow unit on the vertical axis. Full-depth mode shows one system curve; individual-level mode shows one per distinct pumping water level. The overlay is included in HTML downloads. Planning source bounds remain fixed; curves outside these bounds are clipped. Head grids are standardized at 25 m rather than reproducing source head-grid intervals. There is no system curve on the absorbed-power panel.

Total head = pumping lift + column friction + surface discharge elevation difference + layflat friction. Pipe friction always uses the full installed column length. In conservative design mode pumping lift equals installation depth. No fittings, outlet pressure or discharge velocity head are included, as requested. Negative elevation is allowed but downhill/siphon cases are flagged.

The included pumps are positive-displacement pumps. Flow and power use piecewise-linear head/RPM interpolation, **not centrifugal affinity laws**. Yield mode solves required RPM at system head; RPM mode solves the pump/system intersection. Positive pump speeds below 100 RPM are accepted. Below the lowest published flow or power speed, the confirmed estimation convention interpolates toward a synthetic 0 RPM / 0 flow / 0 absorbed-kW anchor at the same head. This is a qualified low-speed estimate, not published performance or a guarantee of starting torque, sealing or minimum stable flow. Warnings appear in planning conditions, step/export notes, field comparisons and direct Python calls (`LowRPMEstimateWarning`). Nonpositive flow remains invalid. Head limits, source head domains and upper flow/power RPM limits are not extended. Source-style plots preserve the original axes, even where these estimates lie below their visible bounds.

Hydraulic kW is distinct from pump absorbed kW. Required engine output = (pump absorbed kW + additional mechanical loss) / transmission efficiency × sizing factor. Continuous ratings at 2300 engine RPM are F3L912 **36 kW**, F4L912 **49 kW**, F5L912 **61 kW**, F6L912 **74 kW**, and user-confirmed F6L413F (V6) **102 kW**. These are not ratings at arbitrary engine speeds. The minimum recommendation is the smallest engine whose rating × available fraction meets the peak requirement over every step. The installed-engine selector sets the red usable-power limit and operating-point warnings, without making an engine-only rejection. Angle-drive power/RPM checks remain active. Historical V6 references now identify F6L413F, not F6L912.

Default transmission efficiency is 90%, sizing factor 1.33 and available-power fraction 90%. These are editable assumptions, not measured losses or automatic altitude correction. The default angle drive is 60 HP with a 1100 pump-RPM cap. Confirm actual drive limits. Starting torque and rod mechanical design are not certified. Saved setups and Excel exports record the installed engine. Older setups discard obsolete engine-speed settings, report default F3L912 metadata if missing, and migrate F6L413FW to the confirmed F6L413F name.

## Data review and limitations

In the sidebar, **Diesel drive settings > Advanced settings** expands the transmission efficiency, additional shaft/bearing mechanical loss, diesel sizing factor and available engine power fraction controls. This section is collapsed by default; collapsing it does not reset the values or disable their effect on calculations.

- `data/pumps.json` retains source, quality and model notes. `data/curve_points.csv` exposes every digitized knot. Source scans and retrieved manufacturer sheets are in `sources/`. Graph readings are approximate; numerical NOV tables are transcribed. Review against the full source sheets before operational release.
- Included WASA models: WA16-2, WA22-1, WA22-2, WA22-3, WA30-2, WA30-4, WA50-2, WA50-4, WA65-2, WA90-2 and WA110-2. Handwritten DW aliases are retained. DW15 appears only in the legacy comparison because no corresponding performance curve was available.
- GW9602 is capped at 150 m as instructed. GW5406 retains its provisional source status. WA110-2 flow extends to 1100 RPM but power data end at 960 RPM: higher-speed duties cannot receive a complete engine recommendation.
- Unknown minimum bore diameters and pump outside diameters remain unknown. The supplied performance sheets do not specify actual pump outside diameters; column sizes and known minimum bore sizes are not substituted. The comparison includes both columns. Add verified outside diameters to `build_data.py` and rebuild when specifications become available. Pump outside diameter is not treated as guaranteed installation clearance. Adapter/column/rod differences require confirmation.
- CEMO column losses are read from the supplied shaft-and-bearing chart for 40–100 mm. The lower 40/50 mm panel is interpreted using the sheet's m³/h flow convention. The missing 150 mm curve is an explicitly labelled annular scaling estimate. Outside chart flow limits, losses use a labelled quadratic extension.
- PVC layflat uses Rain-Flo's published inch-size friction table mapped to nominal metric 50/65/80/100/150 mm. The missing 200 mm curve is estimated by diameter scaling. Flow extensions use Q^1.85 and are flagged. Actual hose internal diameter and deformation can change losses. These are not manufacturer-certified metric hose curves.
- Velocity uses nominal diameters and assumed shaft diameters (13/16/19/22/25/40 mm respectively). A 3 m/s review threshold is used. This is a warning, not a universal permissible velocity.
- The old AB quick chart retains its reference depths, columns and hose arrangements. Its engine colours are historical guidance, not a replacement for power calculations. The V6 model is confirmed as F6L413F.
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

Automated tests cover unit conversion, signed rated-head percentages/overload, pump kW ranges, interpolation domains, low-RPM round trips for every pump, all-step limits, minimum diesel recommendations independent of installed-engine selection, 25 m grids, both flow units and plot themes, field RPM deviation, pin parsing, stale terrain results, setup migration, simplified view and 24-step interaction. Browser location additionally needs a real browser/device permission check. Tests validate software behaviour, not digitization accuracy or commissioning.
