from __future__ import annotations

import argparse
import logging
import sys

from retailpulse import pipeline
from retailpulse.config import Paths
from retailpulse.ingestion.download import RawDataExistsError
from retailpulse.ingestion.reader import SchemaError

logger = logging.getLogger("retailpulse")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="retailpulse", description="RetailPulse e-commerce analytics pipeline."
    )
    parser.add_argument("--log-level", default="INFO", help="Python logging level (default: INFO)")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="Acquire the raw dataset into data/raw")
    ingest.add_argument(
        "--source",
        choices=["auto", "uci", "synthetic"],
        default="auto",
        help="'auto' downloads UCI Online Retail and falls back to synthetic data on failure",
    )
    ingest.add_argument("--force", action="store_true", help="Replace an existing raw file")

    commands.add_parser("clean", help="Classify raw rows and write the processed layer")
    commands.add_parser("load", help="Rebuild the PostgreSQL staging and analytics schemas")
    commands.add_parser("sql", help="Run the SQL analyses and save their results as CSV")
    commands.add_parser("analyze", help="Compute the pandas analytics tables")
    commands.add_parser("export", help="Export the star schema for Power BI")

    run = commands.add_parser("run", help="Run every step in order")
    run.add_argument("--source", choices=["auto", "uci", "synthetic"], default="auto")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    paths = Paths()
    try:
        if args.command == "ingest":
            pipeline.ingest(paths, source=args.source, force=args.force)
        elif args.command == "clean":
            pipeline.clean(paths)
        elif args.command == "load":
            pipeline.load(paths)
        elif args.command == "sql":
            pipeline.run_sql(paths)
        elif args.command == "analyze":
            pipeline.analyze(paths)
        elif args.command == "export":
            pipeline.export(paths)
        elif args.command == "run":
            pipeline.run_all(paths, source=args.source)
    except (FileNotFoundError, RawDataExistsError, SchemaError) as error:
        logger.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
