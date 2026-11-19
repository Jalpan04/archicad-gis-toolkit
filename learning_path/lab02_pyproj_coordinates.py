"""
LAB 02: Coordinate Systems & Projections with PyProj
=====================================================
Architectural Goal:
  Understand why GPS lat/lon degrees break in CAD, how to project to
  metric UTM coordinates, and how to compute the Archicad Project Origin
  and Survey Point offsets cleanly.

How to Run:
  .venv\\Scripts\\python.exe learning_path\\lab02_pyproj_coordinates.py
"""

from pyproj import CRS, Transformer
import math
from pathlib import Path


def section_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f" {title.upper()}")
    print("=" * 60)


def calculate_utm_epsg(latitude: float, longitude: float) -> int:
    """
    Earth is divided into 60 UTM zones, each 6 degrees of longitude wide.
    Zone 1 starts at 180W.
    Northern hemisphere = EPSG:32600 + zone
    Southern hemisphere = EPSG:32700 + zone
    """
    zone = int((longitude + 180.0) // 6.0) + 1
    base = 32600 if latitude >= 0 else 32700
    return base + zone


def main() -> None:
    section_header("1. The Problem: Degrees vs. Meters")

    # Real Coordinates for Sangath Studio (Balkrishna Doshi, Thaltej, Ahmedabad)
    sangath_lat = 23.04917  # Degrees North
    sangath_lon = 72.52667  # Degrees East

    print(f"Sangath GPS Location: {sangath_lat:.5f} N, {sangath_lon:.5f} E")
    print("CRS: WGS84 (EPSG:4326) - Units are DEGREES.")
    print("Why CAD fails here: You cannot specify a 230mm brick wall in degrees!")

    section_header("2. Auto-Detecting the UTM Metric Zone")

    utm_epsg = calculate_utm_epsg(sangath_lat, sangath_lon)
    utm_crs = CRS.from_epsg(utm_epsg)

    print(f"Calculated UTM Code: EPSG:{utm_epsg}")
    print(f"CRS Name:            {utm_crs.name}")
    print(f"Axis Units:          {utm_crs.axis_info[0].unit_name} (True ground meters)")

    section_header("3. Projecting Degrees -> UTM Meters")

    # Transformer: EPSG:4326 (WGS84) -> EPSG:32643 (UTM Zone 43N)
    # always_xy=True ensures input and output follow (Longitude/X, Latitude/Y)
    transformer_to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{utm_epsg}", always_xy=True)

    easting_m, northing_m = transformer_to_utm.transform(sangath_lon, sangath_lat)
    print(f"WGS84 Lon, Lat:       {sangath_lon:.5f}, {sangath_lat:.5f}")
    print(f"UTM Easting (X):      {easting_m:.2f} meters")
    print(f"UTM Northing (Y):     {northing_m:.2f} meters")

    section_header("4. The Archicad Far-Coordinates Glitch")

    print("Notice the raw UTM coordinates: X = ~246,566 m, Y = ~2,551,105 m.")
    print("In 3D CAD engines (Archicad OpenGL/Metal, Rhino, Blender), single-precision")
    print("floating point numbers store ~7 significant digits.")
    print("If an object is located at 2,551,105.123 meters from origin, the millimeter")
    print("precision is lost to floating-point truncation, causing:")
    print("  - Jagged geometry and polygon clipping")
    print("  - Camera stuttering during 3D orbit and walk-throughs")
    print("  - Dimension rounding errors in construction drawings")

    section_header("5. The Professional BIM Solution: Local Origin Shift")

    # We shift the site center to (0, 0, 0) for the Archicad Project Origin!
    origin_easting = easting_m
    origin_northing = northing_m

    # A survey point 50 meters East and 30 meters North of Sangath entrance:
    test_pt_lon = sangath_lon + 0.000488
    test_pt_lat = sangath_lat + 0.000271
    test_easting, test_northing = transformer_to_utm.transform(test_pt_lon, test_pt_lat)

    local_x = test_easting - origin_easting
    local_y = test_northing - origin_northing

    print(f"Test Point UTM:   E = {test_easting:.2f} m, N = {test_northing:.2f} m")
    print(f"Archicad CAD (X): {local_x:.2f} m (centered around 0, 0)")
    print(f"Archicad CAD (Y): {local_y:.2f} m (centered around 0, 0)")
    print("\nArchicad Setup Guide:")
    print(f"  1. Model site geometry centered at (0, 0).")
    print(f"  2. In Archicad: Options > Project Preferences > Location Settings.")
    print(f"  3. Enter Survey Point coordinates: Easting = {origin_easting:.2f}, Northing = {origin_northing:.2f}.")
    print("  4. Result: Clean drafting at (0,0) + perfect IFC / GIS export alignment!")

    section_header("6. Inverse Transform: Local CAD Meters -> GPS Lat/Lon")

    transformer_to_wgs84 = Transformer.from_crs(f"EPSG:{utm_epsg}", "EPSG:4326", always_xy=True)
    restored_utm_x = local_x + origin_easting
    restored_utm_y = local_y + origin_northing
    restored_lon, restored_lat = transformer_to_wgs84.transform(restored_utm_x, restored_utm_y)

    print(f"Reconstructed Longitude: {restored_lon:.6f} (Original: {test_pt_lon:.6f})")
    print(f"Reconstructed Latitude:  {restored_lat:.6f} (Original: {test_pt_lat:.6f})")
    error_deg = math.hypot(restored_lon - test_pt_lon, restored_lat - test_pt_lat)
    print(f"Reconstruction Error:    {error_deg:.10f} degrees (< 0.001 mm error)")

    print("\nDone! You now understand WGS84, UTM projections, and Archicad origin shifts.")


if __name__ == "__main__":
    main()
