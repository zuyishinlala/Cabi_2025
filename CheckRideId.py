import csv
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "data" / "user_records" / "202501.csv"
MAX_DUPLICATES_TO_SHOW = 10


def main() -> None:
    ride_id_counts: Counter[str] = Counter()
    row_count = 0
    missing_ride_id_count = 0

    with CSV_PATH.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames or "ride_id" not in reader.fieldnames:
            raise ValueError(f"CSV file must contain a ride_id column: {CSV_PATH}")

        for row in reader:
            row_count += 1
            ride_id = row.get("ride_id")
            if ride_id is None or not ride_id.strip():
                missing_ride_id_count += 1
            else:
                ride_id_counts[ride_id] += 1

    duplicates = sorted(
        (
            (ride_id, count)
            for ride_id, count in ride_id_counts.items()
            if count > 1
        ),
        key=lambda item: (-item[1], item[0]),
    )
    is_unique = not duplicates and missing_ride_id_count == 0

    print(f"CSV: {CSV_PATH}")
    print(f"Data rows: {row_count:,}")
    print(f"Unique ride_id values: {len(ride_id_counts):,}")
    print(f"Duplicate ride_id values: {len(duplicates):,}")
    print(f"Missing ride_id values: {missing_ride_id_count:,}")
    print(f"ride_id is unique: {is_unique}")

    if duplicates:
        print(f"\nFirst {min(len(duplicates), MAX_DUPLICATES_TO_SHOW)} duplicates:")
        for ride_id, count in duplicates[:MAX_DUPLICATES_TO_SHOW]:
            print(f"  {ride_id}: {count} rows")


if __name__ == "__main__":
    main()
