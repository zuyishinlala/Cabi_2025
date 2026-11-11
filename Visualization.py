import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RECORDS_PATH = ROOT / "Results" / "DC_Records.csv"
GEOJSON_PATH = ROOT / "data" / "DC_boundary" / "Washington_DC_Administrative_Boundary.geojson"
OUTPUT_PATH = ROOT / "Visualization.html"

SVG_WIDTH = 1100
SVG_HEIGHT = 820
MAP_PADDING = 35
CELL_SIZE = 4
START_COLOR = "#087eae"
END_COLOR = "#e76f00"


def polygons_from_geojson(geojson):
    polygons = []

    def add_geometry(geometry):
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates", [])
        if geometry_type == "Polygon":
            polygons.append(coordinates)
        elif geometry_type == "MultiPolygon":
            polygons.extend(coordinates)
        elif geometry_type == "GeometryCollection":
            for child in geometry.get("geometries", []):
                add_geometry(child)
        elif geometry_type not in (None, "Point", "MultiPoint", "LineString", "MultiLineString"):
            raise ValueError(f"Unsupported GeoJSON geometry type: {geometry_type}")

    if geojson.get("type") == "FeatureCollection":
        for feature in geojson.get("features", []):
            if feature.get("geometry"):
                add_geometry(feature["geometry"])
    elif geojson.get("type") == "Feature":
        if geojson.get("geometry"):
            add_geometry(geojson["geometry"])
    else:
        add_geometry(geojson)

    if not polygons:
        raise ValueError("GeoJSON must contain at least one polygon")
    return polygons


def make_projection(polygons):
    coordinates = [
        point[:2]
        for polygon in polygons
        for ring in polygon
        for point in ring
    ]
    mean_latitude = sum(lat for _, lat in coordinates) / len(coordinates)
    longitude_scale = math.cos(math.radians(mean_latitude))
    projected = [(lng * longitude_scale, lat) for lng, lat in coordinates]
    min_x = min(x for x, _ in projected)
    max_x = max(x for x, _ in projected)
    min_y = min(y for _, y in projected)
    max_y = max(y for _, y in projected)
    scale = min(
        (SVG_WIDTH - 2 * MAP_PADDING) / (max_x - min_x),
        (SVG_HEIGHT - 2 * MAP_PADDING) / (max_y - min_y),
    )
    map_width = (max_x - min_x) * scale
    map_height = (max_y - min_y) * scale
    offset_x = (SVG_WIDTH - map_width) / 2
    offset_y = (SVG_HEIGHT - map_height) / 2

    def project(lng, lat):
        x = offset_x + (lng * longitude_scale - min_x) * scale
        y = SVG_HEIGHT - offset_y - (lat - min_y) * scale
        return x, y

    return project


def polygon_svg(polygons, project):
    paths = []
    for polygon in polygons:
        for ring in polygon:
            commands = []
            for index, point in enumerate(ring):
                x, y = project(point[0], point[1])
                commands.append(f"{'M' if index == 0 else 'L'}{x:.2f},{y:.2f}")
            commands.append("Z")
            paths.append(" ".join(commands))
    return (
        '<path d="' + " ".join(paths) + '" fill="#edf1f4" '
        'fill-rule="evenodd" stroke="#263746" stroke-width="1.5" '
        'stroke-linejoin="round"/>'
    )


def add_records(path, project):
    starts = {}
    ends = {}
    trip_count = 0

    def add_point(counts, lng, lat):
        x, y = project(lng, lat)
        cell = (math.floor(x / CELL_SIZE), math.floor(y / CELL_SIZE))
        counts[cell] = counts.get(cell, 0) + 1

    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        required = {"start_lat", "start_lng", "end_lat", "end_lng"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path} must contain columns: {', '.join(sorted(required))}")

        for record in reader:
            try:
                start_lng = float(record["start_lng"])
                start_lat = float(record["start_lat"])
                end_lng = float(record["end_lng"])
                end_lat = float(record["end_lat"])
            except (TypeError, ValueError):
                continue
            add_point(starts, start_lng, start_lat)
            add_point(ends, end_lng, end_lat)
            trip_count += 1

    return starts, ends, trip_count


def density_layer(counts, color, label):
    maximum = max(counts.values(), default=1)
    cells = []
    for (column, row), count in counts.items():
        opacity = 0.15 + 0.78 * math.log1p(count) / math.log1p(maximum)
        x = column * CELL_SIZE
        y = row * CELL_SIZE
        cells.append(
            f'<rect x="{x}" y="{y}" width="{CELL_SIZE + 0.4}" '
            f'height="{CELL_SIZE + 0.4}" fill="{color}" fill-opacity="{opacity:.3f}"/>'
        )
    return f'<g id="{label}-layer" aria-label="{label} locations">{"".join(cells)}</g>'


def build_html(polygons, project, starts, ends, trip_count):
    boundary = polygon_svg(polygons, project)
    start_layer = density_layer(starts, START_COLOR, "start")
    end_layer = density_layer(ends, END_COLOR, "end")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Washington, DC Ride Locations</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #17212b; }}
    body {{ margin: 0; padding: 1.5rem; background: #f5f7f9; }}
    main {{ max-width: 1200px; margin: auto; }}
    h1 {{ margin: 0 0 .4rem; font-size: 1.6rem; }}
    p {{ color: #45515c; }}
    .controls {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 1rem 0; }}
    button {{ border: 1px solid #8794a0; border-radius: 5px; background: white; padding: .55rem .85rem; cursor: pointer; }}
    button[aria-pressed="true"] {{ color: white; background: #263746; border-color: #263746; }}
    .map {{ overflow: auto; background: white; border: 1px solid #d5dce2; border-radius: 8px; }}
    svg {{ display: block; width: 100%; min-width: 600px; height: auto; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 1.2rem; margin-top: .8rem; color: #45515c; }}
    .key {{ display: inline-block; width: .8rem; height: .8rem; border-radius: 50%; margin-right: .4rem; }}
    .note {{ font-size: .9rem; }}
  </style>
</head>
<body>
<main>
  <h1>Washington, DC ride locations</h1>
  <p>{trip_count:,} rides shown. Each colored cell represents the number of start or end events in that small map area.</p>
  <div class="controls" aria-label="Map layers">
    <button id="start-toggle" type="button" aria-pressed="true">Toggle start locations ({sum(starts.values()):,})</button>
    <button id="end-toggle" type="button" aria-pressed="true">Toggle end locations ({sum(ends.values()):,})</button>
  </div>
  <div class="map">
    <svg viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" role="img" aria-label="Map showing DC boundary and ride start and end location densities">
      {boundary}
      {start_layer}
      {end_layer}
    </svg>
  </div>
  <div class="legend">
    <span><i class="key" style="background:{START_COLOR}"></i>Ride starts</span>
    <span><i class="key" style="background:{END_COLOR}"></i>Ride ends</span>
    <span>Darkness indicates more events.</span>
  </div>
  <p class="note">Boundary outline is from the supplied GeoJSON. Location cells are aggregated for a responsive, self-contained view; all valid ride endpoints are counted.</p>
</main>
<script>
  for (const [buttonId, layerId] of [["start-toggle", "start-layer"], ["end-toggle", "end-layer"]]) {{
    const button = document.getElementById(buttonId);
    const layer = document.getElementById(layerId);
    button.addEventListener("click", () => {{
      const visible = button.getAttribute("aria-pressed") !== "true";
      button.setAttribute("aria-pressed", String(visible));
      layer.style.display = visible ? "" : "none";
    }});
  }}
</script>
</body>
</html>
"""


def main():
    with GEOJSON_PATH.open(encoding="utf-8") as geojson_file:
        polygons = polygons_from_geojson(json.load(geojson_file))
    project = make_projection(polygons)
    starts, ends, trip_count = add_records(RECORDS_PATH, project)
    page = build_html(polygons, project, starts, ends, trip_count)
    OUTPUT_PATH.write_text(page, encoding="utf-8")
    print(f"Rendered {trip_count:,} rides to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()