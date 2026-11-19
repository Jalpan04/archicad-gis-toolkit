"""
All-in-One CLI: GIS-to-Archicad Site Context Generator.

Usage example (Sangath, Thaltej, Ahmedabad):
  python run_site_generator.py --lat 23.04917 --lon 72.52667 --radius 400 --name Sangath_Thaltej

Usage example (any other project site in India):
  python run_site_generator.py --lat 23.0225 --lon 72.5714 --radius 500 --name Sabarmati_Riverfront
"""

from __future__ import annotations

import argparse
from pathlib import Path
import importlib.util


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Archicad-ready 2D DXF, 3D Massing DXF, and 3D Terrain XYZ.")
    parser.add_argument("--lat", type=float, default=23.04917, help="Site latitude (WGS84)")
    parser.add_argument("--lon", type=float, default=72.52667, help="Site longitude (WGS84)")
    parser.add_argument("--radius", type=int, default=400, help="Context radius in meters")
    parser.add_argument("--name", type=str, default="Sangath_Thaltej_Ahmedabad", help="Site name")
    parser.add_argument("--grid", type=int, default=11, help="Terrain elevation grid size (N x N)")
    parser.add_argument("--out", type=Path, default=None, help="Output folder (defaults to output/<name>)")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    out_dir = args.out if args.out else (base_dir / "output" / args.name)

    step1 = _load_module("step1", base_dir / "01_fetch_osm_data.py")
    step2 = _load_module("step2", base_dir / "02_export_archicad_dxf.py")
    step3 = _load_module("step3", base_dir / "03_fetch_terrain_xyz.py")

    print("=" * 68)
    print(f"GIS-to-Archicad Generator | Target: {args.name}")
    print("=" * 68)
    step1.fetch_site_context(args.lat, args.lon, args.radius, out_dir, args.name)
    print("-" * 68)
    step2.export_archicad_dxfs(out_dir)
    print("-" * 68)
    step3.export_terrain_xyz(out_dir, grid_size=args.grid)
    print("=" * 68)
    print(f"All Archicad assets ready in: {out_dir}")


if __name__ == "__main__":
    main()
