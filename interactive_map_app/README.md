# Interactive Architectural Site Selector & Archicad Generator

A visual, map-based tool built in Python. Select or draw any plot on a real satellite/street map and export Archicad 29 files instantly.

---

## Features

1. **Real-World Interactive Map**:
   - Switch between **OpenStreetMap** (road vectors) and **Esri World Imagery** (high-resolution satellite view).
   - Fast presets for iconic architectural sites in India:
     - Sangath Studio (Balkrishna Doshi, Ahmedabad)
     - CEPT University (Ahmedabad)
     - IIM Ahmedabad (Louis Kahn)
     - Sabarmati Riverfront
     - Connaught Place (New Delhi)
     - Bandra Kurla Complex (Mumbai)
2. **Point-and-Click Drawing Tool**:
   - Click "Start Drawing Plot" to place corners around any real land parcel.
   - Click near the first point to close the boundary.
3. **Live Municipal & BIM Calculations**:
   - **Plot Boundary Area** in both $m^2$ and $sq.ft$.
   - **Perimeter** in meters.
   - **Municipal Setback (m)**: Adjust the setback slider to see the buildable zone shrink in real time.
   - **Permissible Ground Coverage %**: See what percentage of the site is buildable.
   - **Floor Space Index (FSI / FAR)**: Change the number of floors to calculate total Gross Floor Area.
   - **UTM Cartographic Projection**: Shows the exact EPSG code and Survey Point coordinates for Archicad.
4. **Instant Archicad 29 Deliverables**:
   - **2D Site Plan (.DXF)**: Layered boundary, setbacks, scale bar, North arrow, and dimensions.
   - **3D Massing (.DXF)**: Extruded 3D building volume using `3DFACE` ready to orbit in Archicad's 3D window (`F3`).
   - **Survey Point (.JSON)**: Exact UTM Easting/Northing offsets for Archicad Location Settings.

---

## How to Run

In your PowerShell terminal:

```powershell
.venv\Scripts\python.exe interactive_map_app\app.py
```

This will automatically start the local server and open `http://localhost:8050` in your default browser.
