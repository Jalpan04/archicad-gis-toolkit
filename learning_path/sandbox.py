"""
INTERACTIVE ARCHITECTURAL GIS & CAD SANDBOX
=============================================
A hands-on testing sandbox to experiment with:
  1. Shapely   (Plot dimensions, setbacks, buildable footprint calculations)
  2. PyProj    (Indian city coordinates, UTM zones, Archicad Survey Point)
  3. GeoPandas (BIM site metrics: Ground Coverage %, Gross Floor Area, FSI/FAR)
  4. ezdxf     (Export custom 2D & 3D DXF models to test directly in Archicad 29)
  5. Run All Lab Verifications

How to Run:
  .venv\\Scripts\\python.exe learning_path\\sandbox.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ezdxf
import geopandas as gpd
from pyproj import CRS, Transformer
from shapely.geometry import Polygon, box
import matplotlib.pyplot as plt


OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "sandbox_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


CITY_PRESETS = {
    "1": ("Sangath Studio (Ahmedabad)", 23.04917, 72.52667),
    "2": ("CEPT University (Ahmedabad)", 23.03750, 72.54889),
    "3": ("IIM Ahmedabad (Louis Kahn)", 23.03194, 72.53167),
    "4": ("Sabarmati Riverfront", 23.02250, 72.57140),
    "5": ("Connaught Place (New Delhi)", 28.63150, 77.21670),
    "6": ("Bandra Kurla Complex (Mumbai)", 19.06570, 72.86860),
}


def print_banner(title: str) -> None:
    print("\n" + "=" * 65)
    print(f"  {title.upper()}")
    print("=" * 65)


def mode_shapely_setbacks(width: float = 30.0, depth: float = 40.0, setback: float = 3.0) -> None:
    print_banner("Shapely Sandbox: Plot Setback & Buildable Envelope")
    print(f"Inputs: Plot Width = {width}m, Plot Depth = {depth}m, Setback = {setback}m")

    # Create rectangular plot
    plot_poly = box(0.0, 0.0, width, depth)
    plot_area = plot_poly.area

    # Negative buffer calculates the internal buildable area
    buildable_poly = plot_poly.buffer(-setback)
    buildable_area = buildable_poly.area if not buildable_poly.is_empty else 0.0
    coverage_pct = (buildable_area / plot_area) * 100.0 if plot_area > 0 else 0.0

    print(f"\nResults:")
    print(f"  - Total Plot Area:         {plot_area:.2f} sq.m")
    print(f"  - Buildable Envelope Area: {buildable_area:.2f} sq.m")
    print(f"  - Permissible Coverage:    {coverage_pct:.2f}%")
    print(f"  - Land Lost to Setbacks:   {plot_area - buildable_area:.2f} sq.m")

    # Generate visual diagram
    fig, ax = plt.subplots(figsize=(6, 7), dpi=150)
    ax.set_facecolor("#F9F8F5")
    px, py = plot_poly.exterior.xy
    ax.plot(px, py, color="#C0392B", linewidth=2.0, label="Plot Boundary")
    ax.fill(px, py, color="#C0392B", alpha=0.1)

    if not buildable_poly.is_empty:
        bx, by = buildable_poly.exterior.xy
        ax.plot(bx, by, color="#2980B9", linewidth=2.0, linestyle="--", label=f"Buildable ({setback}m setback)")
        ax.fill(bx, by, color="#2980B9", alpha=0.3)

    ax.set_title(f"Plot: {width}m x {depth}m | Buildable: {coverage_pct:.1f}%", fontweight="bold", fontsize=10)
    ax.set_xlabel("Meters")
    ax.set_ylabel("Meters")
    ax.set_aspect("equal")
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend(loc="upper right", fontsize=8)

    out_file = OUTPUT_DIR / f"setback_{int(width)}x{int(depth)}_s{int(setback)}.png"
    plt.tight_layout()
    plt.savefig(out_file)
    plt.close(fig)
    print(f"  - Diagram saved: {out_file}")


def mode_pyproj_coordinates(lat: float = 23.04917, lon: float = 72.52667) -> None:
    print_banner("PyProj Sandbox: WGS84 -> UTM & Archicad Survey Point")
    print(f"GPS Input: Latitude = {lat:.5f} N, Longitude = {lon:.5f} E")

    zone = int((lon + 180.0) // 6.0) + 1
    utm_epsg = (32600 if lat >= 0 else 32700) + zone
    crs = CRS.from_epsg(utm_epsg)

    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{utm_epsg}", always_xy=True)
    easting_m, northing_m = transformer.transform(lon, lat)

    print(f"\nCalculated Cartographic Parameters:")
    print(f"  - Detected UTM Zone:    UTM {zone}N")
    print(f"  - Standard EPSG Code:   EPSG:{utm_epsg}")
    print(f"  - CRS Name:             {crs.name}")
    print(f"  - Projected Coordinates:")
    print(f"      Easting  (X): {easting_m:.3f} meters")
    print(f"      Northing (Y): {northing_m:.3f} meters")

    print("\nArchicad 29 Studio Configuration:")
    print("  1. Keep model geometry centered at Project Origin (0, 0, 0).")
    print("  2. In Archicad: Options > Project Preferences > Location Settings.")
    print(f"  3. Set Survey Point Easting  = {easting_m:.3f} m")
    print(f"  4. Set Survey Point Northing = {northing_m:.3f} m")
    print("  5. Result: Clean 3D viewport without graphics jitter + exact GIS alignment.")


def mode_geopandas_bim(plot_area: float = 2500.0) -> None:
    print_banner("GeoPandas Sandbox: Masterplan Ground Coverage & FSI")

    buildings = [
        {"name": "Studio A", "footprint_sqm": 450.0, "floors": 2, "type": "institutional"},
        {"name": "Workshop Block", "footprint_sqm": 320.0, "floors": 1, "type": "institutional"},
        {"name": "Faculty Residence", "footprint_sqm": 280.0, "floors": 4, "type": "residential"},
    ]

    total_footprint = sum(b["footprint_sqm"] for b in buildings)
    total_builtup = sum(b["footprint_sqm"] * b["floors"] for b in buildings)
    ground_coverage_pct = (total_footprint / plot_area) * 100.0
    fsi = total_builtup / plot_area

    print(f"Site Plot Area: {plot_area:.1f} sq.m")
    print("\nBuilding Schedule:")
    for b in buildings:
        gfa = b["footprint_sqm"] * b["floors"]
        print(f"  - {b['name']:<18}: Footprint {b['footprint_sqm']:.0f} sqm | {b['floors']} floors | Built-up {gfa:.0f} sqm")

    print("\nUrban Planning Summary (GDCR Check):")
    print(f"  - Total Footprint:       {total_footprint:.1f} sq.m")
    print(f"  - Ground Coverage:       {ground_coverage_pct:.2f}% (Permissible max typically 40-50%)")
    print(f"  - Total Built-Up Area:   {total_builtup:.1f} sq.m")
    print(f"  - Floor Space Index FSI: {fsi:.2f}")


def mode_ezdxf_generator(bld_width: float = 20.0, bld_depth: float = 15.0, bld_height: float = 9.0) -> None:
    print_banner("ezdxf Sandbox: Export 2D + 3D DXF for Archicad 29")

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6      # 6 = Meters
    doc.header["$MEASUREMENT"] = 1   # Metric
    if "Standard" in doc.styles:
        doc.styles.get("Standard").dxf.font = "Arial.ttf"

    doc.layers.add("A-SITE", color=1)    # Red
    doc.layers.add("A-BLD-2D", color=4)  # Cyan
    doc.layers.add("A-BLD-3D", color=4)  # Cyan
    doc.layers.add("A-TEXT", color=2)    # Yellow

    msp = doc.modelspace()

    # 1. Site boundary
    site_w, site_d = bld_width + 20.0, bld_depth + 20.0
    msp.add_lwpolyline([(0, 0), (site_w, 0), (site_w, site_d), (0, site_d)], close=True, dxfattribs={"layer": "A-SITE"})

    # 2. Building placement (centered with 10m margin)
    x1, y1 = 10.0, 10.0
    x2, y2 = x1 + bld_width, y1 + bld_depth
    bld_pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    # 2D Polyline
    msp.add_lwpolyline(bld_pts, close=True, dxfattribs={"layer": "A-BLD-2D"})
    msp.add_text(
        f"TEST MASSING (+{bld_height}m)",
        dxfattribs={"layer": "A-TEXT", "height": 1.2},
    ).set_placement((x1 + 1.0, y1 + bld_depth / 2.0))

    # 3D Extrusion using 3DFACE
    # 4 vertical walls
    for i in range(4):
        p1 = bld_pts[i]
        p2 = bld_pts[(i + 1) % 4]
        msp.add_3dface(
            [(p1[0], p1[1], 0.0), (p2[0], p2[1], 0.0), (p2[0], p2[1], bld_height), (p1[0], p1[1], bld_height)],
            dxfattribs={"layer": "A-BLD-3D"},
        )
    # Roof cap
    msp.add_3dface(
        [(x1, y1, bld_height), (x2, y1, bld_height), (x2, y2, bld_height), (x1, y2, bld_height)],
        dxfattribs={"layer": "A-BLD-3D"},
    )

    out_dxf = OUTPUT_DIR / f"test_massing_{int(bld_width)}x{int(bld_depth)}x{int(bld_height)}m.dxf"
    doc.saveas(out_dxf)

    print(f"Generated 2D outline and 5-face 3D solid massing.")
    print(f"Saved Archicad-ready DXF to: {out_dxf}")
    print("\nQuick Test in Archicad 29:")
    print("  File > Interoperability > Merge > select this file > Drawing unit = 1m > Press F3!")


def run_interactive_menu() -> None:
    while True:
        print_banner("Architectural GIS & CAD Interactive Sandbox")
        print("Select an exercise to run:")
        print("  [1] Shapely:   Test custom plot dimensions and setbacks")
        print("  [2] PyProj:    Test Indian city coordinate projections (UTM)")
        print("  [3] GeoPandas: Test BIM site metrics & FSI calculations")
        print("  [4] ezdxf:     Generate a custom 2D & 3D DXF file for Archicad")
        print("  [5] Exit Sandbox")

        choice = input("\nEnter choice [1-5]: ").strip()

        if choice == "1":
            try:
                w_str = input("Enter plot width in meters (default 30): ").strip()
                w = float(w_str) if w_str else 30.0
                d_str = input("Enter plot depth in meters (default 40): ").strip()
                d = float(d_str) if d_str else 40.0
                s_str = input("Enter setback distance in meters (default 3): ").strip()
                s = float(s_str) if s_str else 3.0
                mode_shapely_setbacks(w, d, s)
            except ValueError:
                print("Invalid number. Using defaults.")
                mode_shapely_setbacks()
        elif choice == "2":
            print("\nSelect a preset location:")
            for k, (name, _, _) in CITY_PRESETS.items():
                print(f"  [{k}] {name}")
            print("  [C] Custom Latitude & Longitude")
            c_choice = input("Select [1-6 or C]: ").strip().upper()
            if c_choice in CITY_PRESETS:
                _, lat, lon = CITY_PRESETS[c_choice]
                mode_pyproj_coordinates(lat, lon)
            elif c_choice == "C":
                try:
                    lat = float(input("Enter Latitude (e.g. 23.04917): ").strip())
                    lon = float(input("Enter Longitude (e.g. 72.52667): ").strip())
                    mode_pyproj_coordinates(lat, lon)
                except ValueError:
                    print("Invalid input.")
            else:
                mode_pyproj_coordinates()
        elif choice == "3":
            try:
                area_str = input("Enter total plot area in sq.m (default 2500): ").strip()
                area = float(area_str) if area_str else 2500.0
                mode_geopandas_bim(area)
            except ValueError:
                mode_geopandas_bim()
        elif choice == "4":
            try:
                w_str = input("Enter building width in meters (default 20): ").strip()
                w = float(w_str) if w_str else 20.0
                d_str = input("Enter building depth in meters (default 15): ").strip()
                d = float(d_str) if d_str else 15.0
                h_str = input("Enter building height in meters (default 9): ").strip()
                h = float(h_str) if h_str else 9.0
                mode_ezdxf_generator(w, d, h)
            except ValueError:
                mode_ezdxf_generator()
        elif choice == "5":
            print("\nExiting sandbox. Happy coding!")
            break
        else:
            print("Invalid choice. Try again.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Architectural GIS & CAD Automation Sandbox")
    parser.add_argument("--test-all", action="store_true", help="Run automated non-interactive checks across all tools")
    args = parser.parse_args()

    if args.test_all or not sys.stdin.isatty():
        print_banner("Running Automated Sandbox Verification")
        mode_shapely_setbacks(30.0, 40.0, 3.0)
        mode_pyproj_coordinates(23.04917, 72.52667)
        mode_geopandas_bim(2500.0)
        mode_ezdxf_generator(24.0, 16.0, 10.5)
        print("\nAll automated sandbox checks completed successfully!")
    else:
        run_interactive_menu()


if __name__ == "__main__":
    main()
