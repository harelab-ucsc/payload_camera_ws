#!/usr/bin/env python3
"""Transform hloc_localize2.py rig poses into real-world lat/lon/alt.

Reads localization_results.csv (rig poses in the reference reconstruction's
arbitrary SfM frame) and a georef_transform.json (produced by
georef_reconstruction.py) and writes a georeferenced CSV of rig positions.
"""

import argparse
import csv
from pathlib import Path

import numpy as np
import pycolmap

from georef_common import load_georef_transform, read_localization_results

parser = argparse.ArgumentParser()
parser.add_argument(
    "--localization_dir",
    type=Path,
    required=True,
    help="Output directory from hloc_localize2.py (contains localization_results.csv)",
)
parser.add_argument(
    "--georef_transform",
    type=Path,
    required=True,
    help="Path to georef_transform.json from georef_reconstruction.py",
)
args = parser.parse_args()

results_csv = args.localization_dir / "localization_results.csv"

if not results_csv.is_file():
    raise FileNotFoundError(f"Missing localization results: {results_csv}")

enu_from_sfm, ref_lla = load_georef_transform(args.georef_transform)
gps_transform = pycolmap.GPSTransform()

frames = read_localization_results(results_csv)

if not frames:
    raise RuntimeError(f"No localized frames found in {results_csv}")

centers_sfm = np.array([f["rig_from_world"].tgt_origin_in_src() for f in frames])
centers_enu = enu_from_sfm * centers_sfm
centers_lla = gps_transform.enu_to_ellipsoid(centers_enu, *ref_lla)

out_path = args.localization_dir / "localized_poses_georeferenced.csv"

with open(out_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "frame", "lat", "lon", "alt",
        "enu_x", "enu_y", "enu_z",
        "num_inliers", "inlier_ratio",
    ])
    for frame, lla, enu in zip(frames, centers_lla, centers_enu):
        writer.writerow([
            frame["name"],
            f"{lla[0]:.9f}", f"{lla[1]:.9f}", f"{lla[2]:.3f}",
            f"{enu[0]:.3f}", f"{enu[1]:.3f}", f"{enu[2]:.3f}",
            frame["num_inliers"], f"{frame['inlier_ratio']:.4f}",
        ])

print(f"Wrote {len(frames)} georeferenced poses to {out_path}")
print()
print(f"lat range: [{centers_lla[:, 0].min():.7f}, {centers_lla[:, 0].max():.7f}]")
print(f"lon range: [{centers_lla[:, 1].min():.7f}, {centers_lla[:, 1].max():.7f}]")
print(f"alt range: [{centers_lla[:, 2].min():.2f}, {centers_lla[:, 2].max():.2f}]")
