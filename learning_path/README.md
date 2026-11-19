# Spatial Computing & CAD Automation: Step-by-Step Learning Path

This folder provides a guided curriculum designed to take you from core geometric principles to Archicad 29 automation.

---

## Curriculum Structure

| Lab | Script | Core Library | Architectural Concept Learned |
|---|---|---|---|
| **01** | [lab01_shapely_geometry.py](file:///d:/Arch/learning%20top%20be%20useful/learning_path/lab01_shapely_geometry.py) | `shapely` | Points, lines, polygons, plot setbacks (`buffer`), courtyards, road widening (`intersection` / `difference`). |
| **02** | [lab02_pyproj_coordinates.py](file:///d:/Arch/learning%20top%20be%20useful/learning_path/lab02_pyproj_coordinates.py) | `pyproj` | WGS84 degrees vs UTM meters, calculating UTM zones in India, solving the Archicad 3D viewport jitter glitch via local origin shifts. |
| **03** | [lab03_geopandas_spatial_data.py](file:///d:/Arch/learning%20top%20be%20useful/learning_path/lab03_geopandas_spatial_data.py) | `geopandas` | Spatial dataframes, querying building types, computing Masterplan Ground Coverage % and Floor Space Index (FSI/FAR). |
| **04** | [lab04_osmnx_urban_mining.py](file:///d:/Arch/learning%20top%20be%20useful/learning_path/lab04_osmnx_urban_mining.py) | `osmnx` | Querying real-world street networks and building footprints from OpenStreetMap, configuring Overpass API polite requests. |
| **05** | [lab05_ezdxf_cad_generation.py](file:///d:/Arch/learning%20top%20be%20useful/learning_path/lab05_ezdxf_cad_generation.py) | `ezdxf` | Setting metric units (`$INSUNITS = 6`), managing architectural layers/colors, writing 2D plans and 3D extruded masses (`3DFACE`) for Archicad. |

---

## Master Reference Guide

For deep technical explanations of how each library works and why architects use them, read:
- [DOCS_GIS_AND_CAD_LIBRARIES.md](file:///d:/Arch/learning%20top%20be%20useful/learning_path/DOCS_GIS_AND_CAD_LIBRARIES.md)

---

## Interactive Sandbox

You can launch the interactive testing sandbox anytime:

```powershell
.venv\Scripts\python.exe learning_path\sandbox.py
```

The sandbox lets you:
1. Enter custom plot widths, depths, and municipal setbacks to calculate buildable areas.
2. Select Indian architectural presets (Sangath, CEPT, Louis Kahn's IIM Ahmedabad, Sabarmati Riverfront, New Delhi, Mumbai) to see their exact UTM zones and Archicad Survey Point numbers.
3. Calculate ground coverage and FSI for any custom campus schedule.
4. Generate a custom 3D extruded `.dxf` building massing on demand to test directly in Archicad 29.
