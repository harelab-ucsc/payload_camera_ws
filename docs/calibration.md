# Spectral Reflectance Calibration

This document describes how the payload converts raw camera DN (Digital Number
— the integer pixel value read directly from the sensor) values to
**absolute reflectance** [0, 1] and corrects for in-flight irradiance variation.
It covers the math, the operator procedure, what the logs tell you, and what
to do when something goes wrong.

---

## Overview

Calibration happens in three stages at different points in the flight workflow:

| Stage | When | Node | Output |
|---|---|---|---|
| **Auto-exposure + irradiance ref** | First image above 6 m AGL | `auto_cal` (MicaCRPCal) | Locked camera settings; 18-band spectrometer snapshot on `/panel_cal/spec_ref`; publishes `/cal/exposure_locked` |
| **Panel scan** | At 6 m hover, after exposure lock | `panel_scan` (MicaCRPCal) | 4 per-band correction factors on `/panel_cal/irradiance` |
| **Per-cycle correction** | Every image cycle during flight | `stream_processor` | Corrected reflectance images written to disk |

> **Why exposure-lock must come first:** `factor[i] = albedo / (panel_DN / dtype_max)` encodes the ExposureTime at scan time inside `panel_DN`. If exposure changes between the panel scan and flight images, every reflectance value is wrong by `E_flight / E_panel`. By waiting for `/cal/exposure_locked`, the panel is always imaged at the same exposure as the survey.

Both `/panel_cal/irradiance` and `/panel_cal/spec_ref` use **transient-local
(latched) QoS**, so `stream_processor` receives them regardless of node start
order.

---

## The Math

### 1. Panel calibration factor (pre-flight)

For each of the four cam0 band slices (`i = 0…3`):

```
factor[i] = albedo(λ_i) / (mean_panel_DN[i] / dtype_max)
```

where:
- `albedo(λ_i)` — certified spectral reflectance of the CRP at band wavelength
  `λ_i`, interpolated from the MicaSense-supplied CSV (`RP06-2120405-OB.csv`).
  Values are per-wavelength, typically ≈ 0.47–0.49 for this panel.
- `mean_panel_DN[i]` — mean raw DN measured by cam0 band slice `i` over the
  flat reflective panel region in the calibration image.
- `dtype_max` — 65535 for 16-bit output.

### 2. Irradiance ratio correction (per image cycle)

The panel may be in shade when calibrated on the ground. The AS7265x
spectrometer captures a reference irradiance snapshot **once the drone clears
6 m AGL** — above any local ground shadow. Each image cycle then applies:

```
total_factor[i] = factor[i] × (spec_ref[k_i] / spec_current[k_i])
```

where `k_i` is the spectrometer band index closest to camera band `i`:

| cam0 slice | Center λ | Spectrometer index | Spectrometer λ |
|---|---|---|---|
| 0 | 450 nm | 2 | 460 nm |
| 1 | 695 nm | 9 | 705 nm |
| 2 | 735 nm | 14 | 730 nm |
| 3 | 850 nm | 17 | 860 nm |

If `spec_ref` is unavailable (spectrometer not connected), `total_factor[i] =
factor[i]` — the panel calibration still applies, but irradiance drift between
panel scan and flight is not corrected.

### 3. Pixel correction (C++ extension, per pixel)

```
corrected_pixel = (raw_DN / dtype_max) × total_factor[i]
               = (raw_DN / panel_DN) × albedo × (spec_ref / spec_current)
               ≈ true_reflectance  ∈ [0, 1]
```

This is applied independently to each of the four cam0 band slices by the
`spectral_correct` C++ extension inside `stream_processor`.

cam1 (off-nadir RGB context camera) is debayered but **not** reflectance-corrected
— it is for visual reference only.

---

## Hardware

| Component | Role |
|---|---|
| **cam0** (arducam-pivariety 4-000c, 5120 × 800 mono) | 4-band multispectral camera. Each band is one 1280 × 800 slice of the full frame. All 4 share the same exposure/gain (mux board). |
| **cam1** (arducam-pivariety 6-000c, 5120 × 800 Bayer) | Off-nadir RGB context camera. Independent exposure from cam0. |
| **AS7265x** | 18-band ambient irradiance sensor. Measures downwelling light during panel scan and in-flight. |
| **MicaSense CRP RP06-2120405-OB** | Calibrated Reflectance Panel. Known spectral albedo ≈ 0.47–0.49 across visible/NIR bands. QR code on top half identifies the panel; flat grey reflective surface on bottom half. |

---

## Operator Procedure

### Before every flight

#### Step 1 — Launch the system
```bash
ros2 launch frc_payload_launcher fast_launch.py
```

The launch sequence:
- `t = 0 s` — PPS, radalt, spectrometer, INS start
- `t = 2 s` — cam0 starts
- `t = 4 s` — cam1 starts
- `t = 5 s` — **`panel_scan`** starts (30-second window)
- `t = 6 s` — **`auto_cal`** starts (waits for 6 m AGL)
- `t = 6 s` — **`stream_processor`** starts

#### Step 2 — Takeoff

Take off normally. Both `auto_cal` and `panel_scan` are waiting silently.

#### Step 3 — Auto-calibration at 6 m AGL (automatic)

Once the drone clears 6 m, `auto_cal` runs automatically:

1. **Exposure calibration for cam0 and cam1** (binary search, ≈ 10–30 seconds):
   - Finds the lowest `AnalogueGain` and corresponding `ExposureTime` where:
     - 99th-pct DN of the **brightest** cam0 band < 85 % of full scale (no clipping)
     - 5th-pct DN of the **darkest** cam0 band > 5 % of full scale (sufficient signal)
   - Hard limits: `ExposureTime ≤ 5 000 µs` (5 ms, < 1 px smear at 5 m/s),
     `AnalogueGain ≤ 6×`.
   - Both cameras are locked (`AeEnable = false`) after convergence.

2. **Irradiance reference snapshot**:
   - Captures the current AS7265x reading as the in-flight reference.
   - Published on `/panel_cal/spec_ref` (latched).

Expected log:
```
[auto_cal] Drone above 6.0 m — starting auto-calibration
[auto_cal] cam0: starting binary search — gain=1.0  exposure range [100, 5000] µs
[auto_cal] cam0 iter 0: exposure=2550 µs  gain=1.0  bright_99=74.2%  dark_05=3.1%
...
[auto_cal] cam0: converged — exposure=4200 µs  gain=1.0
[auto_cal] cam0 locked — ExposureTime=4200 µs  AnalogueGain=1.0×
[auto_cal] cam1: converged — exposure=3100 µs  gain=1.0
[auto_cal] cam1 locked — ExposureTime=3100 µs  AnalogueGain=1.0×
[auto_cal] Irradiance reference published (18 bands) on /panel_cal/spec_ref
[auto_cal] Auto-calibration complete.
```

#### Step 4 — Panel scan at 6 m hover (after auto_cal completes)

Once `auto_cal` finishes it publishes `/cal/exposure_locked`. `panel_scan`
receives this and opens its 30-second scan window. The log will show:

```
[panel_scan] Exposure locked — opening 30 s panel scan window.
             Place the CRP panel flat on the ground directly below the drone
             with the QR tag visible. Panel must be in direct sunlight with
             NO shadow on the reflective surface.
```

> **⚠ CRITICAL: The CRP panel must be in direct sunlight with NO shadow on
> the reflective grey surface. Shadow biases reflectance values for the
> entire flight. Abort and rescan if any shadow is present.**

1. Place the CRP panel **flat on the ground directly below the hovering drone**,
   reflective surface facing up.
2. Keep the **QR code fully visible** from above (QR on top half of holder;
   grey panel on bottom half).
3. The panel can be at any in-plane rotation — the node handles arbitrary
   orientation.
4. Wait for the log to confirm:

   ```
   [panel_scan] QR detected in slice(s) [0, 1, 2] (1/3): 'RP06-...'
   [panel_scan] QR detected in slice(s) [0, 1, 2] (2/3): 'RP06-...'
   [panel_scan] QR detected in slice(s) [0, 1, 2] (3/3): 'RP06-...'
   [panel_scan] Slice 0 (450 nm): mean_DN=…  albedo=0.4730  factor=…
   [panel_scan] Slice 1 (695 nm): mean_DN=…  albedo=0.4775  factor=…
   [panel_scan] Slice 2 (735 nm): mean_DN=…  albedo=0.4786  factor=…
   [panel_scan] Slice 3 (850 nm): mean_DN=…  albedo=0.4776  factor=…
   [panel_scan] Panel calibration published (4 bands) on /panel_cal/irradiance
   [stream_processor] Calibration complete — image capture and saving now active.
   ```

5. If the 30-second window expires without confirmation:
   ```
   [panel_scan] Panel scan timed out — no QR tag confirmed.
   ```
   Run `panel_scan` again manually while hovering. It will wait for
   `/cal/exposure_locked` (already published, latched) and open a new window.

#### Step 5 — Fly the survey

`stream_processor` applies the full correction to every image cycle:
```
[sync_node] Irradiance reference received: 18 bands
[sync_node] Cycle Complete: Saved 8 images at 1234567890.000000000
```

---

## Reading the Calibration Logs

### Good panel scan — all slices detected their own QR corners
```
Slice 0 (450 nm): mean_DN=28450  albedo=0.4730  factor=1.091
Slice 1 (695 nm): mean_DN=31200  albedo=0.4775  factor=1.003
Slice 2 (735 nm): mean_DN=29800  albedo=0.4786  factor=1.052
Slice 3 (850 nm): mean_DN=41000  albedo=0.4776  factor=0.763
```
NIR (850 nm) is brightest (low filter attenuation), blue (450 nm) is
dimmest — this is expected. `factor < 1` means the panel appeared brighter
than the reference albedo; `factor > 1` means it appeared darker.

### Partial detection — NIR slice fell back to visible-band corners
```
Slice 3 (850 nm) (QR not detected in this slice — using corners from slice 0):
    mean_DN=41000  albedo=0.4776  factor=0.763
```
This is normal. Printed black QR codes have poor contrast in NIR (ink absorbs
poorly at 850 nm). The corners from a visible slice are used instead; accuracy
is not materially affected because the panel is 6 m away — at that distance
the physical separation between the four cam0 sensors on the mux board
subtends a negligible angle, so all four cameras see the panel at essentially
the same position in their frames.

### Auto-exposure stepped up to higher gain
```
[auto_cal] cam0: searching at gain=2.0  exposure=[100, 5000] µs
```
This means the darkest band couldn't reach 5 % of full scale at gain=1.0 and
max exposure. Common when flying in overcast conditions or with high-attenuation
bandpass filters. The images are still correctly calibrated; `factor` will be
larger to compensate for the lower signal.

---

## Known Limitations

**Panel shade bias** — If the panel is in shadow during the scan (local shadow
from a person, vehicle, or tree — not uniform cloud cover), `mean_panel_DN`
is artificially low, producing an inflated `factor`. This causes the flight
images to appear too bright. The fix is to hold the panel in direct sun. Uniform
overcast is acceptable since the irradiance ratio correction (spec_ref /
spec_current) will compensate, as long as the overcast conditions are similar
between the scan and the flight.

**Single shared exposure for all cam0 bands** — The four cam0 sensors are on
a mux board and must share the same ExposureTime and AnalogueGain. The
binary search finds the best compromise: no clipping in the brightest band, and
sufficient signal in the darkest band. If the filter transmittances differ by
more than ≈ 10×, the darkest band may remain dim even at maximum settings.

**Irradiance correction is global** — The AS7265x measures irradiance at the
drone's position. Pixels in shadow on the ground (from clouds or terrain) are
not individually corrected — the correction assumes uniform illumination across
the scene within a single image cycle.

---

## Panel Albedo Data

The certified reflectance values for panel **RP06-2120405-OB** are bundled at:
```
src/MicaCRPCal/mica_crp_cal/data/RP06-2120405-OB.csv
```

Format: `wavelength_nm, reflectance` (no header), 251–950 nm at 1 nm steps.
The node interpolates this CSV at each camera band's center wavelength at startup.

To use a different panel, set the `crp_csv` ROS parameter on the `panel_scan`
node:
```python
Node(
    package="mica_crp_cal",
    executable="panel_scan",
    parameters=[{"crp_csv": "/path/to/your/panel.csv"}],
)
```
