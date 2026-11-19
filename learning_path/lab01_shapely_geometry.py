"""
LAB 01: Computational 2D Geometry with Shapely
================================================
Architectural Goal:
  Learn how to model plots, roads, setbacks, courtyards, and buildable
  envelopes using Shapely geometry primitives and boolean operations.

How to Run:
  .venv\\Scripts\\python.exe learning_path\\lab01_shapely_geometry.py
"""

from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from shapely.ops import unary_union
import matplotlib.pyplot as plt
from pathlib import Path


def section_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f" {title.upper()}")
    print("=" * 60)


def main() -> None:
    section_header("1. Core Geometry Primitives")

    # Point: survey marker or tree location
    survey_origin = Point(0.0, 0.0)
    tree_loc = Point(12.5, 8.0)
    print(f"Point (Survey Origin): {survey_origin}")
    print(f"Distance between origin and tree: {survey_origin.distance(tree_loc):.2f} meters")

    # LineString: road centerline or property wall
    road_centerline = LineString([(-30, 0), (0, 0), (30, 10), (50, 25)])
    print(f"\nLineString (Road Centerline): {road_centerline}")
    print(f"Total road centerline length: {road_centerline.length:.2f} meters")

    # Polygon: A typical 40m x 25m architectural plot
    # Coordinates in counter-clockwise order: (x, y) in meters
    plot_coords = [(0, 0), (40, 0), (40, 25), (0, 25)]
    plot_poly = Polygon(plot_coords)
    print(f"\nPolygon (Plot Boundary): {plot_poly}")
    print(f"Plot Area:      {plot_poly.area:.2f} sq.m")
    print(f"Plot Perimeter: {plot_poly.length:.2f} meters")
    print(f"Plot Centroid:  {plot_poly.centroid.x:.2f}, {plot_poly.centroid.y:.2f}")

    section_header("2. Buffers: Modeling Setbacks and Road Widths")

    # In municipal planning (like Ahmedabad GDCR), buildings cannot touch plot edges.
    # Front/Rear/Side setbacks restrict where you can build.
    # An inward buffer (negative distance) calculates the allowable building footprint!
    setback_distance = 3.0  # 3 meters municipal setback
    buildable_envelope = plot_poly.buffer(-setback_distance)
    print(f"Original Plot Area:      {plot_poly.area:.2f} sq.m")
    print(f"Buildable Envelope Area: {buildable_envelope.area:.2f} sq.m (after {setback_distance}m setback)")
    print(f"Permissible Ground Footprint: {(buildable_envelope.area / plot_poly.area) * 100:.1f}%")

    # An outward buffer on a line creates a 2D road corridor from a 1D centerline
    road_width = 12.0  # 12 meter wide road right-of-way
    road_corridor = road_centerline.buffer(road_width / 2.0, cap_style="flat")
    print(f"\nRoad Corridor Area (12m wide): {road_corridor.area:.2f} sq.m")

    section_header("3. Boolean Operations: Courtyards and Subtractions")

    # Sangath Studio famously uses sunken courtyards and amphitheaters.
    # Let's create an L-shaped building with an interior open-air courtyard.
    building_outer = Polygon([(5, 5), (35, 5), (35, 20), (20, 20), (20, 15), (5, 15)])
    courtyard = Polygon([(10, 8), (18, 8), (18, 12), (10, 12)])

    # Difference: Subtract courtyard from outer building shell
    building_with_courtyard = building_outer.difference(courtyard)
    print(f"Building Outer Footprint: {building_outer.area:.2f} sq.m")
    print(f"Courtyard Cutout:         {courtyard.area:.2f} sq.m")
    print(f"Net Built-up Ground Area: {building_with_courtyard.area:.2f} sq.m")

    section_header("4. Intersections: Site Boundary Clipping")

    # Suppose a proposed road corridor cuts across the corner of our plot
    road_cut_line = LineString([(-10, -5), (50, 10)])
    road_cut_zone = road_cut_line.buffer(5.0)

    # What part of the plot is lost to road widening?
    plot_lost_to_road = plot_poly.intersection(road_cut_zone)
    # Remaining net plot
    net_plot = plot_poly.difference(road_cut_zone)
    print(f"Plot Area Lost to Road Widening: {plot_lost_to_road.area:.2f} sq.m")
    print(f"Net Usable Plot Area:            {net_plot.area:.2f} sq.m")

    section_header("5. Visualizing Geometric Operations")

    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_plot = out_dir / "lab01_shapely_diagram.png"

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), dpi=150)

    # Subplot 1: Setbacks & Buildable Envelope
    ax1 = axes[0]
    ax1.set_facecolor("#FAF9F6")
    px, py = plot_poly.exterior.xy
    ax1.plot(px, py, color="#C0392B", linewidth=2.5, label="Plot Boundary (40x25m)")
    ax1.fill(px, py, color="#C0392B", alpha=0.08)

    bx, by = buildable_envelope.exterior.xy
    ax1.plot(bx, by, color="#2980B9", linewidth=2.0, linestyle="--", label="3m Setback Envelope")
    ax1.fill(bx, by, color="#2980B9", alpha=0.25)
    ax1.plot(plot_poly.centroid.x, plot_poly.centroid.y, marker="+", color="#333333", markersize=10, label="Centroid")

    ax1.set_title("Plot Setbacks (Shapely Buffer)", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Meters")
    ax1.set_ylabel("Meters")
    ax1.set_aspect("equal")
    ax1.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(loc="upper right", fontsize=9)

    # Subplot 2: Building Footprint with Courtyard
    ax2 = axes[1]
    ax2.set_facecolor("#FAF9F6")
    ox, oy = building_outer.exterior.xy
    ax2.plot(ox, oy, color="#2C3E50", linewidth=2.0, label="Building Shell")
    ax2.fill(ox, oy, color="#7F8C8D", alpha=0.3)

    cx, cy = courtyard.exterior.xy
    ax2.plot(cx, cy, color="#27AE60", linewidth=2.0, linestyle="-.", label="Open Courtyard")
    ax2.fill(cx, cy, color="#FAF9F6", alpha=1.0)  # cutout white

    ax2.set_title("Footprint with Courtyard (Shapely Difference)", fontsize=11, fontweight="bold")
    ax2.set_xlabel("Meters")
    ax2.set_ylabel("Meters")
    ax2.set_aspect("equal")
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(loc="upper right", fontsize=9)

    plt.tight_layout()
    plt.savefig(out_plot)
    plt.close(fig)

    print(f"\nSaved diagram to: {out_plot}")
    print("Done! You now understand Shapely Point, LineString, Polygon, Buffer, and Boolean ops.")


if __name__ == "__main__":
    main()
