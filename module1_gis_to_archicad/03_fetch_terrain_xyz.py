"""
Lesson 3: Fetch Real Site Elevation Data and Export Archicad Surveyors Data (.xyz)
for 1-Click 3D Terrain Mesh Creation.

How Archicad 29 Uses This File:
  File > Interoperability > Place Mesh from Surveyors Data...
  Select `terrain_surveyors_relative.xyz` (units = Meters, Place at Project Origin).
  Archicad immediately generates a triangulated 3D editable Terrain Mesh aligned
  1:1 with `site_context_2d.dxf` and `site_context_3d_massing.dxf`!
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests
from pyproj import Transformer


OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"


def fetch_elevations_batched(lat_list: list[float], lon_list: list[float], batch_size: int = 80) -> list[float]:
    """Query Open-Meteo Elevation API (Copernicus DEM) in safe batches."""
    elevations: list[float] = []
    for start in range(0, len(lat_list), batch_size):
        lats = lat_list[start : start + batch_size]
        lons = lon_list[start : start + batch_size]
        params = {
            "latitude": ",".join(f"{v:.6f}" for v in lats),
            "longitude": ",".join(f"{v:.6f}" for v in lons),
        }
        resp = requests.get(OPEN_METEO_ELEVATION_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        elevations.extend(float(z) for z in data["elevation"])
        if start + batch_size < len(lat_list):
            time.sleep(0.2)
    return elevations


def export_terrain_xyz(data_dir: Path, grid_size: int = 11) -> None:
    """Sample a grid_size x grid_size elevation grid aligned to origin.json and write .xyz files."""
    meta = json.loads((data_dir / "origin.json").read_text(encoding="utf-8"))
    radius = float(meta["radius_m"])
    utm_epsg = int(meta["utm_epsg"])
    origin_x = float(meta["utm_origin_easting_m"])
    origin_y = float(meta["utm_origin_northing_m"])

    inv_transformer = Transformer.from_crs(f"EPSG:{utm_epsg}", "EPSG:4326", always_xy=True)

    # Build evenly spaced local grid from -radius to +radius
    step = (2.0 * radius) / (grid_size - 1)
    local_coords: list[tuple[float, float]] = []
    lats: list[float] = []
    lons: list[float] = []

    for iy in range(grid_size):
        ly = -radius + iy * step
        for ix in range(grid_size):
            lx = -radius + ix * step
            lon, lat = inv_transformer.transform(origin_x + lx, origin_y + ly)
            local_coords.append((lx, ly))
            lats.append(lat)
            lons.append(lon)

    print(f"Fetching elevation for {len(local_coords)} survey points ({grid_size}x{grid_size} grid)...")
    elevations = fetch_elevations_batched(lats, lons)

    # Elevation at the center point of the grid (for relative Z = 0.00 at Project Origin)
    center_idx = (grid_size // 2) * grid_size + (grid_size // 2)
    center_z = elevations[center_idx]
    min_z, max_z = min(elevations), max(elevations)

    rel_lines: list[str] = []
    amsl_lines: list[str] = []
    for (lx, ly), z in zip(local_coords, elevations):
        rel_lines.append(f"{lx:.3f} {ly:.3f} {z - center_z:.3f}")
        amsl_lines.append(f"{lx:.3f} {ly:.3f} {z:.3f}")

    rel_path = data_dir / "terrain_surveyors_relative.xyz"
    amsl_path = data_dir / "terrain_surveyors_amsl.xyz"
    rel_path.write_text("\n".join(rel_lines) + "\n", encoding="utf-8")
    amsl_path.write_text("\n".join(amsl_lines) + "\n", encoding="utf-8")

    print(f"Saved relative terrain (.xyz): {rel_path}")
    print(f"Saved AMSL terrain (.xyz):     {amsl_path}")
    print(f"Elevation stats: min={min_z:.2f} m, max={max_z:.2f} m, relief={max_z - min_z:.2f} m, center={center_z:.2f} m AMSL")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Archicad Surveyors Data (.xyz) terrain mesh.")
    parser.add_argument("--data-dir", type=Path, default=Path("output"), help="Directory containing origin.json")
    parser.add_argument("--grid", type=int, default=11, help="Grid resolution per side (e.g., 11 = 121 points)")
    args = parser.parse_args()
    export_terrain_xyz(args.data_dir, args.grid)


if __name__ == "__main__":
    main()
