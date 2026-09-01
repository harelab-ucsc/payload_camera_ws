#!/usr/bin/env python3

import argparse
import csv
from collections import defaultdict
import json
import re
from pathlib import Path

import h5py
import numpy as np
import pycolmap

from hloc import (
    extract_features,
    match_features,
    pairs_from_retrieval,
)
from hloc.utils.io import get_keypoints, get_matches

from hloc_mask_features import apply_masks_to_features

CAMERA_RE = re.compile(r"camera(\d+)", re.IGNORECASE)

QUERY_PREFIX = "yard_"


def namespace_top_level_groups(h5_path: Path, prefix: str) -> Path:
    """Rename every top-level group in an HLoc feature h5 file by prepending
    `prefix` to it.

    The query and reference datasets both use cameraN/imageNNNN.jpeg naming
    that restarts from image0001 for every capture, so their names can
    collide (e.g. both may have a "camera2/image0230.jpeg", two unrelated
    photos). HLoc's retrieval/matching utilities (pairs_from_retrieval's
    self-match filter, match_features' (i, j)/(j, i) pair-cache folding)
    assume query and reference names share one unique namespace; an
    unprefixed collision silently drops or misattributes correspondences
    between an unrelated query/reference pair. Namespacing every query-side
    name makes it impossible for it to ever equal a reference-side name.
    """
    with h5py.File(h5_path, "r+") as f:
        for name in list(f.keys()):
            if name.startswith(prefix):
                continue
            target = prefix + name
            # On a re-run, hloc re-extracts under the original (unprefixed)
            # name because it only sees the prefixed groups from last time.
            # The freshly extracted group is authoritative, so drop the stale
            # prefixed one before renaming.
            if target in f:
                del f[target]
            f.move(name, target)
    return h5_path

def camera_number(name: str) -> int:
    """Extract the physical camera number from cameraN or yard_cameraN."""
    match = CAMERA_RE.search(name)

    if match is None:
        raise ValueError(f"Could not infer camera number from: {name}")

    return int(match.group(1))


def get_reference_camera_ids(reconstruction):
    """
    Map physical camera number -> COLMAP camera ID.

    We infer the physical camera from registered reference image names rather
    than assuming that COLMAP camera ID N means physical camera N.
    """
    mapping = {}

    for image in reconstruction.images.values():
        image_path = Path(image.name)

        if len(image_path.parts) < 2:
            continue

        physical_camera = camera_number(image_path.parts[0])
        camera_id = image.camera_id

        if physical_camera in mapping:
            if mapping[physical_camera] != camera_id:
                raise RuntimeError(
                    f"Physical camera {physical_camera} maps to multiple "
                    f"COLMAP camera IDs"
                )
        else:
            mapping[physical_camera] = camera_id

    return mapping


def get_query_camera_dirs(query_images):
    """Map physical camera number -> query image directory."""
    mapping = {}

    for directory in sorted(query_images.iterdir()):
        if not directory.is_dir():
            continue

        try:
            physical_camera = camera_number(directory.name)
        except ValueError:
            continue

        if physical_camera in mapping:
            raise RuntimeError(
                f"Multiple query directories found for camera "
                f"{physical_camera}"
            )

        mapping[physical_camera] = directory

    return mapping

def group_queries_by_frame(query_names):
    """
    Group query images by frame name, which is the filename without the camera
    directory. For example, the following query images would be grouped together:
    - images/camera1/image001.jpeg
    - images/camera2/image001.jpeg
    Would be grouped under the frame name "image001.jpeg".
    """
    frames = defaultdict(dict)
    for name in query_names:
        path = Path(name)
        camera_name = path.parent.name
        frame_name = path.name
        frames[frame_name][camera_name] = name
    return frames

def get_query_correspondences(
        reconstruction,
        query_name,
        db_ids,
        features_path,
        matches_path,
):
    """
    Build 2D-3D correspondences for a query image using the reference reconstruction.

    Returns:
        - points2D: Nx2 array of 2D points in the query image
        - points3D: Nx3 array of corresponding 3D points in the reference reconstruction
        - point3D_ids: N array of 3D point IDs in the reference reconstruction
        - num_matches: total raw query-reference matches considered (before filtering by 3D points)
    """
    kpq = get_keypoints(features_path, query_name)
    kpq += 0.5  # COLMAP coordinates

    kp_idx_to_3D = defaultdict(list)
    num_matches = 0
    for db_id in db_ids:
        image = reconstruction.images[db_id]
        if image.num_points3D == 0:
            continue
        points3D_ids = np.array(
            [p.point3D_id if p.has_point3D() else -1 for p in image.points2D]
        )

        matches, _ = get_matches(matches_path, query_name, image.name)
        valid_matches = points3D_ids[matches[:, 1]] != -1
        matches = matches[valid_matches]
        num_matches += len(matches)

        for query_idx, ref_idx in matches:
            point3D_id = points3D_ids[ref_idx]
            # avoid duplicate observations
            if point3D_id not in kp_idx_to_3D[query_idx]:
                kp_idx_to_3D[query_idx].append(point3D_id)

    query_idxs = []
    point3D_ids = []

    for query_idx, ids in kp_idx_to_3D.items():
        for point3D_id in ids:
            query_idxs.append(query_idx)
            point3D_ids.append(point3D_id)

    points2D = kpq[query_idxs]
    points3D = np.array([
        reconstruction.points3D[pid].xyz for pid in point3D_ids
    ])

    log = {
        "points2D": points2D,
        "points3D": points3D,
        "point3D_ids": np.asarray(point3D_ids),
        "num_matches": num_matches,
    }
    return log

def load_retrieval_ids(pairs_path, reconstruction):
    """Map each query image to its retrieved reference image IDs in the reconstruction."""
    name_to_id = {image.name: image.image_id for image in reconstruction.images.values()}
    retrieval = defaultdict(list)
    with open(pairs_path, "r") as f:
        for line in f:
            query_name, ref_name = line.strip().split()
            retrieval[query_name].append(name_to_id[ref_name])
    return retrieval

def get_rig_cameras(reconstruction):
    """Return rig cameras ordered by physical camera number."""
    camera_ids = get_reference_camera_ids(reconstruction)
    return [
        reconstruction.cameras[camera_ids[x]]
        for x in sorted(camera_ids)
    ]

def get_camera_index_map(reconstruction):
    """Map physical camera number to its index in the ordered rig cameras."""
    camera_ids = get_reference_camera_ids(reconstruction)
    camera_numbers = sorted(camera_ids)
    return {num: idx for idx, num in enumerate(camera_numbers)}

def load_cameras_from_rig(rig_config_path):
    """Load cameras from a rig configuration file."""
    config = json.loads(rig_config_path.read_text())
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
            np.asarray(tvec)
        )

    return [by_camera[number] for number in sorted(by_camera)]

def localize_rig_frame(frame_queries, context):
    reconstruction = context["reconstruction"]
    retrieval = context["retrieval"]
    features_path = context["features_path"]
    matches_path = context["matches_path"]
    cameras = context["cameras"]
    cams_from_rig = context["cams_from_rig"]
    camera_index_map = context["camera_index_map"]

    all_points2D = []
    all_points3D = []
    all_camera_idxs = []

    per_camera = {}

    for camera_name, query_name in sorted(frame_queries.items()):
        physical_camera = camera_number(camera_name)
        camera_idx = camera_index_map[physical_camera]

        db_ids = retrieval[query_name]

        corrs = get_query_correspondences(
            reconstruction,
            query_name,
            db_ids,
            features_path,
            matches_path,
        )
        n = len(corrs["points2D"])

        per_camera[camera_name] = {
            "num_correspondences": n,
            "num_matches": corrs["num_matches"],

        }

        if n == 0:
            continue

        all_points2D.append(corrs["points2D"])
        all_points3D.append(corrs["points3D"])
        all_camera_idxs.append(np.full(n, camera_idx, dtype=int))

    if not all_points2D:
        return None, per_camera

    points2D = np.concatenate(all_points2D, axis=0)
    points3D = np.concatenate(all_points3D, axis=0)
    camera_idxs = [int(i) for i in np.concatenate(all_camera_idxs)]

    ransac_options = pycolmap.RANSACOptions(
        max_error=12.0,
    )

    ret = pycolmap.estimate_and_refine_generalized_absolute_pose(
        points2D,
        points3D,
        camera_idxs,
        cams_from_rig,
        cameras,
        estimation_options=ransac_options,
    )

    return ret, per_camera

def quaternion_to_rotation(qw, qx, qy, qz):
    """Convert a wxyz quaternion to a 3x3 rotation matrix."""
    q = np.array([qw, qx, qy, qz], dtype=float)
    q /= np.linalg.norm(q)

    w, x, y, z = q

    return np.array([
        [
            1 - 2 * (y * y + z * z),
            2 * (x * y - z * w),
            2 * (x * z + y * w),
        ],
        [
            2 * (x * y + z * w),
            1 - 2 * (x * x + z * z),
            2 * (y * z - x * w),
        ],
        [
            2 * (x * z - y * w),
            2 * (y * z + x * w),
            1 - 2 * (x * x + y * y),
        ],
    ])

def write_summary(results_path, output_path):
    """Write a human-readable summary of rig localization poses."""
    poses = []

    # NOTE: write_results packs qw,qx,qy,qz and tx,ty,tz as single
    # whitespace-separated CSV fields (not one field per component), so this
    # must be parsed as CSV plus a secondary whitespace split, not by
    # splitting the raw line on whitespace alone.
    with open(results_path, newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header

        for row in reader:
            name = row[0]
            qw, qx, qy, qz = (float(v) for v in row[1].split())
            tx, ty, tz = (float(v) for v in row[2].split())

            rotation = quaternion_to_rotation(qw, qx, qy, qz)
            translation = np.array([tx, ty, tz])

            center = -rotation.T @ translation
            poses.append((name, center))

    if not poses:
        output_path.write_text("No localized poses.\n")
        return

    centers = np.array([
        center
        for _, center in poses
    ])

    norms = np.linalg.norm(centers, axis=1)

    lines = [
        "Rig localization summary",
        "========================",
        "",
        f"Rig poses: {len(poses)}",
        "",
        "Distance from SfM origin",
        "------------------------",
        (
            "|C| = distance of the estimated rig center from the "
            "SfM world origin [reconstruction units]"
        ),
    ]

    for percentile in [0, 10, 25, 50, 75, 90, 95, 99, 100]:
        value = np.percentile(norms, percentile)
        lines.append(f"p{percentile:02}: {value:.3f}")

    lines.extend([
        "",
        "Potential spatial outliers",
        "--------------------------",
    ])

    ranked = sorted(
        zip(poses, norms),
        key=lambda item: item[1],
        reverse=True,
    )

    for (name, center), norm in ranked[:5]:
        lines.append(
            f"{name:16s} "
            f"|C|={norm:9.3f}  "
            f"C=[{center[0]:9.3f}, "
            f"{center[1]:9.3f}, "
            f"{center[2]:9.3f}]"
        )

    output_path.write_text("\n".join(lines) + "\n")


def write_results(results_path, frames, context):
    """Localize each rig frame and write per-frame results to a CSV file."""
    num_successes = 0

    with open(results_path, "w") as f:
        f.write(
            "frame,"
            "qw,qx,qy,qz,tx,ty,tz,"
            "num_inliers,total_corrs,inlier_ratio,"
            "cam1_corr,cam2_corr,cam3_corr,cam4_corr,"
            "cam1_matches,cam2_matches,cam3_matches,cam4_matches\n"
        )

        for frame_name, frame_queries in sorted(frames.items()):
            ret, camera_log = localize_rig_frame(frame_queries, context)
            if ret is None:
                print(f"Frame {frame_name}: localization failed")
                continue

            num_inliers = ret.get("num_inliers", -1)

            corrs = {}
            matches = {}

            for camera_name, info in camera_log.items():
                number = camera_number(camera_name)
                corrs[number] = info["num_correspondences"]
                matches[number] = info["num_matches"]

            rig_from_world = ret["rig_from_world"]
            q = rig_from_world.rotation.quat
            t = rig_from_world.translation
            qx, qy, qz, qw = q

            total_corrs = sum(corrs.values())
            inlier_ratio = num_inliers / total_corrs if total_corrs > 0 else 0.0

            f.write(
                f"{frame_name},"
                f"{qw} {qx} {qy} {qz},"
                f"{t[0]} {t[1]} {t[2]},"
                f"{num_inliers}, {total_corrs}, {inlier_ratio},"
                f"{corrs.get(1, 0)},{corrs.get(2, 0)},"
                f"{corrs.get(3, 0)},{corrs.get(4, 0)},"
                f"{matches.get(1, 0)},{matches.get(2, 0)},"
                f"{matches.get(3, 0)},{matches.get(4, 0)}\n"
            )
            num_successes += 1

    return num_successes


parser = argparse.ArgumentParser()

parser.add_argument(
    "--query_dir",
    type=Path,
    required=True,
    help="Postprocessed query dataset root containing images/ and masks/",
)

parser.add_argument(
    "--reference_dir",
    type=Path,
    required=True,
    help="Postprocessed reference dataset root containing outputs/",
)

parser.add_argument(
    "--output_dir",
    type=Path,
    required=True,
    help="Directory in which to save localization results",
)

args = parser.parse_args()

# -- Dataset paths -------------------------------------------------------------

query_dataset = args.query_dir
reference_dataset = args.reference_dir
outputs = args.output_dir

query_images = query_dataset / "images"
query_masks = query_dataset / "masks"
reference_outputs = reference_dataset / "outputs"

if not query_images.is_dir():
    raise FileNotFoundError(f"Missing query images: {query_images}")

if not query_masks.is_dir():
    raise FileNotFoundError(f"Missing query masks: {query_masks}")

if not reference_outputs.is_dir():
    raise FileNotFoundError(f"Missing reference outputs: {reference_outputs}")

outputs.mkdir(exist_ok=True, parents=True)

# -- Existing reference reconstruction artifacts -------------------------------

reference_sfm = (
    reference_outputs
    / "sfm_superpoint+superglue"
)

reference_features = (
    reference_outputs
    / "feats-superpoint-n4096-r1024_masked.h5"
)

reference_descriptors = (
    reference_outputs
    / "global-feats-netvlad.h5"
)

for path in (
    reference_sfm,
    reference_features,
    reference_descriptors,
):
    if not path.exists():
        raise FileNotFoundError(f"Missing reference artifact: {path}")

# -- New query artifacts -------------------------------------------------------

raw_query_features = outputs / "query_superpoint_raw.h5"
query_features = outputs / "query_superpoint.h5"
query_descriptors = outputs / "query_netvlad.h5"

loc_pairs = outputs / "pairs-query-netvlad20.txt"
loc_matches = outputs / "matches-query-superglue.h5"

# -- HLoc configurations used by reference reconstruction ----------------------

retrieval_conf = extract_features.confs["netvlad"]
feature_conf = extract_features.confs["superpoint_aachen"]
matcher_conf = match_features.confs["superglue"]


# 1. Extract raw query SuperPoint features -------------------------------------

raw_query_features = extract_features.main(
    feature_conf,
    query_images,
    outputs,
    feature_path=raw_query_features,
)

# 2. Apply postproc masks to local query features ------------------------------

query_features = apply_masks_to_features(
    raw_query_features,
    query_features,
    query_masks,
    overwrite=True,
)
namespace_top_level_groups(query_features, QUERY_PREFIX)

# 3. Extract NetVLAD descriptors from original query images --------------------

query_descriptors = extract_features.main(
    retrieval_conf,
    query_images,
    outputs,
    feature_path=query_descriptors,
)
namespace_top_level_groups(query_descriptors, QUERY_PREFIX)

# 4. Retrieve the 20 most similar reference images for each query image --------

pairs_from_retrieval.main(
    query_descriptors,
    loc_pairs,
    num_matched=20,
    db_model=reference_sfm,
    db_descriptors=reference_descriptors,
)

# 5. SuperGlue: match masked query features vs masked reference features -------

loc_matches = match_features.main(
    matcher_conf,
    loc_pairs,
    query_features,
    export_dir=outputs,
    matches=loc_matches,
    features_ref=reference_features,
)

# 6. Load reference reconstruction ---------------------------------------------

reconstruction = pycolmap.Reconstruction(reference_sfm)

# 7. Localize ------------------------------------------------------------------

retrieval = load_retrieval_ids(loc_pairs, reconstruction)
query_names = sorted(retrieval.keys())
frames = group_queries_by_frame(query_names)

cameras = get_rig_cameras(reconstruction)
camera_index_map = get_camera_index_map(reconstruction)

cams_from_rig = load_cameras_from_rig(reference_dataset / "rig_config.json")
results = outputs / "localization_results.csv"
summary = outputs / "localization_summary.txt"

localization_context = {
    "reconstruction": reconstruction,
    "retrieval": retrieval,
    "features_path": query_features,
    "matches_path": loc_matches,
    "cameras": cameras,
    "cams_from_rig": cams_from_rig,
    "camera_index_map": camera_index_map,
}

num_successes = write_results(results, frames, localization_context)
write_summary(results, summary)

print(f"Localized {num_successes}/{len(frames)} rig frames successfully.")
print(f"Summary: {summary}")
print(f"Results: {results}")