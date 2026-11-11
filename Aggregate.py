from pathlib import Path

from DC_Records import filter_dc_records
from DownSampling import downsample_and_aggregate

ROOT = Path(__file__).resolve().parent
DATASETS_DIR = ROOT / "data" / "user_records"
RESULTS_DIR = ROOT / "Results"
SAMPLED_PATH = RESULTS_DIR / "aggregated_sample.csv"
OUTPUT_PATH = RESULTS_DIR / "DC_Records.csv"
GEOJSON_PATH = ROOT / "data" / "DC_boundary" / "Washington_DC_Administrative_Boundary.geojson"
SAMPLE_FRACTION = 0.3
RANDOM_SEED = 42


def main() -> None:
    input_paths = sorted(DATASETS_DIR.glob("*.csv"))
    if not input_paths:
        raise FileNotFoundError(f"No CSV files found in {DATASETS_DIR}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    sampled_row_count = downsample_and_aggregate(
        input_paths,
        SAMPLED_PATH,
        sample_fraction=SAMPLE_FRACTION,
        seed=RANDOM_SEED,
    )
    dc_row_count = filter_dc_records(
        input_path=SAMPLED_PATH,
        geojson_path=GEOJSON_PATH,
        output_path=OUTPUT_PATH,
    )

    print(
        f"Sampled {sampled_row_count:,} rows from {len(input_paths)} monthly files "
        f"and wrote {dc_row_count:,} D.C. records to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()