#!/usr/bin/env python3

from pathlib import Path
import shutil

import cv2
import h5py
import numpy as np


def replace_dataset(group: h5py.Group, name: str, data: np.ndarray):
    """Replace an HDF5 dataset with a new array."""
    attrs = dict(group[name].attrs)
    del group[name]
    dataset = group.create_dataset(name, data=data)
    for key, value in attrs.items():
        dataset.attrs[key] = value


def mask_path_for_image(masks_dir: Path, image_name: str) -> Path:
    """
    Convert:
        camera2/image0042.jpeg
    into:
        masks/camera2/image0042.jpeg.png
    which is the COLMAP-style mask filename produced by postproc.
    """
    image_path = Path(image_name)
    camera_dir = image_path.parent.name

    if camera_dir.startswith("yard_"):
        camera_dir = camera_dir.removeprefix("yard_")

    return masks_dir / camera_dir / f"{image_path.name}.png"


def find_image_groups(feature_file: h5py.File):
    """
    Return the HDF5 group names corresponding to HLoc images.

    Example:
        camera2/image0042.jpeg
    """
    image_names = []

    def visitor(name, obj):
        if isinstance(obj, h5py.Group) and "keypoints" in obj:
            image_names.append(name)

    feature_file.visititems(visitor)
    return image_names


def apply_masks_to_features(
    input_features: Path,
    output_features: Path,
    masks_dir: Path,
    overwrite: bool = False,
) -> Path:
    """
    Copy an HLoc SuperPoint feature file and remove all features whose
    keypoints land on black pixels in the corresponding postproc mask.

    Expected SuperPoint datasets:
        descriptors  (256, N)
        image_size   (2,)
        keypoints    (N, 2)
        scores       (N,)

    Postproc mask convention:
        0   = ignore
        255 = keep
    """
    input_features = Path(input_features)
    output_features = Path(output_features)
    masks_dir = Path(masks_dir)

    if not input_features.is_file():
        raise FileNotFoundError(
            f"Input feature file does not exist: {input_features}"
        )

    if not masks_dir.is_dir():
        raise FileNotFoundError(f"Mask directory does not exist: {masks_dir}")

    if output_features.exists():
        if not overwrite:
            print(
                f"Masked feature file already exists; "
                f"reusing:\n  {output_features}"
            )
            return output_features
        output_features.unlink()

    output_features.parent.mkdir(parents=True, exist_ok=True)

    # Keep the original SuperPoint file untouched.
    shutil.copy2(input_features, output_features)

    total_images = 0
    total_before = 0
    total_after = 0

    with h5py.File(output_features, "r+") as feature_file:
        image_names = find_image_groups(feature_file)

        for image_name in image_names:
            group = feature_file[image_name]
            mask_path = mask_path_for_image(masks_dir, image_name)
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

            if mask is None:
                raise RuntimeError(
                    f"Could not read mask for {image_name}:\n\t{mask_path}"
                )

            keypoints = np.asarray(group["keypoints"])
            scores = np.asarray(group["scores"])
            descriptors = np.asarray(group["descriptors"])

            # Sanity-check the HLoc feature layout
            n = keypoints.shape[0]

            if keypoints.shape != (n, 2):
                raise RuntimeError(
                    f"{image_name}: unexpected keypoints shape "
                    f"{keypoints.shape}"
                )

            if scores.shape != (n,):
                raise RuntimeError(
                    f"{image_name}: scores shape {scores.shape} does not "
                    f"match {n} keypoints"
                )

            if descriptors.ndim != 2:
                raise RuntimeError(
                    f"{image_name}: unexpected descriptors shape "
                    f"{descriptors.shape}"
                )

            if descriptors.shape[1] != n:
                raise RuntimeError(
                    f"{image_name}: descriptor count {descriptors.shape[1]} "
                    f"does not match {n} keypoints"
                )

            # Map floating-point SuperPoint coordinates onto the integer
            # mask image. HLoc keypoints are [x, y].
            x = np.rint(keypoints[:, 0]).astype(np.int64)
            y = np.rint(keypoints[:, 1]).astype(np.int64)
            x = np.clip(x, 0, mask.shape[1] - 1)
            y = np.clip(y, 0, mask.shape[0] - 1)

            # Black = masked = remove.
            keep = mask[y, x] != 0

            # Filter every feature-indexed array
            filtered_keypoints = keypoints[keep]
            filtered_scores = scores[keep]
            filtered_descriptors = descriptors[:, keep]

            replace_dataset(group, "keypoints", filtered_keypoints)
            replace_dataset(group, "scores", filtered_scores)
            replace_dataset(group, "descriptors", filtered_descriptors)
            # image_size is deliberately left untouched.

            total_images += 1
            total_before += n
            total_after += int(keep.sum())

    removed = total_before - total_after
    removed_fraction = removed / total_before if total_before else 0.0

    print()
    print(f"Processed {total_images} images.")
    print(f"Features before masking: {total_before}")
    print(f"Features after masking:  {total_after}")
    print(
        f"Removed:                 "
        f"{removed} ({100.0 * removed_fraction:.2f}%)"
    )
    print(f"Masked feature file:\n  {output_features}")

    return output_features
