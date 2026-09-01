#!/usr/bin/env python3

import argparse
from pathlib import Path

import pycolmap

from hloc import (
    extract_features,
    match_features,
    pairs_from_retrieval,
)
from hloc import reconstruction as hloc_reconstruction

from hloc_mask_features import apply_masks_to_features


parser = argparse.ArgumentParser()

parser.add_argument(
    "--dataset_dir",
    type=Path,
    required=True,
    help="Postprocessed dataset root containing images/ and masks/",
)

args = parser.parse_args()

dataset = args.dataset_dir
images = dataset / "images"
masks = dataset / "masks"
outputs = dataset / "outputs"

if not images.is_dir():
    raise FileNotFoundError(f"Missing images directory: {images}")

if not masks.is_dir():
    raise FileNotFoundError(f"Missing masks directory: {masks}")

outputs.mkdir(parents=True, exist_ok=True)

sfm_pairs = outputs / "pairs-netvlad.txt"
sfm_dir = outputs / "sfm_superpoint+superglue"

retrieval_conf = extract_features.confs["netvlad"]
feature_conf = extract_features.confs["superpoint_aachen"]
matcher_conf = match_features.confs["superglue"]

# 1. Extract NetVLAD descriptors from the original images.
retrieval_path = extract_features.main(
    retrieval_conf,
    images,
    outputs,
)

# 2. Retrieve nearby/reference image pairs.
pairs_from_retrieval.main(
    retrieval_path,
    sfm_pairs,
    num_matched=5,
)

# 3. Extract raw SuperPoint features.
raw_feature_path = extract_features.main(
    feature_conf,
    images,
    outputs,
)

# 4. Apply the postproc masks to the local features.
masked_feature_path = outputs / (
    "feats-superpoint-n4096-r1024_masked.h5"
)

masked_feature_path = apply_masks_to_features(
    raw_feature_path,
    masked_feature_path,
    masks,
    overwrite=True,
)

# 5. Match the masked local features with SuperGlue.
match_path = outputs / "matches-masked-superglue.h5"

match_path = match_features.main(
    matcher_conf,
    sfm_pairs,
    masked_feature_path,
    export_dir=outputs,
    matches=match_path,
)

# 6. Build the sparse reconstruction.
sfm_dir.mkdir(parents=True, exist_ok=True)

database_path = sfm_dir / "database.db"
rig_config_path = dataset / "rig_config.json"

if not rig_config_path.is_file():
    raise FileNotFoundError(f"Missing rig configuration: {rig_config_path}")

hloc_reconstruction.create_empty_db(database_path)

hloc_reconstruction.import_images(
    images,
    database_path,
    camera_mode=pycolmap.CameraMode.PER_FOLDER,
)
rig_configs = pycolmap.read_rig_config(rig_config_path)

with pycolmap.Database.open(database_path) as database:
    pycolmap.apply_rig_config(rig_configs, database)

with pycolmap.Database.open(database_path) as database:
    print()
    print("Database after applying rig config:")
    print(f"  cameras: {database.num_cameras}")
    print(f"  images:  {database.num_images}")
    print(f"  rigs:    {database.num_rigs}")
    print(f"  frames:  {database.num_frames}")

image_ids = hloc_reconstruction.get_image_ids(database_path)

with pycolmap.Database.open(database_path) as database:
    hloc_reconstruction.import_features(
        image_ids,
        database,
        masked_feature_path,
    )
    hloc_reconstruction.import_matches(
        image_ids,
        database,
        sfm_pairs,
        match_path,
    )
hloc_reconstruction.estimation_and_geometric_verification(
    database_path,
    sfm_pairs,
    False,
)

mapper_options = {
    "ba_refine_focal_length": False,
    "ba_refine_principal_point": False,
    "ba_refine_extra_params": False,
    "ba_refine_sensor_from_rig": False,
}

model = hloc_reconstruction.run_reconstruction(
    sfm_dir,
    database_path,
    images,
    False,
    mapper_options,
)

if model is None:
    raise RuntimeError(f"Reconstruction failed!")

print()
print(model.summary())