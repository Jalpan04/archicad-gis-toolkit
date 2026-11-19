# Module 1: GIS-to-Archicad Site Context Generator

Turn any latitude/longitude in India into Archicad 29-ready site context in under 30 seconds:
- `site_context_2d.dxf` — Layered 2D site plan (roads by hierarchy, building footprints, height labels, green cover, water, North arrow, 100 m scale bar, UTM Survey Point notes).
- `site_context_3d_massing.dxf` — 3D extruded building massing volumes (`3DFACE`) + road network for instant shadow/sun/skyline studies.
- `terrain_surveyors_relative.xyz` & `terrain_surveyors_amsl.xyz` — Real Copernicus DEM elevation grid for Archicad's 1-click 3D Terrain Mesh tool.
- `site_preview.png` — Nolli-style architectural figure-ground preview for quick visual QA.
- `origin.json` — Exact WGS84 + UTM coordinates for Archicad's Survey Point.

## Why Architects Care About What This Script Does

1. **Automatic Metric Projection (WGS84 -> UTM)**
   OpenStreetMap stores coordinates in latitude/longitude degrees (`EPSG:4326`). CAD/BIM software works in flat meters. `01_fetch_osm_data.py` automatically selects the right UTM zone (e.g., Ahmedabad = UTM Zone 43N = `EPSG:32643`).

2. **Project Origin (0, 0) vs. Survey Point**
   If you drop raw UTM coordinates (~246,000 m East, ~2,550,000 m North) into Archicad, 3D orbit navigation and OpenGL/Metal shaders suffer floating-point jitter. Our script translates the site center to `(0, 0)` while saving the exact UTM offset in `origin.json` so the team can configure Archicad's Survey Point properly.

3. **Clean Studio CAD Layers**
   - `01-SITE-BOUNDARY`
   - `02-ROADS-MAJOR`, `02-ROADS-MINOR`, `02-ROADS-PEDESTRIAN`
   - `03-BUILDINGS-FOOTPRINT`, `03-BUILDINGS-3D-MASSING`, `03-BUILDINGS-HEIGHT-TXT`
   - `04-LANDSCAPE-GREEN`
   - `05-WATER`
   - `06-ANNOTATIONS`

## How to Run for Any Site

From `d:\Arch\learning top be useful`:

```powershell
# Default: Sangath Studio, Thaltej, Ahmedabad (400 m radius)
.venv\Scripts\python.exe module1_gis_to_archicad\run_site_generator.py

# Custom site (example: Sabarmati Riverfront, 500 m radius)
.venv\Scripts\python.exe module1_gis_to_archicad\run_site_generator.py --lat 23.0225 --lon 72.5714 --radius 500 --name Sabarmati_Riverfront
```

## Importing into Archicad 29 (Step-by-Step)

### A. Import the 2D Context Plan (`site_context_2d.dxf`)
Best studio practice is to place reference DWGs/DXFs on a **Worksheet** rather than directly on the Ground Floor, then turn on **Trace & Reference** so the floor plan stays clean.

1. In Archicad 29 Navigator, right-click **Worksheets** -> **New Independent Worksheet** (name it `Site Context - OSM`).
2. Go to **File -> Interoperability -> Merge -> Merge from File...**
3. Select `site_context_2d.dxf`.
4. Choose **Merge content of Model Space into current View**.
5. In the Merge DXF dialog:
   - **Insertion Point:** `X = 0`, `Y = 0` (Archicad Project Origin).
   - **Translator Settings -> Drawing Unit:** confirm `1 DXF drawing unit = 1 Meter`.
6. Click **Merge**. Press **Fit in Window** (`Ctrl + '`).
7. Switch back to **0. Ground Floor**, right-click the Worksheet in Navigator -> **Show as Trace Reference**.

### B. Import the 3D Context Massing (`site_context_3d_massing.dxf`)
1. Go to **File -> Libraries and Objects -> Open Object...** (or **File -> Interoperability -> Merge...** and choose **Merge into 3D** / **Import as GDL Object**).
2. Alternatively, use **File -> Interoperability -> Merge -> Merge from File...** on Floor Plan with `site_context_3d_massing.dxf` -> select **Import Model Space content as GDL Object** -> click at `(0, 0)`.
3. Press **F3** (3D Window). You will see the surrounding urban massing centered at `(0, 0)`.
4. Optional: Select the placed object -> right-click -> **Convert Selection to Morph(s)** if you want to edit or delete individual surrounding buildings (for example, clearing your actual project plot).

### C. Import the 3D Terrain Mesh (`terrain_surveyors_relative.xyz`)
1. On **0. Ground Floor**, go to **File -> Interoperability -> Place Mesh from Surveyors Data...**
2. Select `terrain_surveyors_relative.xyz` (this keeps the site center at `Z = 0.00 m`, matching Ground Floor).
3. In the dialog:
   - **Units:** `Meters`
   - **Location:** `Define graphically` or `Original location` (Project Origin `0, 0`).
   - **Z coordinate:** `Use Z values from file` (relative to Project Zero).
4. Click **OK** -> Press **F3** to inspect the 3D terrain aligned directly underneath your 2D roads and 3D buildings!

### D. Optional Pro Move: Set Archicad Survey Point
Open `origin.json` and check `utm_origin_easting_m` and `utm_origin_northing_m`.
In Archicad 29, go to **Options -> Project Preferences -> Location Settings** to enter the site latitude, longitude, and Survey Point Easting/Northing so Sun Studies (`Document -> Creative Imaging -> Create Sun Study`) calculate exact Ahmedabad solar angles!
