import csv
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "Results" / "DC_Records.csv"
TABLE_NAME = "public.dc_records"
COLUMNS = (
    "ride_id",
    "rideable_type",
    "started_at",
    "ended_at",
    "start_station_name",
    "start_station_id",
    "end_station_name",
    "end_station_id",
    "start_lat",
    "start_lng",
    "end_lat",
    "end_lng",
    "member_casual",
)


def connection_details(database_url: str) -> tuple[str, str]:
    parsed_url = urlsplit(database_url)
    if parsed_url.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")

    host = parsed_url.hostname
    username = unquote(parsed_url.username or "")
    password = unquote(parsed_url.password or "")
    database = unquote(parsed_url.path.lstrip("/"))
    if not all((host, username, password, database)):
        raise ValueError(
            "DATABASE_URL must include a host, username, password, and database"
        )

    port = parsed_url.port or 5432
    encoded_username = parsed_url.netloc.rsplit("@", 1)[0].split(":", 1)[0]
    safe_netloc = encoded_username + "@" + parsed_url.netloc.rsplit("@", 1)[-1]
    query = parse_qsl(parsed_url.query, keep_blank_values=True)
    if not any(key == "sslmode" for key, _ in query):
        query.append(("sslmode", "require"))
    safe_url = urlunsplit(
        (
            parsed_url.scheme,
            safe_netloc,
            parsed_url.path,
            urlencode(query),
            "",
        )
    )

    def escape_pgpass(value: str) -> str:
        return value.replace("\\", "\\\\").replace(":", "\\:")

    pgpass_entry = ":".join(
        escape_pgpass(value)
        for value in (host, str(port), database, username, password)
    )
    return safe_url, pgpass_entry


def main() -> None:
    load_dotenv(ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is missing from .env")
    if not CSV_PATH.is_file():
        raise FileNotFoundError(f"CSV file not found: {CSV_PATH}")

    with CSV_PATH.open("r", newline="", encoding="utf-8-sig") as csv_file:
        header = next(csv.reader(csv_file), None)
    if header != list(COLUMNS):
        raise ValueError(
            f"Unexpected CSV header in {CSV_PATH}; "
            f"expected: {', '.join(COLUMNS)}"
        )

    psql = shutil.which("psql")
    if psql is None:
        raise FileNotFoundError("psql CLI not found; install PostgreSQL command-line tools")

    safe_url, pgpass_entry = connection_details(database_url)
    csv_path = str(CSV_PATH).replace("'", "''")
    copy_command = (
        f"\\copy {TABLE_NAME} ({', '.join(COLUMNS)}) "
        f"FROM '{csv_path}' "
        "WITH (FORMAT csv, HEADER true)\n"
    )

    pgpass_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False
        ) as pgpass_file:
            pgpass_file.write(pgpass_entry + "\n")
            pgpass_path = Path(pgpass_file.name)
        os.chmod(pgpass_path, 0o600)

        environment = os.environ.copy()
        environment["PGPASSFILE"] = str(pgpass_path)
        subprocess.run(
            [
                psql,
                "--no-psqlrc",
                "--set",
                "ON_ERROR_STOP=1",
                "--dbname",
                safe_url,
                "--file",
                "-",
            ],
            input=copy_command,
            text=True,
            check=True,
            env=environment,
        )
    finally:
        if pgpass_path is not None:
            pgpass_path.unlink(missing_ok=True)

    print(f"Copied {CSV_PATH.name} into {TABLE_NAME}.")


if __name__ == "__main__":
    main()
