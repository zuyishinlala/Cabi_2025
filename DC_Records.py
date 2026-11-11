import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUT_PATH = ROOT / "Results" / "aggregated_sample.csv"
GEOJSON_PATH = ROOT / "data" / "DC_boundary" / "Washington_DC_Administrative_Boundary.geojson"
OUTPUT_PATH = ROOT / "Results" / "DC_Records.csv"
GRID_SIZE = 0.001


def extract_rings(geojson):
    rings = []

    def add_geometry(geometry):
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates", [])
        if geometry_type == "Polygon":
            rings.extend(coordinates)
        elif geometry_type == "MultiPolygon":
            for polygon in coordinates:
                rings.extend(polygon)
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

    if not rings or any(len(ring) < 4 for ring in rings):
        raise ValueError("GeoJSON must contain at least one valid polygon ring")
    return rings


def make_point_tester(rings):
    all_points = [point for ring in rings for point in ring]
    min_lng = min(point[0] for point in all_points)
    max_lng = max(point[0] for point in all_points)
    min_lat = min(point[1] for point in all_points)
    max_lat = max(point[1] for point in all_points)
    columns = math.floor((max_lng - min_lng) / GRID_SIZE) + 1
    rows = math.floor((max_lat - min_lat) / GRID_SIZE) + 1
    latitude_bins = [[] for _ in range(rows)]
    boundary_cells = set()

    def cell_index(value, lower_bound, count):
        return min(count - 1, max(0, math.floor((value - lower_bound) / GRID_SIZE)))

    for ring in rings:
        for first, second in zip(ring, ring[1:]):
            x1, y1 = first[:2]
            x2, y2 = second[:2]
            first_row = cell_index(min(y1, y2), min_lat, rows)
            last_row = cell_index(max(y1, y2), min_lat, rows)
            for row in range(first_row, last_row + 1):
                latitude_bins[row].append((x1, y1, x2, y2))

            min_column = cell_index(min(x1, x2), min_lng, columns)
            max_column = cell_index(max(x1, x2), min_lng, columns)
            min_row = cell_index(min(y1, y2), min_lat, rows)
            max_row = cell_index(max(y1, y2), min_lat, rows)
            for row in range(max(0, min_row - 1), min(rows, max_row + 2)):
                for column in range(max(0, min_column - 1), min(columns, max_column + 2)):
                    boundary_cells.add((row, column))

    def is_inside(lng, lat):
        if not (min_lng <= lng <= max_lng and min_lat <= lat <= max_lat):
            return False
        row = cell_index(lat, min_lat, rows)
        column = cell_index(lng, min_lng, columns)
        edges = latitude_bins[row]
        inside = False

        for x1, y1, x2, y2 in edges:
            cross = (lng - x1) * (y2 - y1) - (lat - y1) * (x2 - x1)
            if (
                abs(cross) <= 1e-12
                and min(x1, x2) <= lng <= max(x1, x2)
                and min(y1, y2) <= lat <= max(y1, y2)
            ):
                return True
            if (y1 > lat) != (y2 > lat):
                intersection_lng = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
                if intersection_lng > lng:
                    inside = not inside
        return inside

    grid = []
    for row in range(rows):
        lat = min_lat + (row + 0.5) * GRID_SIZE
        grid_row = []
        for column in range(columns):
            lng = min_lng + (column + 0.5) * GRID_SIZE
            grid_row.append(is_inside(lng, lat))
        grid.append(grid_row)

    def covers(lng, lat):
        if not (min_lng <= lng <= max_lng and min_lat <= lat <= max_lat):
            return False
        row = cell_index(lat, min_lat, rows)
        column = cell_index(lng, min_lng, columns)
        if (row, column) in boundary_cells:
            return is_inside(lng, lat)
        return grid[row][column]

    return covers


def filter_dc_records(
    input_path: Path = INPUT_PATH,
    geojson_path: Path = GEOJSON_PATH,
    output_path: Path = OUTPUT_PATH,
) -> int:
    with geojson_path.open(encoding="utf-8") as geojson_file:
        rings = extract_rings(json.load(geojson_file))
    covers = make_point_tester(rings)

    row_count = 0
    with input_path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        required_columns = {"start_lat", "start_lng", "end_lat", "end_lng"}
        if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
            raise ValueError(f"Input CSV must contain columns: {', '.join(sorted(required_columns))}")

        with output_path.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=reader.fieldnames)
            writer.writeheader()
            for record in reader:
                try:
                    start_lat = float(record["start_lat"])
                    start_lng = float(record["start_lng"])
                    end_lat = float(record["end_lat"])
                    end_lng = float(record["end_lng"])
                except (TypeError, ValueError):
                    continue

                if covers(start_lng, start_lat) and covers(end_lng, end_lat):
                    writer.writerow(record)
                    row_count += 1

    return row_count


def main():
    row_count = filter_dc_records()
    print(f"Wrote {row_count:,} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()