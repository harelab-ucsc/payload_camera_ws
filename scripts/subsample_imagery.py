#!/usr/bin/env python3

from pathlib import Path
import argparse
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Copy every Nth file from a source directory to a destination directory."
    )
    parser.add_argument("src", type=Path, help="Source directory")
    parser.add_argument("dst", type=Path, help="Destination directory")
    parser.add_argument(
        "n",
        type=int,
        help="Copy every Nth file (e.g. 10 copies files 0, 10, 20, ...)",
    )
    parser.add_argument(
        "--contains",
        type=str,
        default=None,
        help="Only consider files whose names contain this string.",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Starting index (default: 0)",
    )

    args = parser.parse_args()

    if not args.src.is_dir():
        sys.exit(f"Error: '{args.src}' is not a directory.")

    if args.n <= 0:
        sys.exit("Error: n must be greater than 0.")

    args.dst.mkdir(parents=True, exist_ok=True)

    files = sorted(
        f for f in args.src.iterdir()
        if f.is_file()
        and (
            args.contains is None
            or args.contains in f.name
        )
    )

    selected = files[args.offset::args.n]

    for file in selected:
        shutil.copy2(file, args.dst / file.name)
        print(f"Copied: {file.name}")

    print(f"\nCopied {len(selected)} of {len(files)} files.")


if __name__ == "__main__":
    main()
