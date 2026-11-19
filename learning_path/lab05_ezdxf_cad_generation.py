"""
LAB 05: CAD Drafting & 3D Massing with ezdxf
=============================================
Architectural Goal:
  Learn how to generate structured AutoCAD/Archicad-compliant DXF drawings
  from Python, configure metric units ($INSUNITS), establish architectural
  layers, draw 2D plans, and extrude 3D building massings using 3DFACE.

How to Run:
  .venv\\Scripts\\python.exe learning_path\\lab05_ezdxf_cad_generation.py
"""

import ezdxf
from shapely.geometry import Polygon
from pathlib import Path


def section_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f" {title.upper()}")
    print("=" * 60)


# Standard Architectural Layer Palette (AutoCAD Color Index - ACI)
# 1 = Red, 2 = Yellow, 3 = Green, 4 = Cyan, 5 = Blue, 6 = Magenta, 7 = White, 8 = Gray
CAD_LAYERS = {
    "A-BNDY": {"color": 1, "desc": "Site Boundary & Setbacks"},
    "A-BLD2": {"color": 4, "desc": "2D Building Footprints"},
    "A-BLD3": {"color": 4, "desc": "3D Extruded Building Massing"},
    "A-TEXT": {"color": 2, "desc": "Room & Height Annotations"},
    "C-ROAD": {"color": 7, "desc": "Civil Road Networks"},
    "L-LAND": {"color": 3, "desc": "Landscape & Green Areas"},
}


def create_architectural_drawing() -> ezdxf.document.Drawing:
    """
    Initializes an AutoCAD R2010 DXF document configured for BIM:
    1. Sets measurement to Metric ($MEASUREMENT = 1).
    2. Sets drawing units to METERS ($INSUNITS = 6).
    3. Remaps default font to TrueType Arial.ttf (prevents Archicad missing txt.SHX dialog).
    4. Pre-loads studio layer names and colors.
    """
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6      # 6 = Meters (Crucial for Archicad!)
    doc.header["$MEASUREMENT"] = 1   # 1 = Metric

    if "Standard" in doc.styles:
        doc.styles.get("Standard").dxf.font = "Arial.ttf"

    for layer_name, info in CAD_LAYERS.items():
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=info["color"])

    return doc


def add_building_3d_extrusion(msp, footprint_coords: list[tuple[float, float]], height_m: float, layer: str) -> int:
    """
    Extrude a 2D polygon footprint into a 3D massing box using 3DFACE entities.
    Archicad 29 reads 3DFACE meshes natively into its 3D viewport or as Morph objects.
    """
    faces_added = 0
    n = len(footprint_coords)

    # 1. Vertical Quad Wall Faces
    for i in range(n):
        x1, y1 = footprint_coords[i]
        x2, y2 = footprint_coords[(i + 1) % n]
        # 4 vertices of the wall quad: (p1_bottom, p2_bottom, p2_top, p1_top)
        msp.add_3dface(
            [(x1, y1, 0.0), (x2, y2, 0.0), (x2, y2, height_m), (x1, y1, height_m)],
            dxfattribs={"layer": layer},
        )
        faces_added += 1

    # 2. Horizontal Roof Cap Face (for 4-sided rectangular footprints)
    if n == 4:
        p1, p2, p3, p4 = footprint_coords
        msp.add_3dface(
            [(p1[0], p1[1], height_m), (p2[0], p2[1], height_m), (p3[0], p3[1], height_m), (p4[0], p4[1], height_m)],
            dxfattribs={"layer": layer},
        )
        faces_added += 1
    elif n > 4:
        # Fan triangulation from center
        cx = sum(p[0] for p in footprint_coords) / n
        cy = sum(p[1] for p in footprint_coords) / n
        for i in range(n):
            x1, y1 = footprint_coords[i]
            x2, y2 = footprint_coords[(i + 1) % n]
            msp.add_3dface(
                [(x1, y1, height_m), (x2, y2, height_m), (cx, cy, height_m), (cx, cy, height_m)],
                dxfattribs={"layer": layer},
            )
            faces_added += 1

    return faces_added


def main() -> None:
    section_header("1. Initializing Metric DXF Document")

    doc = create_architectural_drawing()
    msp = doc.modelspace()
    print("Created R2010 DXF document with $INSUNITS = 6 (Meters).")
    print("Configured Studio Layers:")
    for lname, ldata in CAD_LAYERS.items():
        print(f"  - {lname:<8} (Color: {ldata['color']}): {ldata['desc']}")

    section_header("2. Drawing 2D Site Context & Annotation")

    # Site Boundary (60m x 40m)
    site_corners = [(0.0, 0.0), (60.0, 0.0), (60.0, 40.0), (0.0, 40.0)]
    msp.add_lwpolyline(site_corners, close=True, dxfattribs={"layer": "A-BNDY"})

    # Scale Bar (20m total)
    msp.add_lwpolyline([(5.0, -8.0), (25.0, -8.0)], dxfattribs={"layer": "A-TEXT"})
    msp.add_line((5.0, -9.0), (5.0, -7.0), dxfattribs={"layer": "A-TEXT"})
    msp.add_line((15.0, -9.0), (15.0, -7.0), dxfattribs={"layer": "A-TEXT"})
    msp.add_line((25.0, -9.0), (25.0, -7.0), dxfattribs={"layer": "A-TEXT"})
    msp.add_text("0m", dxfattribs={"layer": "A-TEXT", "height": 1.2}).set_placement((4.0, -11.0))
    msp.add_text("10m", dxfattribs={"layer": "A-TEXT", "height": 1.2}).set_placement((13.5, -11.0))
    msp.add_text("20m", dxfattribs={"layer": "A-TEXT", "height": 1.2}).set_placement((23.5, -11.0))

    # North Arrow
    nx, ny = 55.0, -8.0
    msp.add_line((nx, ny - 3.0), (nx, ny + 4.0), dxfattribs={"layer": "A-TEXT"})
    msp.add_lwpolyline([(nx - 1.2, ny + 2.0), (nx, ny + 4.0), (nx + 1.2, ny + 2.0)], dxfattribs={"layer": "A-TEXT"})
    msp.add_text("N", dxfattribs={"layer": "A-TEXT", "height": 2.0}).set_placement((nx - 0.7, ny + 5.0))

    section_header("3. Drawing 2D & 3D Building Massings")

    # Sample Building 1: Studio Pavilion (Height = 8.5m)
    bld1_pts = [(10.0, 10.0), (35.0, 10.0), (35.0, 25.0), (10.0, 25.0)]
    # Add 2D outline
    msp.add_lwpolyline(bld1_pts, close=True, dxfattribs={"layer": "A-BLD2"})
    msp.add_text("STUDIO PAVILION (+8.5m)", dxfattribs={"layer": "A-TEXT", "height": 1.5}).set_placement((12.0, 17.5))
    # Extrude 3D Massing
    faces_bld1 = add_building_3d_extrusion(msp, bld1_pts, height_m=8.5, layer="A-BLD3")

    # Sample Building 2: Administration Tower (Height = 16.0m)
    bld2_pts = [(40.0, 12.0), (52.0, 12.0), (52.0, 28.0), (40.0, 28.0)]
    msp.add_lwpolyline(bld2_pts, close=True, dxfattribs={"layer": "A-BLD2"})
    msp.add_text("TOWER (+16.0m)", dxfattribs={"layer": "A-TEXT", "height": 1.5}).set_placement((41.0, 20.0))
    faces_bld2 = add_building_3d_extrusion(msp, bld2_pts, height_m=16.0, layer="A-BLD3")

    print(f"Generated 2D and 3D geometry for Studio Pavilion ({faces_bld1} 3D faces).")
    print(f"Generated 2D and 3D geometry for Tower ({faces_bld2} 3D faces).")

    section_header("4. Exporting to DXF")

    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    dxf_path = out_dir / "lab05_sample_project.dxf"

    doc.saveas(dxf_path)
    print(f"Successfully wrote architectural DXF: {dxf_path}")
    print("\nHow to test in Archicad 29:")
    print("  1. In Archicad: File > Interoperability > Merge > Merge from File...")
    print(f"  2. Select '{dxf_path.name}'.")
    print("  3. Set Drawing Unit = 1 Meter, Insertion Point = (0, 0).")
    print("  4. Press F3 to view the 3D extruded masses in the 3D window!")
    print("\nDone! You now understand how to programmatically create Archicad-ready DXF drawings.")


if __name__ == "__main__":
    main()
