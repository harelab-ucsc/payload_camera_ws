#!/usr/bin/env python3
"""Validate the georeferenced yard localization against a surveyed AprilTag GCP.

Detects an AprilTag in the localized yard query images, triangulates its 3D
position from the localized rig poses (in the reference reconstruction's SfM
frame), georeferences that point, and compares it against the surveyed GCP
in click_gcps.csv.
"""

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pycolmap

from georef_common import (
    camera_number,
    load_cameras_from_rig,
    load_georef_transform,
    read_localization_results,
)

APRILTAG_DICTS = [
    ("36h11", cv2.aruco.DICT_APRILTAG_36h11),
    ("25h9", cv2.aruco.DICT_APRILTAG_25h9),
    ("16h5", cv2.aruco.DICT_APRILTAG_16h5),
    ("36h10", cv2.aruco.DICT_APRILTAG_36h10),
]


def load_rig_intrinsics(rig_config_path):
    """Map physical camera number -> OPENCV camera_params [fx,fy,cx,cy,k1,k2,p1,p2]."""
    config = json.loads(Path(rig_config_path).read_text())
    assert len(config) == 1, f"Expected a single rig in {rig_config_path}"

    intrinsics = {}
    for entry in config[0]["cameras"]:
        assert entry["camera_model_name"] == "OPENCV", (
            f"Unsupported camera model: {entry['camera_model_name']}"
        )
        number = camera_number(entry["image_prefix"])
        intrinsics[number] = np.asarray(entry["camera_params"], dtype=np.float64)

    return intrinsics


def load_gcp_truth(click_gcps_csv):
    """Average the quality-2 surveyed GCP rows into a single (lat, lon, alt).

    The CSV carries two altitudes that differ by ~30.7m, the local geoid
    separation: column 2 (~-6.9) and column 3 (~23.8). Column 3 matches the
    site's elevation above sea level (WRP sits ~23-24m above MSL), so column
    2 is the WGS84 *ellipsoid* height. We use column 2 because
    GPSTransform.ellipsoid_to_enu() requires ellipsoid height, and because
    the INS lla[2] the image EXIF altitudes come from is also ellipsoid
    height. Using column 3 instead puts the tag ~26m off vertically.
    """
    rows = []
    with open(click_gcps_csv, newline="") as f:
        for row in csv.reader(f):
            if not row:
                continue
            lat, lon, alt, quality = float(row[0]), float(row[1]), float(row[2]), int(row[4])
            if quality != 2:
                continue
            rows.append((lat, lon, alt))

    if not rows:
        raise RuntimeError(f"No quality-2 GCP rows found in {click_gcps_csv}")

    return np.mean(np.asarray(rows), axis=0)


def build_detector(dict_id):
    dictionary = cv2.aruco.getPredefinedDictionary(dict_id)
    params = cv2.aruco.DetectorParameters()
    return cv2.aruco.ArucoDetector(dictionary, params)


def detect_tag_center(image_path, detector):
    """Return the pixel (x, y) of the first detected AprilTag's center, or None."""
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    corners, ids, _ = detector.detectMarkers(image)
    if ids is not None and len(ids) > 0:
        return corners[0].reshape(4, 2).mean(axis=0)
    return None


def undistorted_ray_dir(pixel, camera_params):
    fx, fy, cx, cy, k1, k2, p1, p2 = camera_params
    K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]])
    dist = np.array([k1, k2, p1, p2])
    pts = np.array([[pixel]], dtype=np.float64)
    undist = cv2.undistortPoints(pts, K, dist)[0, 0]
    direction = np.array([undist[0], undist[1], 1.0])
    return direction / np.linalg.norm(direction)


def triangulate_rays(origins, directions):
    """Least-squares closest point to a set of 3D rays (origin, unit direction)."""
    A = np.zeros((3, 3))
    b = np.zeros(3)
    for o, d in zip(origins, directions):
        proj = np.eye(3) - np.outer(d, d)
        A += proj
        b += proj @ o
    point, *_ = np.linalg.lstsq(A, b, rcond=None)
    return point


parser = argparse.ArgumentParser()
parser.add_argument("--query_dir", type=Path, required=True, help="Postprocessed yard query dataset root")
parser.add_argument("--reference_dir", type=Path, required=True, help="Postprocessed roof reference dataset root (rig_config.json)")
parser.add_argument("--localization_dir", type=Path, required=True, help="Output directory from hloc_localize2.py")
parser.add_argument("--georef_transform", type=Path, required=True, help="Path to georef_transform.json")
parser.add_argument("--click_gcps_csv", type=Path, required=True, help="Path to click_gcps.csv")
args = parser.parse_args()

results_csv = args.localization_dir / "localization_results.csv"
frames = read_localization_results(results_csv)
print(f"{len(frames)} localized yard rig frames to search for the AprilTag.")

cams_from_rig_by_number = load_cameras_from_rig(args.reference_dir / "rig_config.json")
intrinsics = load_rig_intrinsics(args.reference_dir / "rig_config.json")
camera_numbers = sorted(intrinsics)

hits = []
used_family = None

for family_name, dict_id in APRILTAG_DICTS:
    detector = build_detector(dict_id)
    family_hits = []

    for frame in frames:
        for number in camera_numbers:
            image_path = args.query_dir / "images" / f"camera{number}" / frame["name"]
            if not image_path.is_file():
                continue
            pixel = detect_tag_center(image_path, detector)
            if pixel is not None:
                family_hits.append((frame, number, pixel))

    print(f"  tried AprilTag family {family_name}: {len(family_hits)} detection(s)")

    if family_hits:
        hits = family_hits
        used_family = family_name
        break

print()
if hits:
    print(f"AprilTag detected in {len(hits)} image(s) (family {used_family}):")
    for frame, number, pixel in hits:
        print(f"  {frame['name']} camera{number}  pixel=({pixel[0]:.1f}, {pixel[1]:.1f})")
else:
    print("AprilTag not detected in any localized yard query image.")

enu_from_sfm, ref_lla = load_georef_transform(args.georef_transform)
gps_transform = pycolmap.GPSTransform()

gcp_lla = load_gcp_truth(args.click_gcps_csv)
gcp_enu = gps_transform.ellipsoid_to_enu(gcp_lla.reshape(1, 3), *ref_lla)[0]

print()
print(f"Surveyed GCP (avg of quality-2 rows): lat={gcp_lla[0]:.9f} lon={gcp_lla[1]:.9f} alt={gcp_lla[2]:.3f}")
print(f"Surveyed GCP in ENU: {gcp_enu}")

# Drop detections whose rig pose itself is low-confidence -- a single
# badly-localized frame (few inliers) can dominate an unweighted
# least-squares triangulation.
MIN_INLIERS = 50
good_hits = [h for h in hits if h[0]["num_inliers"] >= MIN_INLIERS]
dropped = [h for h in hits if h[0]["num_inliers"] < MIN_INLIERS]

if dropped:
    print()
    print(f"Dropping {len(dropped)} detection(s) from low-confidence rig poses (< {MIN_INLIERS} inliers):")
    for frame, number, pixel in dropped:
        print(f"  {frame['name']} camera{number}  num_inliers={frame['num_inliers']}")

if len(good_hits) < 2:
    print()
    print(
        f"Only {len(good_hits)} high-confidence AprilTag detection(s) found -- "
        "cannot triangulate (need >= 2). No accuracy residual can be computed "
        "for this dataset."
    )
    raise SystemExit(0)

def build_rays(hits):
    origins, directions = [], []
    for frame, number, pixel in hits:
        cam_from_rig = cams_from_rig_by_number[number]
        cam_from_world = cam_from_rig * frame["rig_from_world"]

        ray_dir_cam = undistorted_ray_dir(pixel, intrinsics[number])
        ray_dir_world = cam_from_world.rotation.matrix().T @ ray_dir_cam
        ray_origin_world = cam_from_world.tgt_origin_in_src()

        origins.append(ray_origin_world)
        directions.append(ray_dir_world / np.linalg.norm(ray_dir_world))
    return origins, directions

origins, directions = build_rays(good_hits)
tag_sfm = triangulate_rays(origins, directions)

# Robustness pass: drop any ray that misses the initial estimate by more than
# 3x the median miss distance, then re-triangulate.
miss_dist = np.array([
    np.linalg.norm((tag_sfm - o) - np.dot(tag_sfm - o, d) * d)
    for o, d in zip(origins, directions)
])
threshold = 3 * np.median(miss_dist)
inlier_mask = miss_dist <= max(threshold, 1e-6)

if not inlier_mask.all():
    outlier_hits = [h for h, keep in zip(good_hits, inlier_mask) if not keep]
    print()
    print(f"Dropping {len(outlier_hits)} geometric outlier ray(s) (miss dist > 3x median):")
    for frame, number, pixel in outlier_hits:
        print(f"  {frame['name']} camera{number}")
    good_hits = [h for h, keep in zip(good_hits, inlier_mask) if keep]
    origins, directions = build_rays(good_hits)
    tag_sfm = triangulate_rays(origins, directions)

tag_enu = (enu_from_sfm * tag_sfm.reshape(1, 3))[0]
residual = np.linalg.norm(tag_enu - gcp_enu)

print()
print(f"Triangulated from {len(good_hits)} detection(s) across "
      f"{len(set(f['name'] for f, _, _ in good_hits))} frame(s).")
print(f"Triangulated AprilTag position (SfM frame): {tag_sfm}")
print(f"Triangulated AprilTag position (ENU):        {tag_enu}")
print(f"Residual vs surveyed GCP: {residual:.3f} m")
