#!/usr/bin/env python3

import argparse

from pathlib import Path
from pprint import pformat

from hloc import (
    extract_features,
    match_features,
    pairs_from_covisibility,
    pairs_from_retrieval,
)
from hloc import triangulation, localize_sfm


parser = argparse.ArgumentParser()

parser.add_argument(
    "--dataset_dir",
    type=Path,
    required=True,
    help="/path/to/dataset",
)

parser.add_argument(
    "--output_dir",
    type=Path,
    required=True,
    help="/path/to/save/results",
)

parser.add_argument(
    "--rebuild_sfm",
    action="store_true",
    help=(
        "Build a new hloc SfM model from dataset/sparse/0 using "
        "the configured local features and matcher. If omitted, "
        "dataset/sparse/0 is used directly."
    ),
)

args = parser.parse_args()

dataset = args.dataset_dir
outputs = args.output_dir

images = dataset / "images"
queries = dataset / "queries"
existing_sfm = dataset / "sparse" / "0"

sfm_pairs = outputs / "pairs-db-covis20.txt"
loc_pairs = outputs / "pairs-query-netvlad20.txt"
new_sfm = outputs / "sfm_superpoint+superglue"
results = outputs / "hloc_superpoint+superglue_netvlad20.txt"

retrieval_conf = extract_features.confs["netvlad"]
feature_conf = extract_features.confs["superpoint_aachen"]
matcher_conf = match_features.confs["superglue"]


# ============================================================
# Extract local features for BOTH reference and query images.
#
# Because dataset is the root, the feature file uses names like:
#
#   images/foo.jpg
#   queries/bar.jpg
# ============================================================
features = extract_features.main(
    feature_conf,
    dataset,
    outputs,
)

# Choose the SfM model used for localization.
if args.rebuild_sfm:

    # Build a new hloc SfM model from the existing reconstruction.
    pairs_from_covisibility.main(
        dataset,
        sfm_pairs,
        num_matched=20,
    )

    sfm_matches = match_features.main(
        matcher_conf,
        sfm_pairs,
        feature_conf["output"],
        outputs,
    )

    reconstruction = triangulation.main(
        new_sfm,
        existing_sfm,
        images,
        sfm_pairs,
        features,
        sfm_matches,
    )

else:

    # Use the existing reconstruction directly.
    reconstruction = existing_sfm

# Extract NetVLAD descriptors for BOTH reference and query
# images.
global_descriptors = extract_features.main(
    retrieval_conf,
    dataset,
    outputs,
)

# Retrieve reference images for each query.
pairs_from_retrieval.main(
    global_descriptors,
    loc_pairs,
    num_matched=20,
    db_prefix="images",
    query_prefix="queries",
)

# Match queries against retrieved reference images.
loc_matches = match_features.main(
    matcher_conf,
    loc_pairs,
    feature_conf["output"],
    outputs,
)

# Localize queries against the selected reconstruction.
localize_sfm.main(
    reconstruction,
    dataset / "queries/*_time_queries_with_intrinsics.txt",
    loc_pairs,
    features,
    loc_matches,
    results,
    covisibility_clustering=False,
)
