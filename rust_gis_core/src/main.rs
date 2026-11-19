//! High-Performance Rust GIS & DXF Acceleration Core
//! ====================================================
//! Executes architectural spatial math, setbacks, and DXF file generation
//! in sub-millisecond native machine code.

use std::env;
use std::fs;
use std::io::Write;
use std::path::Path;
use std::time::Instant;

#[derive(Debug, Clone, Copy)]
struct Point2D {
    x: f64,
    y: f64,
}

impl Point2D {
    fn new(x: f64, y: f64) -> Self {
        Self { x, y }
    }

    fn dist(&self, other: &Point2D) -> f64 {
        ((self.x - other.x).powi(2) + (self.y - other.y).powi(2)).sqrt()
    }
}

/// Calculate standard UTM zone and EPSG code
fn calculate_utm_epsg(lat: f64, lon: f64) -> (i32, i32) {
    let zone = ((lon + 180.0) / 6.0).floor() as i32 + 1;
    let base = if lat >= 0.0 { 32600 } else { 32700 };
    (base + zone, zone)
}

/// Project WGS84 (lon, lat) to UTM Easting/Northing in meters (WGS84 Ellipsoid)
fn lat_lon_to_utm(lat: f64, lon: f64, zone: i32) -> (f64, f64) {
    let a = 6378137.0; // WGS84 major axis
    let e = 0.081819190842622; // WGS84 eccentricity
    let e2 = e * e;

    let lat_rad = lat.to_radians();
    let lon_rad = lon.to_radians();
    let lon_origin = ((zone - 1) as f64 * 6.0 - 180.0 + 3.0).to_radians();

    let n = a / (1.0 - e2 * lat_rad.sin().powi(2)).sqrt();
    let t = lat_rad.tan().powi(2);
    let c = e2 / (1.0 - e2) * lat_rad.cos().powi(2);
    let delta_lon = lon_rad - lon_origin;

    let m = a * ((1.0 - e2 / 4.0 - 3.0 * e2.powi(2) / 64.0 - 5.0 * e2.powi(3) / 256.0) * lat_rad
        - (3.0 * e2 / 8.0 + 3.0 * e2.powi(2) / 32.0 + 45.0 * e2.powi(3) / 1024.0) * (2.0 * lat_rad).sin()
        + (15.0 * e2.powi(2) / 256.0 + 45.0 * e2.powi(3) / 1024.0) * (4.0 * lat_rad).sin()
        - (35.0 * e2.powi(3) / 3072.0) * (6.0 * lat_rad).sin());

    let k0 = 0.9996;
    let easting = k0 * n * (delta_lon * lat_rad.cos()
        + delta_lon.powi(3) * lat_rad.cos().powi(3) / 6.0 * (1.0 - t + c)
        + delta_lon.powi(5) * lat_rad.cos().powi(5) / 120.0 * (5.0 - 18.0 * t + t.powi(2) + 72.0 * c - 58.0 * e2))
        + 500000.0;

    let northing = k0 * (m + n * lat_rad.tan() * (delta_lon.powi(2) / 2.0
        + delta_lon.powi(4) / 24.0 * (5.0 - t + 9.0 * c + 4.0 * c.powi(2))
        + delta_lon.powi(6) / 720.0 * (61.0 - 58.0 * t + t.powi(2) + 600.0 * c - 330.0 * e2)));

    (easting, northing)
}

/// Inverse UTM projection (Easting, Northing -> WGS84 lon, lat)
fn utm_to_lat_lon(easting: f64, northing: f64, zone: i32) -> (f64, f64) {
    let a: f64 = 6378137.0;
    let e: f64 = 0.081819190842622;
    let e2: f64 = e * e;
    let k0: f64 = 0.9996;

    let x = easting - 500000.0;
    let y = northing;

    let m = y / k0;
    let mu = m / (a * (1.0 - e2 / 4.0 - 3.0 * e2.powi(2) / 64.0 - 5.0 * e2.powi(3) / 256.0));

    let e1 = (1.0 - (1.0 - e2).sqrt()) / (1.0 + (1.0 - e2).sqrt());
    let phi1 = mu
        + (3.0 * e1 / 2.0 - 27.0 * e1.powi(3) / 32.0) * (2.0 * mu).sin()
        + (21.0 * e1.powi(2) / 16.0 - 55.0 * e1.powi(4) / 32.0) * (4.0 * mu).sin()
        + (151.0 * e1.powi(3) / 96.0) * (6.0 * mu).sin()
        + (1097.0 * e1.powi(4) / 512.0) * (8.0 * mu).sin();

    let n1 = a / (1.0 - e2 * phi1.sin().powi(2)).sqrt();
    let t1 = phi1.tan().powi(2);
    let c1 = e2 / (1.0 - e2) * phi1.cos().powi(2);
    let r1 = a * (1.0 - e2) / (1.0 - e2 * phi1.sin().powi(2)).powf(1.5);
    let d = x / (n1 * k0);

    let lat = phi1 - (n1 * phi1.tan() / r1) * (d.powi(2) / 2.0
        - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1.powi(2) - 9.0 * e2) * d.powi(4) / 24.0
        + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1.powi(2) - 252.0 * e2 - 3.0 * c1.powi(2)) * d.powi(6) / 720.0);

    let lon_origin = ((zone - 1) as f64 * 6.0 - 180.0 + 3.0).to_radians();
    let lon = lon_origin + (d
        - (1.0 + 2.0 * t1 + c1) * d.powi(3) / 6.0
        + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1.powi(2) + 8.0 * e2 + 24.0 * t1.powi(2)) * d.powi(5) / 120.0) / phi1.cos();

    (lat.to_degrees(), lon.to_degrees())
}

/// Compute 2D polygon area via Shoelace formula
fn polygon_area(pts: &[Point2D]) -> f64 {
    let n = pts.len();
    if n < 3 {
        return 0.0;
    }
    let mut sum = 0.0;
    for i in 0..n {
        let j = (i + 1) % n;
        sum += pts[i].x * pts[j].y - pts[j].x * pts[i].y;
    }
    (sum.abs()) / 2.0
}

/// Compute 2D polygon perimeter
fn polygon_perimeter(pts: &[Point2D]) -> f64 {
    let n = pts.len();
    if n < 3 {
        return 0.0;
    }
    let mut sum = 0.0;
    for i in 0..n {
        sum += pts[i].dist(&pts[(i + 1) % n]);
    }
    sum
}

/// Compute line intersection for two infinite lines given by point + direction
fn line_intersection(p1: Point2D, d1: Point2D, p2: Point2D, d2: Point2D) -> Option<Point2D> {
    let det = d1.x * d2.y - d1.y * d2.x;
    if det.abs() < 1e-9 {
        return None;
    }
    let dx = p2.x - p1.x;
    let dy = p2.y - p1.y;
    let t = (dx * d2.y - dy * d2.x) / det;
    Some(Point2D::new(p1.x + t * d1.x, p1.y + t * d1.y))
}

/// Compute inward setback buffer polygon
fn compute_inward_setback(pts: &[Point2D], setback: f64) -> Vec<Point2D> {
    let n = pts.len();
    if n < 3 || setback <= 0.0 {
        return Vec::new();
    }

    // Check winding order (ensure counter-clockwise)
    let mut signed_area = 0.0;
    for i in 0..n {
        let j = (i + 1) % n;
        signed_area += pts[i].x * pts[j].y - pts[j].x * pts[i].y;
    }
    let ccw = signed_area > 0.0;

    // Build inward offset segments
    let mut offset_lines: Vec<(Point2D, Point2D)> = Vec::with_capacity(n);
    for i in 0..n {
        let p1 = pts[i];
        let p2 = pts[(i + 1) % n];
        let dx = p2.x - p1.x;
        let dy = p2.y - p1.y;
        let len = (dx * dx + dy * dy).sqrt();
        if len < 1e-6 {
            continue;
        }

        // Inward normal
        let (nx, ny) = if ccw {
            (-dy / len, dx / len)
        } else {
            (dy / len, -dx / len)
        };

        let off_p1 = Point2D::new(p1.x + nx * setback, p1.y + ny * setback);
        let dir = Point2D::new(dx / len, dy / len);
        offset_lines.push((off_p1, dir));
    }

    // Intersect consecutive offset lines to get setback vertices
    let m = offset_lines.len();
    let mut setback_pts = Vec::with_capacity(m);
    for i in 0..m {
        let prev = (i + m - 1) % m;
        let (p1, d1) = offset_lines[prev];
        let (p2, d2) = offset_lines[i];
        if let Some(inter) = line_intersection(p1, d1, p2, d2) {
            setback_pts.push(inter);
        }
    }

    // Validate that inward polygon has positive area and is smaller than original
    let orig_area = polygon_area(pts);
    let set_area = polygon_area(&setback_pts);
    if set_area > 0.0 && set_area < orig_area {
        setback_pts
    } else {
        Vec::new()
    }
}

/// Fast DXF Writer (Metric $INSUNITS = 6)
fn export_dxf_2d(path: &Path, plot_pts: &[Point2D], setback_pts: &[Point2D], meta_text: &str) -> std::io::Result<()> {
    let mut file = fs::File::create(path)?;
    writeln!(file, "0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n6\n9\n$MEASUREMENT\n70\n1\n0\nENDSEC")?;
    writeln!(file, "0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nLAYER")?;
    writeln!(file, "0\nLAYER\n2\n01-PLOT-BOUNDARY\n70\n0\n62\n1\n6\nCONTINUOUS")?;
    writeln!(file, "0\nLAYER\n2\n02-SETBACK-ENVELOPE\n70\n0\n62\n3\n6\nCONTINUOUS")?;
    writeln!(file, "0\nLAYER\n2\n03-ANNOTATIONS\n70\n0\n62\n2\n6\nCONTINUOUS")?;
    writeln!(file, "0\nENDTAB\n0\nENDSEC")?;
    writeln!(file, "0\nSECTION\n2\nENTITIES")?;

    // Plot polyline
    writeln!(file, "0\nLWPOLYLINE\n8\n01-PLOT-BOUNDARY\n90\n{}\n70\n1", plot_pts.len())?;
    for p in plot_pts {
        writeln!(file, "10\n{:.3}\n20\n{:.3}", p.x, p.y)?;
    }

    // Setback polyline
    if !setback_pts.is_empty() {
        writeln!(file, "0\nLWPOLYLINE\n8\n02-SETBACK-ENVELOPE\n90\n{}\n70\n1", setback_pts.len())?;
        for p in setback_pts {
            writeln!(file, "10\n{:.3}\n20\n{:.3}", p.x, p.y)?;
        }
    }

    // Annotation
    writeln!(file, "0\nTEXT\n8\n03-ANNOTATIONS\n10\n0.0\n20\n-5.0\n30\n0.0\n40\n1.5\n1\n{}", meta_text)?;

    writeln!(file, "0\nENDSEC\n0\nEOF")?;
    Ok(())
}

fn export_dxf_3d(path: &Path, setback_pts: &[Point2D], height: f64) -> std::io::Result<()> {
    let mut file = fs::File::create(path)?;
    writeln!(file, "0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n6\n0\nENDSEC")?;
    writeln!(file, "0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nLAYER\n0\nLAYER\n2\n01-3D-MASSING\n62\n4\n0\nENDTAB\n0\nENDSEC")?;
    writeln!(file, "0\nSECTION\n2\nENTITIES")?;

    if !setback_pts.is_empty() {
        let n = setback_pts.len();
        // Vertical walls
        for i in 0..n {
            let p1 = setback_pts[i];
            let p2 = setback_pts[(i + 1) % n];
            writeln!(file, "0\n3DFACE\n8\n01-3D-MASSING")?;
            writeln!(file, "10\n{:.3}\n20\n{:.3}\n30\n0.0", p1.x, p1.y)?;
            writeln!(file, "11\n{:.3}\n20\n{:.3}\n31\n0.0", p2.x, p2.y)?;
            writeln!(file, "12\n{:.3}\n20\n{:.3}\n32\n{:.3}", p2.x, p2.y, height)?;
            writeln!(file, "13\n{:.3}\n20\n{:.3}\n33\n{:.3}", p1.x, p1.y, height)?;
        }

        // Roof cap
        let cx: f64 = setback_pts.iter().map(|p| p.x).sum::<f64>() / n as f64;
        let cy: f64 = setback_pts.iter().map(|p| p.y).sum::<f64>() / n as f64;
        for i in 0..n {
            let p1 = setback_pts[i];
            let p2 = setback_pts[(i + 1) % n];
            writeln!(file, "0\n3DFACE\n8\n01-3D-MASSING")?;
            writeln!(file, "10\n{:.3}\n20\n{:.3}\n30\n{:.3}", p1.x, p1.y, height)?;
            writeln!(file, "11\n{:.3}\n20\n{:.3}\n31\n{:.3}", p2.x, p2.y, height)?;
            writeln!(file, "12\n{:.3}\n20\n{:.3}\n32\n{:.3}", cx, cy, height)?;
            writeln!(file, "13\n{:.3}\n20\n{:.3}\n33\n{:.3}", cx, cy, height)?;
        }
    }

    writeln!(file, "0\nENDSEC\n0\nEOF")?;
    Ok(())
}

fn main() {
    let start_time = Instant::now();
    let args: Vec<String> = env::args().collect();

    if args.len() > 1 && args[1] == "--bench" {
        println!("Rust GIS Core: Running benchmark on Sangath sample plot...");
        let sangath_coords = vec![
            (23.04940, 72.52650),
            (23.04940, 72.52690),
            (23.04910, 72.52690),
            (23.04910, 72.52650),
        ];
        let (epsg, zone) = calculate_utm_epsg(23.04925, 72.52670);
        let (ox, oy) = lat_lon_to_utm(23.04925, 72.52670, zone);

        let local_pts: Vec<Point2D> = sangath_coords
            .iter()
            .map(|&(lat, lon)| {
                let (ux, uy) = lat_lon_to_utm(lat, lon, zone);
                Point2D::new(ux - ox, uy - oy)
            })
            .collect();

        let area = polygon_area(&local_pts);
        let peri = polygon_perimeter(&local_pts);
        let setback = compute_inward_setback(&local_pts, 3.0);
        let b_area = polygon_area(&setback);

        let elapsed = start_time.elapsed();
        println!("Benchmark Results:");
        println!("  Plot Area:         {:.2} sq.m", area);
        println!("  Plot Perimeter:    {:.2} m", peri);
        println!("  Buildable Area:    {:.2} sq.m", b_area);
        println!("  UTM EPSG:          EPSG:{}", epsg);
        println!("  Execution Time:    {:.2?} ({} microseconds)", elapsed, elapsed.as_micros());
        return;
    }

    println!("Rust Architectural GIS & DXF Acceleration Engine ready.");
    println!("Usage: rust_gis_core --bench");
}
