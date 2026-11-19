"""
Lesson 1: Fetch Real Urban Context from OpenStreetMap (OSM)
and Project It to Archicad-Safe Local Metric Coordinates.

Key Concepts for Architecture / BIM:
1. WGS84 (EPSG:4326) uses latitude/longitude degrees (not usable for CAD drafting).
2. UTM (e.g. EPSG:32643 for Ahmedabad) uses true meters on a flat grid.
3. Archicad (and Rhino/Revit) loses floating-point precision if geometry sits
   hundreds of kilometers from (0, 0). Shifting the site center to (0, 0) while
   recording the UTM offset for Archicad's Survey Point solves this cleanly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
from pyproj import Transformer
from shapely.affinity import translate
from shapely.geometry import Point


# Default site: Sangath Studio, Thaltej Road, Ahmedabad
DEFAULT_LAT = 23.04917
DEFAULT_LON = 72.52667
DEFAULT_RADIUS_M = 400


def get_utm_epsg(lat: float, lon: float) -> int:
    """Compute the standard WGS84 UTM EPSG code for any (lat, lon) on Earth."""
    zone = int((lon + 180.0) // 6.0) + 1
    return (32600 + zone) if lat >= 0 else (32700 + zone)


def shift_gdf_to_local(gdf: gpd.GeoDataFrame, origin_x: float, origin_y: float) -> gpd.GeoDataFrame:
    """Translate all geometries in a projected GeoDataFrame so site center = (0, 0)."""
    if gdf.empty:
        return gdf
    out = gdf.copy()
    out["geometry"] = out["geometry"].apply(
        lambda geom: translate(geom, xoff=-origin_x, yoff=-origin_y) if geom is not None else None
    )
    return out


def fetch_features_safe(
    lat: float,
    lon: float,
    tags: dict,
    dist: int,
    utm_epsg: int,
    origin_x: float,
    origin_y: float,
    geom_types: tuple[str, ...] = ("Polygon", "MultiPolygon"),
) -> gpd.GeoDataFrame:
    """Fetch OSM features by tag, project to UTM, shift to (0,0), and filter geometry types."""
    try:
        gdf = ox.features_from_point((lat, lon), tags=tags, dist=dist)
    except Exception:
        return gpd.GeoDataFrame(geometry=[], crs=f"EPSG:{utm_epsg}")

    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=f"EPSG:{utm_epsg}")

    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[gdf.geometry.geom_type.isin(geom_types)].copy()
    if gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=f"EPSG:{utm_epsg}")

    gdf = gdf.to_crs(epsg=utm_epsg)
    gdf = shift_gdf_to_local(gdf, origin_x, origin_y)

    # Clip cleanly to circular site boundary of radius `dist`
    boundary = Point(0.0, 0.0).buffer(dist)
    gdf["geometry"] = gdf.geometry.intersection(boundary)
    gdf = gdf[~gdf.geometry.is_empty].copy()
    return gdf


def keep_serializable_columns(gdf: gpd.GeoDataFrame, columns: list[str]) -> gpd.GeoDataFrame:
    """Retain only selected scalar columns + geometry so GeoJSON export never fails on list values."""
    out = gpd.GeoDataFrame(geometry=gdf.geometry, crs=gdf.crs)
    for col in columns:
        if col in gdf.columns:
            out[col] = gdf[col].apply(
                lambda v: str(v[0]) if isinstance(v, list) and v else ("" if v is None else str(v))
            )
    return out.reset_index(drop=True)


def render_preview(
    output_png: Path,
    radius: int,
    buildings: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    greens: gpd.GeoDataFrame,
    water: gpd.GeoDataFrame,
    site_name: str,
) -> None:
    """Generate a clean Nolli-style architectural figure-ground preview image."""
    fig, ax = plt.subplots(figsize=(10, 10), dpi=180)
    ax.set_facecolor("#F7F6F2")

    # Site boundary circle
    circle = plt.Circle((0, 0), radius, fill=False, edgecolor="#C0392B", linewidth=1.2, linestyle="--")
    ax.add_patch(circle)

    if not greens.empty:
        greens.plot(ax=ax, color="#B7D3B0", edgecolor="#89B080", linewidth=0.4, zorder=1)
    if not water.empty:
        water.plot(ax=ax, color="#A9CCE3", edgecolor="#5499C7", linewidth=0.6, zorder=2)
    if not roads.empty:
        roads.plot(ax=ax, color="#8C8C8C", linewidth=0.9, zorder=3)
    if not buildings.empty:
        buildings.plot(ax=ax, color="#2C2C2C", edgecolor="#1A1A1A", linewidth=0.25, zorder=4)

    # Site center crosshair (Archicad Project Origin 0,0)
    ax.plot(0, 0, marker="+", color="#C0392B", markersize=14, markeredgewidth=2, zorder=5)

    pad = radius * 1.08
    ax.set_xlim(-pad, pad)
    ax.set_ylim(-pad, pad)
    ax.set_aspect("equal")
    ax.set_xlabel("Local Easting X (meters from site origin)")
    ax.set_ylabel("Local Northing Y (meters from site origin)")
    ax.set_title(
        f"Architectural Figure-Ground Context: {site_name} (R = {radius} m)\n"
        f"Buildings: {len(buildings)} | Road Segments: {len(roads)} | Green Polygons: {len(greens)}",
        fontsize=11,
        fontweight="bold",
    )
    ax.grid(True, linestyle=":", alpha=0.35, color="#666666")
    plt.tight_layout()
    plt.savefig(output_png)
    plt.close(fig)


def fetch_site_context(lat: float, lon: float, radius: int, out_dir: Path, site_name: str) -> dict:
    """Run the full OSM fetch, UTM projection, local shift, and GeoJSON export."""
    out_dir.mkdir(parents=True, exist_ok=True)
    utm_epsg = get_utm_epsg(lat, lon)

    # Project center (lon, lat) -> UTM (origin_x, origin_y) in meters
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{utm_epsg}", always_xy=True)
    origin_x, origin_y = transformer.transform(lon, lat)

    print(f"[1/4] Site: {site_name} ({lat:.5f}, {lon:.5f}) | Radius: {radius} m")
    print(f"      Auto-selected CRS: EPSG:{utm_epsg} (UTM meters)")
    print(f"      UTM Survey Point Origin: E={origin_x:.2f} m, N={origin_y:.2f} m")

    # 1. Street network
    print("[2/4] Downloading street network from OpenStreetMap...")
    graph = ox.graph_from_point((lat, lon), dist=radius, network_type="all", simplify=True)
    edges = ox.graph_to_gdfs(graph, nodes=False, edges=True)
    edges = edges.to_crs(epsg=utm_epsg)
    edges = shift_gdf_to_local(edges, origin_x, origin_y)
    boundary = Point(0.0, 0.0).buffer(radius)
    edges["geometry"] = edges.geometry.intersection(boundary)
    edges = edges[~edges.geometry.is_empty].copy()
    roads = keep_serializable_columns(edges, ["highway", "name", "lanes", "oneway"])

    # 2. Building footprints
    print("[3/4] Downloading building footprints, green cover, and water bodies...")
    buildings_raw = fetch_features_safe(
        lat, lon, tags={"building": True}, dist=radius,
        utm_epsg=utm_epsg, origin_x=origin_x, origin_y=origin_y,
    )
    buildings = keep_serializable_columns(
        buildings_raw, ["building", "name", "height", "building:levels"]
    )

    greens_raw = fetch_features_safe(
        lat, lon,
        tags={"leisure": ["park", "garden", "playground"], "landuse": ["grass", "forest", "meadow"], "natural": ["wood", "scrub"]},
        dist=radius, utm_epsg=utm_epsg, origin_x=origin_x, origin_y=origin_y,
    )
    greens = keep_serializable_columns(greens_raw, ["leisure", "landuse", "natural", "name"])

    water_raw = fetch_features_safe(
        lat, lon,
        tags={"natural": ["water"], "waterway": ["river", "canal", "stream"]},
        dist=radius, utm_epsg=utm_epsg, origin_x=origin_x, origin_y=origin_y,
        geom_types=("Polygon", "MultiPolygon", "LineString", "MultiLineString"),
    )
    water = keep_serializable_columns(water_raw, ["natural", "waterway", "name"])

    # Save GeoJSONs (note: geometries are in local meters around 0,0)
    print("[4/4] Saving local-meter GeoJSON layers and figure-ground preview...")
    roads.to_file(out_dir / "roads.geojson", driver="GeoJSON")
    buildings.to_file(out_dir / "buildings.geojson", driver="GeoJSON")
    greens.to_file(out_dir / "greens.geojson", driver="GeoJSON")
    water.to_file(out_dir / "water.geojson", driver="GeoJSON")

    meta = {
        "site_name": site_name,
        "latitude": lat,
        "longitude": lon,
        "radius_m": radius,
        "utm_epsg": utm_epsg,
        "utm_origin_easting_m": round(origin_x, 3),
        "utm_origin_northing_m": round(origin_y, 3),
        "counts": {
            "buildings": int(len(buildings)),
            "roads": int(len(roads)),
            "greens": int(len(greens)),
            "water": int(len(water)),
        },
    }
    (out_dir / "origin.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    preview_path = out_dir / "site_preview.png"
    render_preview(preview_path, radius, buildings, roads, greens, water, site_name)
    print(f"Done! Saved outputs to: {out_dir}")
    print(f"  Buildings: {len(buildings)} | Roads: {len(roads)} | Greens: {len(greens)} | Water: {len(water)}")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch OSM urban context in local meters for Archicad.")
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT, help="Site latitude (WGS84)")
    parser.add_argument("--lon", type=float, default=DEFAULT_LON, help="Site longitude (WGS84)")
    parser.add_argument("--radius", type=int, default=DEFAULT_RADIUS_M, help="Context radius in meters")
    parser.add_argument("--name", type=str, default="Sangath_Thaltej_Ahmedabad", help="Site label")
    parser.add_argument("--out", type=Path, default=Path("output"), help="Output directory")
    args = parser.parse_args()

    fetch_site_context(args.lat, args.lon, args.radius, args.out, args.name)


if __name__ == "__main__":
    main()
