#!/usr/bin/env python3

import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch paper screening via API.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--batch-id", required=True)
    return parser.parse_args(argv)


def main() -> None:
    parse_args()


if __name__ == "__main__":
    main()
