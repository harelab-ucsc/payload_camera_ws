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
from hloc import colmap_from_nvm, triangulation, localize_sfm, visualization

parser = argparse.ArgumentParser()
parser.add_argument("--query_dir", type=Path, required=True, help="/path/to/query/images")
parser.add_argument("--reference_dir", type=Path, required=True, help="/path/to/reference/sfm")
parser.add_argument("--output_dir", type=Path, required=True, help="/path/to/save/results")
args = parser.parse_args()

queries = Path(args.query_dir)
outputs = Path(args.output_dir)
dataset = Path(args.reference_dir)

images = dataset / "images"

sfm_pairs = outputs / "pairs-db-covis20.txt"  # top 20 most covisible in SIFT model
loc_pairs = outputs / "pairs-query-netvlad20.txt"  # top 20 retrieved by NetVLAD
reference_sfm = outputs / "sfm_superpoint+superglue"  # the SfM model we will build
results = outputs / "hloc_superpoint+superglue_netvlad20.txt"  # the result file

retrieval_conf = extract_features.confs["netvlad"]
feature_conf = extract_features.confs["superpoint_aachen"]
matcher_conf = match_features.confs["superglue"]

features = extract_features.main(
    feature_conf,
    images,
    outputs
)
query_features = extract_features.main(
    feature_conf,
    queries,
    outputs,
    feature_path = outputs / "queries.h5"
)

pairs_from_covisibility.main(dataset, sfm_pairs, num_matched=20)
sfm_matches = match_features.main(
    matcher_conf,
    sfm_pairs,  # filepath to read found image pairs from
    feature_conf["output"],  # filepath to read derived features from
    outputs  # write other results to here
)
reconstruction = triangulation.main(
    reference_sfm,  # filepath to write new SfM to
    dataset/"sparse/0",  # path to COLMAP reference model
    images,  # source SfM imagery
    sfm_pairs,  # filepath to read found image pairs from
    features,  # filepath to read derived features from
    sfm_matches  # filepath to read matched features from
)

global_descriptors = extract_features.main(retrieval_conf, images, outputs)
pairs_from_retrieval.main(
    global_descriptors, loc_pairs, num_matched=20, db_prefix="db", query_prefix="query"
)
