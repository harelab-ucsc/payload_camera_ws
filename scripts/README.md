# Payload camera pipeline: raw images → georeferenced localization

End-to-end pipeline that takes a raw 4-camera Birdseye payload capture, builds a
COLMAP/hloc 3D reconstruction from it, localizes a second capture against that
reconstruction, and expresses the result in real-world coordinates.

The motivating experiment: replace a **flat-world assumption** (project pixels
onto an assumed flat ground plane at fixed height) with an actual 3D
reconstruction, and measure whether that is more accurate — using a surveyed
AprilTag ground-control point as truth.

## Pipeline overview

```
                        ┌──────────────────────────────────────┐
   RAW CAPTURE          │  rgb_<N>_<timestamp>.jpeg  (N=1..4)  │
   (per flight)         │  + birdseye_v2_camchain.yaml         │
                        └───────────────────┬──────────────────┘
                                            │
                          [1] uav_image_postproc/postproc.sh
                                            │  rotate 180°, regroup by camera,
                                            │  rename, build rig config + masks
                                            v
                        ┌──────────────────────────────────────┐
   POSTPROCESSED        │ <project>/images/cameraN/imageNNNN.jpeg
   DATASET              │ <project>/masks/...                  │
   (a "project root")   │ <project>/rig_config.json            │
                        │ <project>/frame_mapping.txt          │
                        └───────────────────┬──────────────────┘
                                            │
                    ┌───────────────────────┴────────────────────────┐
                    │                                                │
         REFERENCE capture (roof)                        QUERY capture (yard)
                    │                                                │
     [2] hloc_reconstruction2.py                                     │
                    │  SuperPoint + NetVLAD + SuperGlue              │
                    │  rig-constrained incremental SfM               │
                    v                                                │
    <ref>/outputs/sfm_superpoint+superglue/                          │
    <ref>/outputs/feats-*-masked.h5                                  │
    <ref>/outputs/global-feats-netvlad.h5                            │
                    │                                                │
                    ├──────────────────┐                             │
                    │                  │                             │
     [3] georef_reconstruction.py      └──────> [4] hloc_localize2.py <┘
                    │  fit ENU<-SfM                  │  retrieve top-20 refs,
                    │  similarity from               │  SuperGlue match,
                    │  GPS EXIF                      │  generalized PnP per rig frame
                    v                                v
    <ref>/outputs/georef_transform.json    <out>/localization_results.csv
                    │                                │
                    └────────────┬───────────────────┘
                                 │
                  [5] georef_localized_poses.py
                                 │  apply Sim3d, ENU -> lat/lon/alt
                                 v
              <out>/localized_poses_georeferenced.csv
                                 │
                  [6] validate_gcp_apriltag.py  <── click_gcps.csv (surveyed truth)
                                 │  detect AprilTag, triangulate,
                                 │  compare against surveyed GCP
                                 v
                    residual in meters (accuracy number)
```

## Environment

Make sure to
1. Make a virtual environment,
2. install all packages, including pycolmap and hloc
3. source the virtual environment's activation script

---

## 1. Postprocess a raw capture

Turns a flat folder of raw images into a COLMAP-ready "project root". (Check the
README in the uav_image_postproc folder for information on what it does.) Run 
this once per capture (both the reference and the query capture).

Raw filenames must match `rgb_<N>_<timestamp>.jpeg` with `N` in 1..4; the four
cameras of one frame are matched by identical timestamp.

```bash
./scripts/uav_image_postproc/postproc.sh \
    /datasets/<user>/<capture>/rgbs \
    /path/to/payload_camera_ws/config/birdseye_v2_camchain.yaml \
    /datasets/<user>/<capture>_hloc_ref
```

```bash
./scripts/uav_image_postproc/postproc.sh \
    /datasets/<user>/<capture>/rgbs \
    /path/to/payload_camera_ws/config/birdseye_v2_camchain.yaml \
    /datasets/<user>/<capture>_hloc_query
```

It then **pauses** so you can inspect the mask overlays.
Once they look right:

```bash
scripts/uav_image_postproc/postproc.sh --finalize-masks /datasets/<user>/<capture>_hloc_ref
```

Use `--no-qa` to skip the review pause and finalize immediately.

Resulting project root:

```
<project>/
  images/cameraN/imageNNNN.jpeg       # 180°-rotated, renamed, EXIF preserved
  masks/cameraN/imageNNNN.jpeg.png    # per-frame masks (links to canonical)
  masks/.canonical/cameraN.{png,npy}
  masks_overlays/cameraN_overlay.png
  rig_config.json                     # intrinsics + cam_from_rig extrinsics
  frame_mapping.txt                   # imageNNNN.jpeg <TAB> original timestamp
```

## 2. Build the reference reconstruction

```bash
python3 scripts/hloc_reconstruction2.py \
    --dataset_dir /datasets/<user>/<capture>_hloc_ref
```

Writes into `/datasets/<user>/<capture>_hloc_ref`:

```
global-feats-netvlad.h5
pairs-netvlad.txt
feats-superpoint-n4096-r1024.h5
feats-superpoint-n4096-r1024_masked.h5     # consumed by localization
matches-masked-superglue.h5
sfm_superpoint+superglue/                  # cameras/images/points3D/rigs/frames .bin
```

All of these are **cached** — re-running skips work that is already present.

## 3. Georeference the reconstruction

```bash
python3 scripts/georef_reconstruction.py \
    --reference_dir /datasets/<user>/<capture>_hloc_ref \
    [--max_align_error 5.0]
```

Reads GPS EXIF from every registered image, converts to a local ENU frame, and
fits a similarity transform (scale + rotation + translation) mapping SfM
coordinates to ENU using `pycolmap.align_reconstruction_to_locations`. Prints
residual percentiles against the images' own GPS as a sanity check and warns if
the median exceeds `--max_align_error`.

Writes `<ref>/outputs/georef_transform.json` (scale, rotation quaternion,
translation, and the ENU reference lat/lon/alt).

---

## 4. Localize a query capture against the reference

```bash
python3 scripts/hloc_localize2.py \
    --query_dir      /datasets/<user>/<query>_hloc_query \
    --reference_dir  /datasets/<user>/<capture>_hloc_ref \
    --output_dir     /datasets/<user>/<query>_hloc_query/outputs_vs_roof
```

Extracts and masks query features, retrieves the top 20 reference images per
query image, matches with SuperGlue, then solves one **generalized absolute
pose** per rig frame (all 4 cameras jointly, using `cam_from_rig`).

Writes into `--output_dir`:

```
query_superpoint_raw.h5 / query_superpoint.h5 / query_netvlad.h5
pairs-query-netvlad20.txt
matches-query-superglue.h5
localization_results.csv    # per-frame rig pose in the reference SfM frame
localization_summary.txt
localization_results.csv_logs.pkl   # hloc-format log, for visualization
```

`localization_results.csv` is a plain CSV — one field per column, matching its
header. You should prefer `georef_common.read_localization_results()` over parsing it by
hand; it returns `rig_from_world` as a `pycolmap.Rigid3d` (handling the
`[w,x,y,z]` → `[x,y,z,w]` quaternion reordering) and still reads files written
by older runs, which packed `qw..qz` and `tx..tz` into two whitespace-separated
fields.

Runtime is dominated by SuperGlue matching (query_images × 20 pairs; ~30k pairs
= around 15-20 min on an RTX 3070). Matching results are cached, so a re-run that only
changes pose estimation is fast.

---

## 5. Convert localized poses to real-world coordinates

```bash
python3 scripts/georef_localized_poses.py \
    --localization_dir  /datasets/<user>/<query>_hloc_query/outputs_vs_roof \
    --georef_transform  /datasets/<user>/<capture>_hloc_ref/outputs/georef_transform.json
```

Writes `localized_poses_georeferenced.csv` with
`frame, lat, lon, alt, enu_x, enu_y, enu_z, num_inliers, inlier_ratio`.

Filter on `num_inliers` — low-inlier frames can produce wild poses that dominate
naive min/max statistics.

---

## 6. Validate against a surveyed AprilTag

```bash
python3 scripts/validate_gcp_apriltag.py \
    --query_dir        /datasets/<user>/<query>_hloc_query \
    --reference_dir    /datasets/<user>/<capture>_hloc_ref \
    --localization_dir /datasets/<user>/<query>_hloc_query/outputs_vs_roof \
    --georef_transform /datasets/<user>/<capture>_hloc_ref/outputs/georef_transform.json \
    --click_gcps_csv   /datasets/<user>/<query>/click_gcps.csv
```

Detects the AprilTag in every localized query image (tries families 36h11,
25h9, 16h5, 36h10), builds a 3D ray per detection from that camera's pose and
intrinsics, triangulates, georeferences the result, and compares it to the
surveyed GCP. Drops detections from low-confidence rig poses (<50 inliers) and
then rejects geometric outlier rays before re-triangulating.

`click_gcps.csv` has no header; columns are:

| col (0-based) | meaning |
|---|---|
| 0 | latitude |
| 1 | longitude |
| 2 | **WGS84 ellipsoid height** — this is what the pipeline uses |
| 3 | height above sea level (MSL) |
| 4 | quality flag (2 = good; only these rows are used) |
| 5 | label (ignored) |

Columns 2 and 3 differ by ~30.7m, the local geoid separation. Column 2 is the
correct one to feed to `GPSTransform.ellipsoid_to_enu()`, and it matches the
datum of the INS `lla[2]` behind the image EXIF altitudes. Using column 3
instead moves the answer ~26m vertically.

---

## 7. Visual QA and the reprojection metric

```bash
python3 scripts/visualize_localization.py --mode all \
    --query_dir        /datasets/<user>/<query>_hloc_query \
    --reference_dir    /datasets/<user>/<capture>_hloc_ref \
    --localization_dir /datasets/<user>/<query>_hloc_query/outputs_vs_roof \
    --georef_transform /datasets/<user>/<capture>_hloc_ref/outputs/georef_transform.json \
    --click_gcps_csv   /datasets/<user>/<query>/click_gcps.csv \
    --output_dir       /datasets/<user>/<query>_hloc_query/outputs_vs_roof/viz \
    --num_frames 6
```

Three modes (`--mode sfm|loc|gcp|all`):

- **`sfm`** — reference reconstruction keypoints coloured by visibility or
  track length, via hloc's `visualize_sfm_2d`. Sanity-checks the model.
- **`loc`** — query/reference correspondences coloured by PnP inlier status
  (green = inlier), via hloc's `visualize_loc_from_log`, reading the
  `_logs.pkl` from step 4.
- **`gcp`** — reprojects the surveyed GCP into every query image that saw the
  AprilTag and draws it against the detected tag centre.

`gcp` mode is the one that yields a **metric**: the pixel gap between the
detected tag and the reprojected surveyed GCP, per image. It is independent of
the triangulation in step 6, so it serves as a cross-check rather than a
restatement — and it converts each pixel error to an approximate ground
distance using that observation's range. It also writes
`gcp_reprojection_errors.csv` with every detection so the distribution can be
inspected rather than trusting a single summary number.

Note `visualize_localization.py` runs its own AprilTag detection rather than
reusing step 6's, so the two are independent measurements of the same quantity.

---

## `georef_common.py`

Shared helpers (no CLI): `load_georef_transform`, `read_localization_results`,
`load_cameras_from_rig`, `camera_number`.

---

## Gotchas worth knowing

**Query and reference filenames collide.** Every capture numbers frames from
`image0001.jpeg`, so a query image and an unrelated reference image can share a
name. hloc's retrieval and match cache assume one global namespace (its
self-match filter compares names, and its pair cache treats `(a,b)` and `(b,a)`
as the same pair), so a collision silently misattributes correspondences.
`hloc_localize2.py` therefore prefixes every query-side h5 group with `yard_`
before retrieval/matching.

**Don't `import` the pipeline scripts.** Most of them execute argparse and the
whole pipeline at module scope, so importing one runs it. Shared code belongs in
`georef_common.py`.

**Interrupting a run can poison the cache.** `match_features` skips any pair
already present in the matches `.h5` without checking that it is complete, so a
killed run can leave a truncated entry that a later run silently reuses. If a
run is interrupted mid-matching, delete the output directory and start over.

---

## Known issue: the reconstruction is not metric

The rig extrinsics are metric and held fixed (cameras 8.87cm / 12.56cm apart),
but the reconstructed scene comes out **~6.55× off scale** — the model behaves
as though the cameras were ~58cm apart. Cause: the four cameras point in four
different directions with no overlapping field of view, so no 3D point is ever
observed by two cameras in the same frame. That makes the 8.87cm baseline a very
weak scale reference against a ~20m scene depth, and scale drifts freely.

Measured scale is roughly **uniform** rather than drifting (median local scale
6.65 across the trajectory vs. 6.55 global; thirds at 6.70 / 6.38 / 6.92), so
the similarity fit in step 3 does absorb most of it.

Possible fix: constrain the reconstruction with the RTK GPS positions
as **pose priors during mapping** (`pycolmap.PosePrior` with
`PosePriorCoordinateSystem.WGS84`, plus
`IncrementalPipelineOptions.use_prior_position=True` and
`use_robust_loss_on_prior_position=True`), which makes the model metric and
georeferenced from the start and removes step 3's post-hoc alignment as a
separate error source. **Not yet implemented.**

---

## Accuracy to date

Against the surveyed AprilTag on the WRP yard/roof datasets:

| stage | 3D residual | horizontal | vertical |
|---|---|---|---|
| with the quaternion bug | 14.73 m | 4.89 m | 13.89 m |
| after fixing it | **6.12 m** | **3.75 m** | **4.84 m** |

Independent checks that the geometry is now sound: every triangulated ray points
downward (-34° to -67°, versus one pointing *upward* before), per-ray
ground-plane intersections cluster within 1.7-8.8m (previously 7-132m), and the
geometric outlier filter now rejects nothing.

The RTK GPS itself is good: EXIF GPS agrees with the raw INS `/ins_quat_uvw_lla`
positions to within ~20cm on the yard flight, so the remaining error is in the
reconstruction/alignment chain, not the GPS.
