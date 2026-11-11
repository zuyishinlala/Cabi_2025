# Washington, DC Ride Data

Python scripts for sampling monthly ride records, keeping rides whose start and
end locations are both within the Washington, DC boundary, visualizing ride
location density, and optionally loading the filtered CSV into PostgreSQL.

## Requirements

- Python 3.9 or newer
- `python-dotenv` (needed only by `UploadData.py`)
- PostgreSQL command-line tools, including `psql` (needed only by `UploadData.py`)

Create and activate a virtual environment from the repository root, then install
the pinned Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.
The `.venv/` directory is local to your machine and excluded from version
control. `python-dotenv` is only used when uploading data to PostgreSQL.

## Input data

The scripts expect these files relative to the repository root:

```text
data/
├── DC_boundary/
│   └── Washington_DC_Administrative_Boundary.geojson
└── user_records/
    ├── 202501.csv
    ├── 202502.csv
    └── ... monthly CSV files
```

Monthly CSV files must have matching headers. The processing and visualization
scripts require `start_lat`, `start_lng`, `end_lat`, and `end_lng` columns.
`UploadData.py` additionally expects the output CSV columns listed below.

The `data/` and `Results/` directories are excluded by `.gitignore`; supply
these inputs locally before running the pipeline. The weather data under
`data/weather/` is not used by the current scripts.

## Run the pipeline

From the repository root:

```bash
python Aggregate.py
python Visualization.py
```

`Aggregate.py` finds every `*.csv` in `data/user_records/`, takes a reproducible
30% random sample from each file (seed `42`), combines the sampled rows, then
keeps rides for which both endpoints fall inside the supplied DC boundary.
Rows with invalid coordinate values are skipped during boundary filtering.

## Scripts and outputs

- `Aggregate.py` runs the sampling and boundary-filtering pipeline.
- `DownSampling.py` samples and combines the monthly CSVs.
- `DC_Records.py` filters a sampled CSV using the boundary GeoJSON.
- `Visualization.py` creates `Visualization.html`, a self-contained map with
  toggles for ride start and end density layers. Open the HTML file in a
  browser to view it.
- `CheckRideId.py` reports duplicate or missing `ride_id` values in
  `data/user_records/202501.csv`.
- `UploadData.py` loads `Results/DC_Records.csv` into PostgreSQL.

The pipeline writes:

- `Results/aggregated_sample.csv` — sampled and combined records.
- `Results/DC_Records.csv` — sampled rides whose start and end are both within
  the boundary.
- `Visualization.html` — map generated from `Results/DC_Records.csv`.

The filtered CSV is expected to contain these columns, in this order, for
database upload:

```text
ride_id, rideable_type, started_at, ended_at, start_station_name,
start_station_id, end_station_name, end_station_id, start_lat, start_lng,
end_lat, end_lng, member_casual
```

## Optional PostgreSQL upload

Create the destination table `public.dc_records` with the columns above, then
create a local `.env` file containing your PostgreSQL connection URL:

```dotenv
DATABASE_URL=postgresql://username:password@host:5432/database
```

Run the uploader from the repository root:

```bash
python UploadData.py
```

The connection uses SSL by default unless an `sslmode` is specified in the
URL. Keep `.env` private; it is excluded from version control.
