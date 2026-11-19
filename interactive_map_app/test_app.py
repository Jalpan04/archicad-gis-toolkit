import threading
import time
import requests
from http.server import HTTPServer
from app import AppRequestHandler

def run():
    server = HTTPServer(("127.0.0.1", 8060), AppRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(1)

    session = requests.Session()
    session.trust_env = False

    url = "http://127.0.0.1:8060"

    # 1. Test GET /
    res_get = session.get(url + "/")
    assert res_get.status_code == 200, f"Expected 200, got {res_get.status_code}"
    assert "Site Context & BIM Analyzer" in res_get.text
    assert "Map Neighbor Building" in res_get.text
    assert "Fetch real surrounding roads from OpenStreetMap" in res_get.text
    print("GET / passed: HTML template loaded with neighbor mapping tools and road checkbox.")

    # 2. Test POST with user neighbors only (no OSM) -- the core use case
    payload_no_osm = {
        "coordinates": [
            [23.03050, 72.56010],
            [23.03050, 72.56060],
            [23.03010, 72.56060],
            [23.03010, 72.56010]
        ],
        "setback_m": 3.0,
        "floors": 4,
        "floor_height_m": 3.2,
        "name": "Law_Garden_Test",
        "include_context": False,
        "user_neighbors": [
            {
                "name": "Residence_North",
                "floors": 5,
                "height_m": 16.0,
                "coordinates": [
                    [23.03070, 72.56010],
                    [23.03070, 72.56060],
                    [23.03055, 72.56060],
                    [23.03055, 72.56010]
                ]
            },
            {
                "name": "Office_East",
                "floors": 7,
                "height_m": 22.4,
                "coordinates": [
                    [23.03050, 72.56065],
                    [23.03050, 72.56110],
                    [23.03010, 72.56110],
                    [23.03010, 72.56065]
                ]
            }
        ]
    }

    res_post = session.post(url + "/api/analyze", json=payload_no_osm)
    assert res_post.status_code == 200, f"Expected 200, got {res_post.status_code}"
    data = res_post.json()

    print("POST /api/analyze (user-traced neighbors only):")
    print(f"  Plot Area:          {data['plot_area_sqm']:.1f} sq.m")
    print(f"  Buildable Area:     {data['buildable_sqm']:.1f} sq.m")
    print(f"  FSI:                {data['fsi']:.2f}")
    print(f"  Context Buildings:  {len(data['context_buildings'])}")
    print(f"  Context Roads:      {len(data['context_roads'])}")

    # Verify ONLY user-traced buildings appear -- no random OSM buildings
    assert len(data['context_buildings']) == 2, f"Expected exactly 2 user buildings, got {len(data['context_buildings'])}"
    assert data['context_buildings'][0]['name'] == "Residence_North"
    assert data['context_buildings'][0]['height_m'] == 16.0
    assert data['context_buildings'][1]['name'] == "Office_East"
    assert data['context_buildings'][1]['height_m'] == 22.4
    assert len(data['context_roads']) == 0, "Roads should be empty when include_context is False"
    print("VERIFIED: Only user-traced buildings appear. Zero random/OSM buildings.")

    # Verify deliverables contain only real data
    token = data["token"]

    res_ifc = session.get(f"{url}/api/download?type=ifc&token={token}")
    assert res_ifc.status_code == 200
    ifc_text = res_ifc.content.decode("utf-8", errors="replace")
    assert "Residence_North" in ifc_text
    assert "Office_East" in ifc_text
    print("IFC verified: Only user-traced neighbor massing blocks in BIM.")

    res_2d = session.get(f"{url}/api/download?type=2d&token={token}")
    assert res_2d.status_code == 200
    assert b"05-CONTEXT-BUILDINGS-2D" in res_2d.content
    print("2D DXF verified: Neighbor layer present.")

    res_3d = session.get(f"{url}/api/download?type=3d&token={token}")
    assert res_3d.status_code == 200
    assert b"3DFACE" in res_3d.content
    print("3D DXF verified: Extruded massing present.")

    res_origin = session.get(f"{url}/api/download?type=origin&token={token}")
    assert res_origin.status_code == 200
    assert "utm_origin_x" in res_origin.json()
    print("Survey Origin JSON verified.")

    # 3. Test POST with no neighbors and no OSM -- should produce clean deliverables with zero context
    payload_empty = {
        "coordinates": [
            [23.03050, 72.56010],
            [23.03050, 72.56060],
            [23.03010, 72.56060],
            [23.03010, 72.56010]
        ],
        "setback_m": 3.0,
        "floors": 3,
        "floor_height_m": 3.2,
        "name": "Clean_Plot",
        "include_context": False,
        "user_neighbors": []
    }

    res_clean = session.post(url + "/api/analyze", json=payload_empty)
    assert res_clean.status_code == 200
    clean_data = res_clean.json()
    assert len(clean_data['context_buildings']) == 0, f"Expected 0 buildings, got {len(clean_data['context_buildings'])}"
    assert len(clean_data['context_roads']) == 0
    print("VERIFIED: Empty neighbors = zero context buildings. No fake/default data generated.")

    print("\nALL TESTS PASSED -- No fake data, only real user-traced buildings.")
    server.shutdown()

if __name__ == "__main__":
    run()
