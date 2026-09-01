#!/usr/bin/env python3
"""Visual QA for the reconstruction / localization pipeline.

Three modes, all writing PNGs to --output_dir:

  sfm      Reference reconstruction keypoints, coloured by visibility or
           track length. Sanity-checks reconstruction quality.

  loc      Query-vs-reference correspondences for localized frames, drawn by
           hloc's own visualize_loc_from_log and coloured by PnP inlier
           status. Reads the "<results>_logs.pkl" that hloc_localize2.py
           writes.

  gcp      Reprojects the surveyed AprilTag GCP into every query image that
           saw the tag, and draws it against the detected tag centre. The
           pixel gap is a per-image accuracy metric that is independent of
           the triangulation step in validate_gcp_apriltag.py.
"""

import argparse
import csv
import json
import pickle
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pycolmap

from hloc.utils.io import read_image
from hloc.utils.viz import add_text, plot_images, save_plot
from hloc.visualization import visualize_loc_from_log, visualize_sfm_2d

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

QUERY_PREFIX = "yard_"


def load_rig_intrinsics(rig_config_path):
    """Map physical camera number -> OPENCV params [fx,fy,cx,cy,k1,k2,p1,p2]."""
    config = json.loads(Path(rig_config_path).read_text())
    return {
        camera_number(e["image_prefix"]): np.asarray(e["camera_params"], dtype=np.float64)
        for e in config[0]["cameras"]
    }


def intrinsics_to_cv(params):
    fx, fy, cx, cy, k1, k2, p1, p2 = params
    K = np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]])
    dist = np.array([k1, k2, p1, p2])
    return K, dist


def load_gcp_truth(click_gcps_csv):
    """Average the quality-2 rows. Column 2 is the WGS84 ellipsoid height."""
    rows = []
    with open(click_gcps_csv, newline="") as f:
        for row in csv.reader(f):
            if not row:
                continue
            if int(row[4]) != 2:
                continue
            rows.append((float(row[0]), float(row[1]), float(row[2])))
    if not rows:
        raise RuntimeError(f"No quality-2 GCP rows in {click_gcps_csv}")
    return np.mean(np.asarray(rows), axis=0)


def detect_tag(image_path):
    """Return (corners 4x2, tag_id, family) for the first tag found, else None."""
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    for family, dict_id in APRILTAG_DICTS:
        detector = cv2.aruco.ArucoDetector(
            cv2.aruco.getPredefinedDictionary(dict_id),
            cv2.aruco.DetectorParameters(),
        )
        corners, ids, _ = detector.detectMarkers(image)
        if ids is not None and len(ids):
            return corners[0].reshape(4, 2), int(ids.flatten()[0]), family
    return None


def project_point(point_world, cam_from_world, params):
    """Project a world (SfM-frame) point into a camera. Returns (px, depth)."""
    point_cam = cam_from_world * point_world.reshape(1, 3)
    point_cam = np.asarray(point_cam).reshape(3)
    if point_cam[2] <= 0:
        return None, point_cam[2]
    K, dist = intrinsics_to_cv(params)
    px, _ = cv2.projectPoints(
        point_cam.reshape(1, 1, 3),
        np.zeros(3),
        np.zeros(3),
        K,
        dist,
    )
    return px.reshape(2), point_cam[2]


# -- modes ---------------------------------------------------------------------


def mode_sfm(args, out_dir):
    sfm_dir = args.reference_dir / "outputs" / "sfm_superpoint+superglue"
    reconstruction = pycolmap.Reconstruction(sfm_dir)
    image_ids = sorted(reconstruction.reg_image_ids())
    step = max(1, len(image_ids) // args.num_frames)
    selected = image_ids[::step][: args.num_frames]

    for color_by in ("visibility", "track_length"):
        for image_id in selected:
            name = reconstruction.images[image_id].name.replace("/", "_")
            visualize_sfm_2d(
                reconstruction,
                args.reference_dir / "images",
                color_by=color_by,
                selected=[image_id],
                dpi=args.dpi,
            )
            path = out_dir / f"sfm_{color_by}_{name}.png"
            save_plot(path)
            plt.close("all")
            print(f"  wrote {path}")


def mode_loc(args, out_dir):
    """Render localization correspondences using hloc's own visualizer.

    hloc_localize2.py writes "<results>_logs.pkl" in hloc's log format, so
    hloc.visualization.visualize_loc_from_log can draw the query/reference
    correspondences coloured by PnP inlier status (red = outlier, green =
    inlier) without any custom rendering here.
    """
    results = args.localization_dir / "localization_results.csv"
    logs_path = Path(f"{results}_logs.pkl")
    if not logs_path.is_file():
        print(f"  {logs_path} not found -- re-run hloc_localize2.py to generate it")
        return

    with open(logs_path, "rb") as f:
        logs = pickle.load(f)["loc"]

    reconstruction = pycolmap.Reconstruction(
        args.reference_dir / "outputs" / "sfm_superpoint+superglue"
    )

    # prefer the query images with the most inliers
    ranked = sorted(
        logs.items(),
        key=lambda kv: -int(np.sum(kv[1]["PnP_ret"]["inlier_mask"])),
    )
    selected = [name for name, _ in ranked[: args.num_frames]]

    for qname in selected:
        visualize_loc_from_log(
            args.query_dir / "images",
            qname,
            logs[qname],
            reconstruction=reconstruction,
            db_image_dir=args.reference_dir / "images",
            top_k_db=args.top_k_db,
            dpi=args.dpi,
        )
        stem = qname.replace("/", "_").replace(".jpeg", "")
        for i, num in enumerate(plt.get_fignums()):
            plt.figure(num)
            path = out_dir / f"loc_{stem}_db{i}.png"
            save_plot(path)
            print(f"  wrote {path}  (green = PnP inlier, red = outlier)")
        plt.close("all")


def mode_gcp(args, out_dir):
    enu_from_sfm, ref_lla = load_georef_transform(args.georef_transform)
    sfm_from_enu = enu_from_sfm.inverse()
    gps = pycolmap.GPSTransform()

    gcp_lla = load_gcp_truth(args.click_gcps_csv)
    gcp_enu = gps.ellipsoid_to_enu(gcp_lla.reshape(1, 3), *ref_lla)[0]
    gcp_sfm = np.asarray(sfm_from_enu * gcp_enu.reshape(1, 3)).reshape(3)

    cams_from_rig = load_cameras_from_rig(args.reference_dir / "rig_config.json")
    intrinsics = load_rig_intrinsics(args.reference_dir / "rig_config.json")

    frames = {f["name"]: f for f in
              read_localization_results(args.localization_dir / "localization_results.csv")}

    records = []
    for name, frame in sorted(frames.items()):
        if frame["num_inliers"] < args.min_inliers:
            continue
        for cam in sorted(intrinsics):
            image_path = args.query_dir / "images" / f"camera{cam}" / name
            if not image_path.is_file():
                continue
            det = detect_tag(image_path)
            if det is None:
                continue
            corners, tag_id, family = det
            detected = corners.mean(axis=0)

            cam_from_world = cams_from_rig[cam] * frame["rig_from_world"]
            projected, depth = project_point(gcp_sfm, cam_from_world, intrinsics[cam])
            if projected is None:
                continue

            err_px = float(np.linalg.norm(projected - detected))
            # approximate ground-distance equivalent of the pixel error
            fx = intrinsics[cam][0]
            range_m = float(depth) * enu_from_sfm.scale
            err_m = err_px * range_m / fx

            records.append({
                "frame": name, "camera": cam, "tag_id": tag_id,
                "detected": detected, "projected": projected,
                "err_px": err_px, "err_m": err_m, "range_m": range_m,
                "image_path": image_path, "corners": corners,
            })

    if not records:
        print("  no AprilTag detections among localized frames; nothing to draw")
        return

    records.sort(key=lambda r: r["err_px"])
    errs_px = np.array([r["err_px"] for r in records])
    errs_m = np.array([r["err_m"] for r in records])

    print(f"  {len(records)} tag detections in localized frames "
          f"(tag id {records[0]['tag_id']}, family 36h11)")
    print("  GCP reprojection error [px]:  " + "  ".join(
        f"p{p}={np.percentile(errs_px, p):.1f}" for p in (0, 25, 50, 75, 100)))
    print("  equivalent ground error [m]:  " + "  ".join(
        f"p{p}={np.percentile(errs_m, p):.2f}" for p in (0, 25, 50, 75, 100)))

    # draw the best, median and worst cases plus a spread up to --num_frames
    idxs = np.unique(np.linspace(0, len(records) - 1, args.num_frames).astype(int))
    for i in idxs:
        r = records[i]
        image = read_image(r["image_path"])
        h, w = image.shape[:2]
        plot_images([image], dpi=args.dpi)
        ax = plt.gcf().axes[0]
        poly = np.vstack([r["corners"], r["corners"][:1]])
        ax.plot(poly[:, 0], poly[:, 1], c="lime", lw=1.5)
        ax.scatter(*r["detected"], c="lime", s=60, marker="o",
                   label="detected AprilTag centre")

        off_frame = not (0 <= r["projected"][0] < w and 0 <= r["projected"][1] < h)
        # Clamp everything we draw to the image bounds, otherwise matplotlib
        # expands the axes to fit an off-frame point and the image no longer
        # fills the figure.
        marker_at = np.clip(r["projected"], [0, 0], [w - 1, h - 1])
        ax.plot([r["detected"][0], marker_at[0]],
                [r["detected"][1], marker_at[1]], c="yellow", lw=1.2)
        if off_frame:
            ax.scatter(*marker_at, c="red", s=120, marker="X",
                       edgecolors="white", linewidths=0.8,
                       label="surveyed GCP, reprojected (OFF-FRAME)")
        else:
            ax.scatter(*marker_at, c="red", s=80, marker="x",
                       label="surveyed GCP, reprojected")
        # plot_images sizes the axes to the image; keep it that way
        ax.set_xlim(0, w)
        ax.set_ylim(h, 0)
        ax.legend(loc="lower right", fontsize=5, framealpha=0.7)
        add_text(0, f"{r['frame']} camera{r['camera']}   "
                    f"error = {r['err_px']:.1f} px  (~{r['err_m']:.2f} m at "
                    f"{r['range_m']:.1f} m range)"
                    + ("   [reprojection lands outside the image]" if off_frame else ""))
        path = out_dir / f"gcp_{r['err_px']:07.1f}px_{r['frame'].replace('.jpeg','')}_cam{r['camera']}.png"
        save_plot(path)
        plt.close("all")
        print(f"  wrote {path}")

    summary = out_dir / "gcp_reprojection_errors.csv"
    with open(summary, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "camera", "err_px", "err_m", "range_m",
                    "detected_x", "detected_y", "projected_x", "projected_y"])
        for r in records:
            w.writerow([r["frame"], r["camera"], f"{r['err_px']:.2f}",
                        f"{r['err_m']:.3f}", f"{r['range_m']:.2f}",
                        f"{r['detected'][0]:.1f}", f"{r['detected'][1]:.1f}",
                        f"{r['projected'][0]:.1f}", f"{r['projected'][1]:.1f}"])
    print(f"  wrote {summary}")


MODES = {"sfm": mode_sfm, "loc": mode_loc, "gcp": mode_gcp}

parser = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--mode", choices=list(MODES) + ["all"], default="all")
parser.add_argument("--query_dir", type=Path, required=True)
parser.add_argument("--reference_dir", type=Path, required=True)
parser.add_argument("--localization_dir", type=Path, required=True)
parser.add_argument("--georef_transform", type=Path)
parser.add_argument("--click_gcps_csv", type=Path)
parser.add_argument("--output_dir", type=Path, required=True)
parser.add_argument("--num_frames", type=int, default=6)
parser.add_argument("--min_inliers", type=int, default=50,
                    help="skip frames whose rig pose has fewer inliers than this")
parser.add_argument("--top_k_db", type=int, default=1,
                    help="reference images to show per query image (loc mode)")
parser.add_argument("--dpi", type=int, default=150)
args = parser.parse_args()

args.output_dir.mkdir(parents=True, exist_ok=True)

selected_modes = list(MODES) if args.mode == "all" else [args.mode]
for name in selected_modes:
    if name == "gcp" and not (args.georef_transform and args.click_gcps_csv):
        print(f"[{name}] skipped: needs --georef_transform and --click_gcps_csv")
        continue
    print(f"[{name}]")
    MODES[name](args, args.output_dir)
