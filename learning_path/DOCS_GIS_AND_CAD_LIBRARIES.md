# Spatial Computing & CAD Automation for Architects: The Core Libraries

This document explains the core Python libraries used for spatial analysis, GIS, and Archicad automation: **Shapely**, **PyProj**, **GeoPandas**, **OSMnx**, and **ezdxf**.

---

## 1. Why VSS and Architectural Studios Need This

Architects and urban planners at firms like Vastu Shilpa Sangath deal with two separate worlds:
1. **The Geographic World (GIS):** Real-world coordinates (latitude/longitude, satellite imagery, municipal road networks, land parcel boundaries, topography).
2. **The Architectural World (CAD/BIM):** High-precision millimeter/meter drawings, local coordinate axes, layers, wall assemblies, and 3D massing inside software like **Archicad**, **AutoCAD**, and **Rhino**.

Traditionally, junior architects spend days manually importing Google Earth screenshots, tracing building footprints by hand, and guessing site elevations. With Python, you can bridge these worlds automatically.

```
+-------------------------------------------------------------+
| 1. OSMnx (OpenStreetMap API)                                |
|    Downloads real streets, buildings, green spaces, water   |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| 2. PyProj (Coordinate Reference Systems)                    |
|    Converts lat/lon degrees (EPSG:4326) to UTM meters       |
|    Shifts coordinates to (0,0) for Archicad Project Origin  |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| 3. Shapely + GeoPandas (Spatial Geometry & Analysis)        |
|    Performs setbacks, site clipping, area calculations,     |
|    ground coverage, and FSI/FAR estimations                 |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| 4. ezdxf (CAD Drafting Engine)                              |
|    Creates structured .DXF files with standard layers,      |
|    metric units, 2D polylines, and 3D extruded massings     |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| 5. Archicad 29                                              |
|    - File > Interoperability > Merge DXF (2D & 3D Massing)  |
|    - File > Interoperability > Place Mesh from Surveyors    |
+-------------------------------------------------------------+
```

---

## 2. Library Breakdown

### A. Shapely (The 2D Computational Geometry Engine)
- **What it is:** A Python library for manipulation and analysis of planar geometric objects. Under the hood, it uses the C++ library GEOS (the same engine powering PostGIS and QGIS).
- **Core Primitives:**
  - `Point(x, y)`: A single vertex (e.g. tree location, survey marker, lamp post).
  - `LineString([(x1, y1), (x2, y2), ...])`: Connected line segments (e.g. road centerline, setback boundary, property wall).
  - `Polygon([(x1, y1), ...], interiors=[...])`: An enclosed 2D area, optionally with cut-outs/holes (e.g. building footprint, courtyard, plot boundary).
  - `MultiPolygon`, `MultiLineString`: Collections of geometries treated as a single entity.
- **Key Architectural Operations:**
  - `.area`: Compute exact floor or plot area in square meters.
  - `.length`: Perimeter of plots or road lengths.
  - `.buffer(distance)`: Create uniform offsets (e.g., municipal road setbacks, fire buffer zones). Positive values expand outward; negative values shrink inward.
  - `.intersection(other)`: Find overlapping areas (e.g., clipping buildings to the site boundary).
  - `.difference(other)`: Subtract one shape from another (e.g., carving courtyards out of building footprints).
  - `.union(other)`: Merge adjacent plots or building wings into one continuous shape.
  - `.centroid` / `.representative_point()`: Find the center for placing room or building height labels.

### B. PyProj (Cartographic Coordinate Transformations)
- **What it is:** Python interface to PROJ, the international standard for cartographic projections and coordinate transformations.
- **Why Architects Need It:**
  - Earth is a spheroid. GPS and OpenStreetMap use **WGS84 (EPSG:4326)**, where coordinates are in degrees:
    - Ahmedabad: `Latitude: ~23.049 deg N, Longitude: ~72.526 deg E`
    - One degree of latitude is ~111 km, but one degree of longitude shrinks depending on distance from the equator. You cannot draft or calculate areas in degrees!
  - CAD and Archicad require a flat Cartesian grid in **Meters (UTM)**:
    - Ahmedabad sits in **UTM Zone 43N (EPSG:32643)**.
    - Here, coordinates are true metric measurements: `X = 246,566.31 m, Y = 2,551,105.44 m`.
- **The Archicad Far-Coordinates Glitch (Crucial Studio Knowledge):**
  - If you import coordinates like `(246566.31, 2551105.44)` straight into Archicad, graphics card precision degrades because 32-bit floating point numbers struggle with numbers millions of units away from `(0, 0)`.
  - Result: Zooming stutters, lines flicker, and 3D orbit breaks.
  - **The Solution:** We subtract the site center coordinates so your project center sits at `(0, 0, 0)` in Archicad, and store the UTM offset in `origin.json` for Archicad's **Survey Point** settings.

### C. GeoPandas (Tabular Spatial Data)
- **What it is:** Extends the popular `pandas` data science library by adding spatial data types (`geometry` column) to standard dataframes.
- **Why Architects Need It:**
  - A building footprint is not just a polygon; it has attributes:
    - `name`: "Sangath Studio"
    - `building`: "institutional"
    - `building:levels`: "2"
    - `height`: "7.5"
  - GeoPandas lets you filter, sort, and query urban data just like SQL or Excel:
    - "Select all residential buildings taller than 15 meters."
    - "Calculate the total built-up ground coverage percentage of this neighborhood."
    - "Export only primary and secondary roads to a DXF layer."
- **Common File Formats:**
  - **GeoJSON (`.geojson`)**: Human-readable JSON containing geometries and properties. Excellent for web and GIS.
  - **Shapefile (`.shp`)**: Traditional GIS format used in QGIS and ArcGIS.

### D. OSMnx (OpenStreetMap Urban Mining)
- **What it is:** A specialized package that downloads, models, analyzes, and visualizes street networks and urban spatial data directly from OpenStreetMap's Overpass API.
- **Key Capabilities:**
  - `ox.graph_from_point((lat, lon), dist=radius, network_type="all")`: Downloads topologically connected road networks (walkways, driveways, major roads).
  - `ox.features_from_point((lat, lon), tags={"building": True}, dist=radius)`: Extracts every tagged building footprint in the specified radius.
  - `ox.features_from_point((lat, lon), tags={"leisure": "park", "natural": "tree"}, dist=radius)`: Extracts green cover, water bodies, and civic amenities.

### E. ezdxf (CAD DXF Generation Engine)
- **What it is:** A fast, pure-Python library to read, modify, and write AutoCAD Drawing Exchange Format (DXF) files.
- **Why Archicad Accepts DXF:**
  - DXF is an open, universal standard. Archicad imports DXF files through `File > Interoperability > Merge`.
- **Key Concepts in ezdxf:**
  - **Header Variables:**
    - `$INSUNITS = 6`: Tells Archicad and AutoCAD that 1 drawing unit equals 1 Meter. Without this, Archicad may default to millimeters or inches, scaling your site 1,000 times too big or small.
  - **Layers & Colors:**
    - Layers keep the drawing clean. We use AutoCAD Color Index (ACI):
      - 1 = Red (Boundary)
      - 2 = Yellow (Text & labels)
      - 3 = Green (Landscaping)
      - 4 = Cyan (Buildings)
      - 5 = Blue (Water)
      - 7 = White/Black (Major roads)
      - 8 / 9 = Grays (Minor & pedestrian roads)
  - **Entities:**
    - `add_lwpolyline([(x1, y1), ...], close=True)`: 2D closed polygon (footprint).
    - `add_3dface([(x1,y1,z1), (x2,y2,z2), (x3,y3,z3), (x4,y4,z4)])`: 3D quad facet. Used to build extruded 3D building walls and roof caps that Archicad renders as solid 3D massings.
    - `add_text(text, dxfattribs={"height": 2.5})`: Text annotations.

---

## 3. How to Use the Learning Path

Follow the five hands-on labs in `learning_path/`:

1. [lab01_shapely_geometry.py](file:///d:/Arch/learning%20top%20be%20useful/learning_path/lab01_shapely_geometry.py): Master points, lines, polygons, buffers (setbacks), and boolean geometric operations.
2. [lab02_pyproj_coordinates.py](file:///d:/Arch/learning%20top%20be%20useful/learning_path/lab02_pyproj_coordinates.py): Convert lat/lon to UTM meters and understand why CAD models must be shifted to (0,0).
3. [lab03_geopandas_spatial_data.py](file:///d:/Arch/learning%20top%20be%20useful/learning_path/lab03_geopandas_spatial_data.py): Query building attributes, calculate site ground coverage, and estimate Floor Space Index (FSI).
4. [lab04_osmnx_urban_mining.py](file:///d:/Arch/learning%20top%20be%20useful/learning_path/lab04_osmnx_urban_mining.py): Query OpenStreetMap reliably with custom Overpass endpoints and parse urban features.
5. [lab05_ezdxf_cad_generation.py](file:///d:/Arch/learning%20top%20be%20useful/learning_path/lab05_ezdxf_cad_generation.py): Write clean 2D and 3D DXF files with layers, scale bars, and building extrusions ready for Archicad 29.

Run the interactive sandbox at any time:
```powershell
.venv\Scripts\python.exe learning_path\sandbox.py
```
