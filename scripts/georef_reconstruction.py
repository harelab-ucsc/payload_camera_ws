#!/usr/bin/env python3
"""Georeference a reconstructed COLMAP model using per-image GPS EXIF.

Reads GPS EXIF from every registered image, converts it to a local ENU
frame, and fits a similarity transform (scale + rotation + translation)
that aligns the reconstruction to that frame. The transform is written to
outputs/georef_transform.json for reuse by downstream scripts.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pycolmap
from PIL import Image
from PIL.ExifTags import GPSTAGS


def dms_to_decimal(dms, ref):
    degrees, minutes, seconds = (float(x) for x in dms)
    value = degrees + minutes / 60.0 + seconds / 3600.0
    if ref in ("S", "W"):
        value = -value
    return value


def read_gps(image_path):
    """Return (lat, lon, alt) in degrees/meters, or None if no GPS EXIF."""
    with Image.open(image_path) as im:
        exif = im.getexif()
        gps_ifd = exif.get_ifd(0x8825)

    if not gps_ifd:
        return None

    tags = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}

    if "GPSLatitude" not in tags or "GPSLongitude" not in tags:
        return None

    lat = dms_to_decimal(tags["GPSLatitude"], tags.get("GPSLatitudeRef", "N"))
    lon = dms_to_decimal(tags["GPSLongitude"], tags.get("GPSLongitudeRef", "E"))
    alt = float(tags.get("GPSAltitude", 0.0))

    if tags.get("GPSAltitudeRef") in (1, b"\x01"):
        alt = -alt

    return lat, lon, alt


def print_percentiles(label, values):
    print(f"{label}")
    for p in (0, 25, 50, 75, 90, 100):
        print(f"  p{p:02}: {np.percentile(values, p):.3f}")


parser = argparse.ArgumentParser()
parser.add_argument(
    "--reference_dir",
    type=Path,
    required=True,
    help="Postprocessed reference dataset root containing images/ and outputs/",
)
parser.add_argument(
    "--max_align_error",
    type=float,
    default=5.0,
    help="RANSAC inlier threshold (meters) for the GPS alignment",
)
args = parser.parse_args()

reference_dir = args.reference_dir
images_dir = reference_dir / "images"
sfm_dir = reference_dir / "outputs" / "sfm_superpoint+superglue"

if not sfm_dir.is_dir():
    raise FileNotFoundError(f"Missing reference reconstruction: {sfm_dir}")

reconstruction = pycolmap.Reconstruction(sfm_dir)

image_names = []
sfm_centers = []
gps_lla = []
skipped = 0

for image in reconstruction.images.values():
    gps = read_gps(images_dir / image.name)
    if gps is None:
        skipped += 1
        continue
    image_names.append(image.name)
    sfm_centers.append(image.projection_center())
    gps_lla.append(gps)

if len(image_names) < 3:
    raise RuntimeError(
        f"Only {len(image_names)} registered images have GPS EXIF; need at least 3 to align."
    )

print(f"{len(image_names)} registered images have GPS EXIF ({skipped} without).")

sfm_centers = np.asarray(sfm_centers)
gps_lla = np.asarray(gps_lla)
ref_lat, ref_lon, ref_alt = gps_lla.mean(axis=0)

gps_transform = pycolmap.GPSTransform()
enu_targets = gps_transform.ellipsoid_to_enu(gps_lla, ref_lat, ref_lon, ref_alt)

ransac_options = pycolmap.RANSACOptions(max_error=args.max_align_error)
enu_from_sfm = pycolmap.align_reconstruction_to_locations(
    reconstruction,
    image_names,
    enu_targets,
    min_common_images=3,
    ransac_options=ransac_options,
)

if enu_from_sfm is None:
    raise RuntimeError("GPS alignment failed to find a valid transform.")

print()
print("Estimated similarity transform (ENU <- SfM):")
print(f"  scale:       {enu_from_sfm.scale:.6f}")
print(f"  rotation:    {enu_from_sfm.rotation.quat} (xyzw)")
print(f"  translation: {enu_from_sfm.translation}")

# -- Sanity check: round-trip each registered image's own SfM projection
# center through the transform and compare against the ENU position implied
# by that same image's own EXIF GPS fix. Residuals should be on the order of
# a few meters (consumer-GPS noise), not tens/hundreds of meters.
predicted_enu = enu_from_sfm * sfm_centers
residuals = np.linalg.norm(predicted_enu - enu_targets, axis=1)

print()
print_percentiles("Alignment residuals vs EXIF GPS [meters]", residuals)

if np.median(residuals) > args.max_align_error:
    print()
    print(
        "WARNING: median residual exceeds --max_align_error "
        f"({args.max_align_error} m). The transform may be wrong."
    )

out = {
    "ref_lat": ref_lat,
    "ref_lon": ref_lon,
    "ref_alt": ref_alt,
    "scale": float(enu_from_sfm.scale),
    "rotation_xyzw": enu_from_sfm.rotation.quat.tolist(),
    "translation": enu_from_sfm.translation.tolist(),
    "num_images_used": len(image_names),
    "residual_mean_m": float(residuals.mean()),
    "residual_median_m": float(np.median(residuals)),
    "residual_max_m": float(residuals.max()),
}

out_path = reference_dir / "outputs" / "georef_transform.json"
out_path.write_text(json.dumps(out, indent=2) + "\n")

print()
print(f"Wrote {out_path}")
