"""
LAB 03: Tabular Spatial Data & BIM Metrics with GeoPandas
==========================================================
Architectural Goal:
  Learn how to structure urban and building datasets into GeoDataFrames,
  calculate municipal metrics like Ground Coverage % and Floor Space Index
  (FSI / FAR), and export clean GeoJSON layers.

How to Run:
  .venv\\Scripts\\python.exe learning_path\\lab03_geopandas_spatial_data.py
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, Point
import matplotlib.pyplot as plt
from pathlib import Path


def section_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f" {title.upper()}")
    print("=" * 60)


def main() -> None:
    section_header("1. What is a GeoDataFrame?")

    # A GeoDataFrame is a Pandas DataFrame with a special 'geometry' column.
    # Let's create an urban site sample containing 4 buildings inside a masterplan.
    records = [
        {
            "name": "Design Studio Block",
            "type": "institutional",
            "levels": 2,
            "height_m": 7.5,
            "geometry": Polygon([(10, 10), (45, 10), (45, 30), (10, 30)]),
        },
        {
            "name": "Library & Archives",
            "type": "institutional",
            "levels": 3,
            "height_m": 11.0,
            "geometry": Polygon([(55, 10), (80, 10), (80, 35), (55, 35)]),
        },
        {
            "name": "Student Hostel Tower A",
            "type": "residential",
            "levels": 7,
            "height_m": 22.4,
            "geometry": Polygon([(10, 45), (35, 45), (35, 70), (10, 70)]),
        },
        {
            "name": "Cafeteria & Amphitheater",
            "type": "commercial",
            "levels": 1,
            "height_m": 4.5,
            "geometry": Polygon([(45, 50), (85, 50), (85, 75), (45, 75)]),
        },
    ]

    # Overall site boundary (100m x 90m plot)
    plot_polygon = Polygon([(0, 0), (100, 0), (100, 90), (0, 90)])
    site_area_sqm = plot_polygon.area

    # Create GeoDataFrame in local metric CRS (EPSG:32643 - Ahmedabad UTM)
    gdf = gpd.GeoDataFrame(records, crs="EPSG:32643")
    print(gdf[["name", "type", "levels", "height_m"]])

    section_header("2. Computing Architectural & Urban Metrics")

    # A. Footprint Area of each building in square meters
    gdf["footprint_sqm"] = gdf.geometry.area

    # B. Total Built-up Area = footprint * number of levels
    gdf["total_builtup_sqm"] = gdf["footprint_sqm"] * gdf["levels"]

    print("\nCalculated Areas:")
    for _, row in gdf.iterrows():
        print(f"  - {row['name']} ({row['type']}):")
        print(f"      Footprint: {row['footprint_sqm']:.1f} sq.m | Built-up ({row['levels']} floors): {row['total_builtup_sqm']:.1f} sq.m")

    # C. Masterplan Summary Metrics (Standard Indian GDCR terminology)
    total_footprint = gdf["footprint_sqm"].sum()
    total_builtup = gdf["total_builtup_sqm"].sum()
    ground_coverage_pct = (total_footprint / site_area_sqm) * 100.0
    fsi = total_builtup / site_area_sqm  # Floor Space Index (also called FAR)

    print("\n--- MASTERPLAN METRICS ---")
    print(f"Total Site Area:         {site_area_sqm:.1f} sq.m (~{site_area_sqm / 10000:.2f} hectares)")
    print(f"Total Ground Coverage:   {total_footprint:.1f} sq.m ({ground_coverage_pct:.2f}% of site)")
    print(f"Total Gross Floor Area:  {total_builtup:.1f} sq.m")
    print(f"Floor Space Index (FSI): {fsi:.2f}")

    section_header("3. Filtering and Spatial Queries")

    # Query 1: Find high-rise buildings (levels > 4)
    high_rise = gdf[gdf["levels"] > 4]
    print(f"Buildings with >4 levels: {list(high_rise['name'])}")

    # Query 2: Aggregate built-up area by building use type
    grouped = gdf.groupby("type")["total_builtup_sqm"].sum()
    print("\nBuilt-up Area by Type:")
    print(grouped)

    section_header("4. Exporting to GeoJSON")

    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = out_dir / "lab03_sample_campus.geojson"

    gdf.to_file(geojson_path, driver="GeoJSON")
    print(f"Saved GeoJSON dataset to: {geojson_path}")

    section_header("5. Visualizing the Dataset with Matplotlib")

    fig, ax = plt.subplots(figsize=(9, 8), dpi=150)
    ax.set_facecolor("#F9F8F5")

    # Draw site boundary
    px, py = plot_polygon.exterior.xy
    ax.plot(px, py, color="#C0392B", linewidth=2.0, linestyle="--", label=f"Site Boundary ({site_area_sqm:.0f} sqm)")

    # Color code by usage type
    color_map = {
        "institutional": "#3498DB",
        "residential": "#E67E22",
        "commercial": "#2ECC71",
    }

    for btype, group in gdf.groupby("type"):
        group.plot(
            ax=ax,
            color=color_map.get(btype, "#95A5A6"),
            edgecolor="#2C3E50",
            linewidth=1.2,
            label=f"{btype.capitalize()} ({len(group)})",
        )

    # Add text labels on building centroids
    for _, row in gdf.iterrows():
        c = row.geometry.centroid
        ax.text(
            c.x, c.y,
            f"{row['name']}\n{row['levels']} Fl ({row['height_m']}m)\n{row['footprint_sqm']:.0f} m2",
            ha="center", va="center",
            fontsize=8, fontweight="bold", color="#1C2833",
        )

    ax.set_title(
        f"Campus Site Plan: Ground Coverage = {ground_coverage_pct:.1f}% | FSI = {fsi:.2f}",
        fontsize=11, fontweight="bold",
    )
    ax.set_xlabel("Local Metric X (meters)")
    ax.set_ylabel("Local Metric Y (meters)")
    ax.set_aspect("equal")
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend(loc="upper right", fontsize=9)

    out_png = out_dir / "lab03_campus_plan.png"
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close(fig)

    print(f"Saved plan diagram to: {out_png}")
    print("Done! You now understand GeoDataFrames, spatial metrics, and GeoJSON export.")


if __name__ == "__main__":
    main()
