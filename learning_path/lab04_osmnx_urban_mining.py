"""
LAB 04: Urban Mining with OSMnx & OpenStreetMap
=================================================
Architectural Goal:
  Learn how to extract real-world urban context (street networks, building
  footprints, public parks, and amenities) from OpenStreetMap using OSMnx,
  configure Overpass API endpoints reliably, and handle network throttling.

How to Run:
  .venv\\Scripts\\python.exe learning_path\\lab04_osmnx_urban_mining.py
"""

import osmnx as ox
import geopandas as gpd
from shapely.geometry import Point, Polygon
import matplotlib.pyplot as plt
from pathlib import Path
import json


def section_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f" {title.upper()}")
    print("=" * 60)


def configure_osmnx() -> None:
    """
    Overpass API best practices:
    1. Set a descriptive User-Agent (Overpass policy rejects anonymous or generic agents).
    2. Set a polite request timeout (15s).
    3. Allow using alternate public Overpass mirrors if the main German server is busy.
    """
    ox.settings.user_agent = "VSS_Sangath_BIM_Studio/1.0 (Ahmedabad Urban Research)"
    ox.settings.timeout = 15
    ox.settings.use_cache = True
    ox.settings.log_console = False


def create_offline_sample_context(lat: float, lon: float, radius_m: float) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Provides a synthetic fallback dataset around the coordinates if
    the live Overpass API endpoint is rate-limited or temporarily unreachable.
    """
    print("Notice: Generating offline architectural fallback dataset...")
    # Synthetic street network
    roads_data = [
        {"name": "Thaltej Main Road", "highway": "primary", "lanes": 4, "geometry": Point(lon, lat).buffer(0.0015).boundary},
        {"name": "Sangath Access Lane", "highway": "residential", "lanes": 2, "geometry": Point(lon, lat).buffer(0.0006).boundary},
    ]
    roads_gdf = gpd.GeoDataFrame(roads_data, crs="EPSG:4326")

    # Synthetic buildings around Sangath
    b_data = [
        {"name": "Sangath Studio Main Wing", "building": "civic", "levels": 2, "height": "7.5",
         "geometry": Polygon([(lon - 0.0003, lat - 0.0002), (lon + 0.0002, lat - 0.0002), (lon + 0.0002, lat + 0.0002), (lon - 0.0003, lat + 0.0002)])},
        {"name": "Adjacent Pavilion", "building": "commercial", "levels": 3, "height": "10.0",
         "geometry": Polygon([(lon + 0.0005, lat + 0.0003), (lon + 0.0010, lat + 0.0003), (lon + 0.0010, lat + 0.0008), (lon + 0.0005, lat + 0.0008)])},
    ]
    buildings_gdf = gpd.GeoDataFrame(b_data, crs="EPSG:4326")
    return roads_gdf, buildings_gdf


import socket


def is_online(host: str = "8.8.8.8", port: int = 53, timeout: float = 2.0) -> bool:
    """Quick check if internet access is available."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except OSError:
        return False


def main() -> None:
    section_header("1. How OpenStreetMap Represents the City")
    print("OSM uses three fundamental geometric elements:")
    print("  1. Node:     A point with lat/lon (e.g. tree, lamp post, traffic signal).")
    print("  2. Way:      An ordered list of nodes. Open ways = roads/railways.")
    print("               Closed ways = building footprints, plots, courtyards.")
    print("  3. Relation: Groups of ways and nodes (e.g. multi-polygon building complexes, bus routes).")

    section_header("2. Configuring OSMnx Settings")
    configure_osmnx()
    print("Configured OSMnx:")
    print(f"  User-Agent: {ox.settings.user_agent}")
    print(f"  Timeout:    {ox.settings.timeout}s")
    print(f"  Cache:      {ox.settings.use_cache}")

    # Sangath Studio, Thaltej, Ahmedabad
    lat = 23.04917
    lon = 72.52667
    radius = 350  # 350 meter radius around Sangath

    section_header("3. Downloading Street Network and Building Footprints")

    roads_gdf = None
    buildings_gdf = None

    if not is_online():
        print("Network check: Offline / sandboxed environment detected.")
        roads_gdf, buildings_gdf = create_offline_sample_context(lat, lon, radius)
    else:
        # Primary Overpass public endpoints to try
        mirrors = [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
        ]
        for endpoint in mirrors:
            try:
                print(f"Attempting live query via: {endpoint}...")
                ox.settings.overpass_endpoint = endpoint

                # Fetch street network graph
                graph = ox.graph_from_point((lat, lon), dist=radius, network_type="all", simplify=True)
                # Convert graph into nodes and edges GeoDataFrames
                _, edges = ox.graph_to_gdfs(graph, nodes=True, edges=True)
                roads_gdf = edges

                # Fetch building footprints
                buildings = ox.features_from_point((lat, lon), tags={"building": True}, dist=radius)
                buildings = buildings[buildings.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
                buildings_gdf = buildings
                print("Successfully retrieved live OpenStreetMap data!")
                break
            except Exception as err:
                print(f"Endpoint notice ({endpoint}): {err}")

    if roads_gdf is None or buildings_gdf is None or len(roads_gdf) == 0:
        roads_gdf, buildings_gdf = create_offline_sample_context(lat, lon, radius)

    section_header("4. Inspecting the Extracted Urban Attributes")

    print(f"Total Road Segments Extracted:    {len(roads_gdf)}")
    print(f"Total Building Footprints Found: {len(buildings_gdf)}")

    if "highway" in roads_gdf.columns:
        print("\nRoad Class Breakdown:")
        print(roads_gdf["highway"].value_counts().head(5))

    building_types = buildings_gdf["building"].value_counts().head(5) if "building" in buildings_gdf.columns else []
    print("\nBuilding Types Breakdown:")
    print(building_types)

    section_header("5. Saving Urban Layers to Output")

    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_roads = out_dir / "lab04_roads.geojson"
    out_buildings = out_dir / "lab04_buildings.geojson"

    # Clean non-scalar attributes for clean GeoJSON export
    def clean_cols(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        clean = gpd.GeoDataFrame(geometry=df.geometry, crs=df.crs)
        for col in df.columns:
            if col != "geometry" and df[col].dtype == "object":
                clean[col] = df[col].astype(str)
            elif col != "geometry":
                clean[col] = df[col]
        return clean

    clean_cols(roads_gdf).to_file(out_roads, driver="GeoJSON")
    clean_cols(buildings_gdf).to_file(out_buildings, driver="GeoJSON")

    print(f"Saved roads GeoJSON:     {out_roads}")
    print(f"Saved buildings GeoJSON: {out_buildings}")
    print("\nDone! You now understand how OSMnx queries Overpass and extracts urban GIS layers.")


if __name__ == "__main__":
    main()
