import csv
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATASETS_DIR = ROOT / "data" / "user_records"
OUTPUT_PATH = ROOT / "Results" / "aggregated_sample.csv"
SAMPLE_FRACTION = 0.3
RANDOM_SEED = 42


def downsample_and_aggregate(
    input_paths: list[Path],
    output_path: Path,
    sample_fraction: float = SAMPLE_FRACTION,
    seed: int = RANDOM_SEED,
) -> int:
    if not 0 <= sample_fraction <= 1:
        raise ValueError("sample_fraction must be between 0 and 1")
    if not input_paths:
        raise FileNotFoundError("No CSV files were provided")

    expected_header = None
    file_row_counts = []
    for input_path in input_paths:
        with input_path.open("r", newline="", encoding="utf-8-sig") as input_file:
            reader = csv.reader(input_file)
            header = next(reader, None)
            if header is None:
                raise ValueError(f"{input_path} is empty")
            if expected_header is None:
                expected_header = header
            elif header != expected_header:
                raise ValueError(
                    f"CSV header in {input_path} does not match the other files"
                )
            file_row_counts.append((input_path, sum(1 for _ in reader)))

    rng = random.Random(seed)
    sampled_row_count = 0
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(expected_header)

        for input_path, row_count in file_row_counts:
            sample_count = round(row_count * sample_fraction)
            sampled_indices = set(rng.sample(range(row_count), sample_count))
            with input_path.open("r", newline="", encoding="utf-8-sig") as input_file:
                reader = csv.reader(input_file)
                header = next(reader, None)
                if header != expected_header:
                    raise ValueError(f"CSV header changed while reading {input_path}")
                for row_index, row in enumerate(reader):
                    if row_index in sampled_indices:
                        writer.writerow(row)
                        sampled_row_count += 1

    return sampled_row_count


def main() -> None:
    input_paths = sorted(DATASETS_DIR.glob("*.csv"))
    if not input_paths:
        raise FileNotFoundError(f"No CSV files found in {DATASETS_DIR}")

    row_count = downsample_and_aggregate(
        input_paths,
        OUTPUT_PATH,
        sample_fraction=SAMPLE_FRACTION,
        seed=RANDOM_SEED,
    )
    print(
        f"Randomly sampled {row_count:,} rows from {len(input_paths)} files "
        f"into {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()