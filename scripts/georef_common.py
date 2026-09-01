#!/usr/bin/env python3
"""Shared helpers for georeferencing the roof reconstruction and transforming
localized poses / ground-control points into that frame.
"""

import csv
import json
import re
from pathlib import Path

import numpy as np
import pycolmap

CAMERA_RE = re.compile(r"camera(\d+)", re.IGNORECASE)


def camera_number(name: str) -> int:
    """Extract the physical camera number from cameraN or yard_cameraN."""
    match = CAMERA_RE.search(name)

    if match is None:
        raise ValueError(f"Could not infer camera number from: {name}")

    return int(match.group(1))


def load_cameras_from_rig(rig_config_path):
    """Load cam_from_rig extrinsics from a rig configuration file.

    Returns a dict of physical camera number -> Rigid3d.
    """
    config = json.loads(Path(rig_config_path).read_text())
    if len(config) != 1:
        raise RuntimeError(f"Expected a single rig in {rig_config_path}, got {len(config)}")

    by_camera = {}

    for entry in config[0]["cameras"]:
        number = camera_number(entry["image_prefix"])
        if entry.get("ref_sensor", False):
            by_camera[number] = pycolmap.Rigid3d()
            continue
        # rig_config.json stores the quaternion as [w, x, y, z] (COLMAP's
        # convention, and what gen_rig_config.py writes), but pycolmap's
        # Rotation3d constructor expects [x, y, z, w]
        qw, qx, qy, qz = entry["cam_from_rig_rotation"]
        tvec = entry["cam_from_rig_translation"]
        by_camera[number] = pycolmap.Rigid3d(
            pycolmap.Rotation3d(np.array([qx, qy, qz, qw])),
            np.asarray(tvec),
        )

    return by_camera


def load_georef_transform(path):
    """Load a georef_transform.json written by georef_reconstruction.py.

    Returns (enu_from_sfm: Sim3d, ref_lla: (lat, lon, alt)).
    """
    data = json.loads(Path(path).read_text())

    rotation = pycolmap.Rotation3d(np.asarray(data["rotation_xyzw"]))
    sim3d = pycolmap.Sim3d(
        data["scale"],
        rotation,
        np.asarray(data["translation"]),
    )
    ref_lla = (data["ref_lat"], data["ref_lon"], data["ref_alt"])

    return sim3d, ref_lla


def _unpack_legacy_pose_fields(row):
    """Split the packed pose fields written by older hloc_localize2.py runs.

    write_results used to emit qw,qx,qy,qz and tx,ty,tz as two
    whitespace-joined fields even though the header named them as seven
    separate columns, so old files have 14 fields per row against a 19-column
    header. Splitting those two fields restores the column-for-column layout
    the header describes.
    """
    return [row[0], *row[1].split(), *row[2].split(), *row[3:]]


def read_localization_results(csv_path):
    """Parse localization_results.csv from hloc_localize2.py.

    Returns a list of dicts, one per successfully localized frame, with keys:
        name, rig_from_world (Rigid3d), num_inliers, total_corrs, inlier_ratio
    """
    frames = []

    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        header = [field.strip() for field in next(reader)]
        assert header[0] == "frame", f"Unexpected localization_results.csv header: {header}"

        for row in reader:
            if len(row) < len(header):
                row = _unpack_legacy_pose_fields(row)

            record = {key: value.strip() for key, value in zip(header, row)}

            name = record["frame"]
            qw, qx, qy, qz = (float(record[key]) for key in ("qw", "qx", "qy", "qz"))
            tx, ty, tz = (float(record[key]) for key in ("tx", "ty", "tz"))
            num_inliers = int(record["num_inliers"])
            total_corrs = int(record["total_corrs"])
            inlier_ratio = float(record["inlier_ratio"])

            rotation = pycolmap.Rotation3d(np.array([qx, qy, qz, qw]))
            rig_from_world = pycolmap.Rigid3d(rotation, np.array([tx, ty, tz]))

            frames.append({
                "name": name,
                "rig_from_world": rig_from_world,
                "num_inliers": num_inliers,
                "total_corrs": total_corrs,
                "inlier_ratio": inlier_ratio,
            })

    return frames
