"""Entry point for the ingestion job."""

import os


def main() -> None:
    host = os.environ["DATABRICKS_HOST"]
    token = os.getenv("DATABRICKS_TOKEN")
    if not token:
        raise SystemExit("DATABRICKS_TOKEN is required")
    print(f"connecting to {host}")


if __name__ == "__main__":
    main()
