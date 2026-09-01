#!/usr/bin/env bash

# ========================================================================
# Script Name:   hloc_reconstruct_and_densify.sh
# Description:   This script takes as input the file path to the project root
#                of an image dataset: /path/to/project/root,
#                with an images subdirectory (/path/to/project/root/images).
#                Process output files and directories will populate.
# Author:        Morgan Masters (mwmaster@ucsc.edu)
# Date:          2026-08-09
# Version:       1.0.0
# ========================================================================

set -Eeuo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 /path/to/repo/root /path/to/project/root" >&2
    exit 2
fi

REPO_ROOT="$1"
PROJECT_ROOT="$2"

IMAGE_DIR="$PROJECT_ROOT/images"
OUTPUT_DIR="$PROJECT_ROOT/outputs/sfm"
SPARSE_DIR="$OUTPUT_DIR/sfm_superpoint+superglue/"
DENSE_DIR="$OUTPUT_DIR/sfm_superpoint+superglue/dense"

# 1.) first, reconstruct
[[ -d "$REPO_ROOT" ]] || {
    echo "Error: repo root does not exist: $REPO_ROOT" >&2
    exit 1
}
[[ -d "$PROJECT_ROOT" ]] || {
    echo "Error: project root does not exist: $PROJECT_ROOT" >&2
    exit 1
}
[[ -d "$IMAGE_DIR" ]] || {
    echo "Error: images directory does not exist: $IMAGE_DIR" >&2
    exit 1
}
find "$IMAGE_DIR" -type f -print -quit | grep -q . || {
    echo "Error: images directory is empty: $IMAGE_DIR" >&2
    exit 1
}
# python3 "$REPO_ROOT/scripts/hloc_reconstruction.py" \
#   --images_dir "$IMAGE_DIR" \
#   --output_dir "$OUTPUT_DIR"

# 2.) densify the sparse reconstruction
[[ -d "$SPARSE_DIR" ]] || {
    echo "Error: COLMAP sparse model does not exist: $SPARSE_DIR" >&2
    exit 1
}
colmap image_undistorter \
    --image_path "$IMAGE_DIR" \
    --input_path "$SPARSE_DIR" \
    --output_path "$DENSE_DIR"

colmap patch_match_stereo \
    --workspace_path "$DENSE_DIR"

colmap stereo_fusion \
    --workspace_path "$DENSE_DIR" \
    --output_path "$DENSE_DIR/fused.ply"

colmap poisson_mesher \
    --input_path "$DENSE_DIR/fused.ply" \
    --output_path "$DENSE_DIR/mesh.ply"
