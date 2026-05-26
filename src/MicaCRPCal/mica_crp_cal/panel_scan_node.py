"""
MicaCRPCal panel scan node.

Subscribes to the cam0 image stream (the only nadir-pointing camera).
cam0 is a 4-band multispectral image: four band images laid side-by-side
horizontally, each occupying one quarter of the full frame width.

Algorithm
---------
1. Run QR detection on band-slice 0 (leftmost quarter, ~450 nm) for up to
   SCAN_TIMEOUT_S seconds.
2. When the panel QR tag is confirmed across CONFIRM_FRAMES consecutive frames,
   derive the flat reflective panel ROI from the QR corner geometry.
   The panel is directly below the QR code in the holder and is the same size.
3. For each of the four cam0 band slices, compute the mean raw DN over the
   panel ROI at full sensor bit-depth.
4. Look up the panel's certified spectral albedo at each band wavelength
   (interpolated from the MicaSense-supplied CRP CSV).
5. Publish four per-band calibration factors on /panel_cal/irradiance (latched):
       factor[i] = albedo(λ_i) / (mean_panel_DN[i] / dtype_max)

stream_processor passes these four factors directly to the C++ spectral_correct
extension, which applies per pixel:
    corrected = (raw_DN / dtype_max) * factor  →  true reflectance ∈ [0, 1]

Note on irradiance correction: the panel lighting conditions at scan time are
already encoded in mean_panel_DN. A spectrometer-based irradiance ratio
correction is intentionally omitted — the panel may be in shade while the
spectrometer sees full sun (or vice versa), which would make such a correction
invalid. If irradiance variation correction is required, apply it in
post-processing using the spectrometer data saved per image cycle in the DB.
"""

import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Float32MultiArray

SCAN_TIMEOUT_S = 30.0
CONFIRM_FRAMES = 3
NUM_SLICES = 4

# Center wavelengths (nm) for cam0 band slices 0-3.
CAM0_BAND_NM = (450, 695, 735, 850)

# Panel geometry relative to the QR bounding quad.
# The flat panel is directly below the QR in the holder; both are the same size.
# PANEL_GAP_FRAC: gap from QR bottom edge to panel top, as a fraction of QR height.
# PANEL_SIZE_FRAC: panel height as a fraction of QR height (~1.0).
PANEL_GAP_FRAC = 0.05
PANEL_SIZE_FRAC = 1.0

# Default CRP CSV — bundled alongside this file.
_DEFAULT_CSV = Path(__file__).parent / "data" / "RP06-2120405-OB.csv"

_LATCHED_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    depth=1,
)


def _load_albedo(csv_path: str | Path, wavelengths_nm: tuple) -> list:
    """Interpolate panel albedo at the requested wavelengths from a MicaSense CRP CSV.

    The CSV has two columns: wavelength_nm, reflectance (no header).
    """
    data = np.loadtxt(str(csv_path), delimiter=",")
    wl = data[:, 0]
    refl = data[:, 1]
    return [float(np.interp(nm, wl, refl)) for nm in wavelengths_nm]


def _panel_roi_from_qr(pts: np.ndarray) -> np.ndarray:
    """Return the flat panel ROI corners given the four QR corner points.

    The panel holder has the QR code at one end and the flat reflective panel
    at the other end (same size, directly adjacent). We project one QR-height
    past the QR's image-space bottom edge to locate the panel.

    This works for any in-plane rotation where the panel is below the QR in
    image-Y (Y=0 at top). If the holder is flipped 180° so the panel is above
    the QR in the image, re-orient the holder and rescan.

    Args:
        pts: (4, 2) float32 QR corner points in any order.

    Returns:
        (4, 2) float32 panel corners in [TL, TR, BR, BL] image order.
    """
    pts = pts.reshape(4, 2).astype(np.float32)

    # Split into "top" (smaller image-Y) and "bottom" (larger image-Y) pairs.
    order = np.argsort(pts[:, 1])
    top_two = pts[order[:2]]
    bot_two = pts[order[2:]]

    step = bot_two.mean(axis=0) - top_two.mean(axis=0)  # QR height vector

    # Sort each pair left-to-right for consistent corner labelling.
    bot_l, bot_r = bot_two[np.argsort(bot_two[:, 0])]

    gap = step * PANEL_GAP_FRAC
    panel_tl = bot_l + gap
    panel_tr = bot_r + gap
    panel_bl = panel_tl + step * PANEL_SIZE_FRAC
    panel_br = panel_tr + step * PANEL_SIZE_FRAC

    return np.array([panel_tl, panel_tr, panel_br, panel_bl], dtype=np.float32)


class PanelScanNode(Node):

    def __init__(self):
        super().__init__("panel_scan")
        self._bridge = CvBridge()
        self._detector = cv2.QRCodeDetector()
        self._confirm = 0
        self._done = False
        self._start = time.monotonic()
        self._last_raw: np.ndarray | None = None
        # Per-slice QR corners from the most recent confirmed frame.
        # Index is slice number; value is the bbox array or None if that slice
        # could not detect the QR (e.g. NIR bands with poor ink contrast).
        self._last_bboxes: list[np.ndarray | None] = [None] * NUM_SLICES

        # CRP albedo CSV — can be overridden via ROS parameter.
        self.declare_parameter("crp_csv", str(_DEFAULT_CSV))
        csv_path = self.get_parameter("crp_csv").value

        try:
            self._albedo = _load_albedo(csv_path, CAM0_BAND_NM)
        except Exception as ex:
            self.get_logger().fatal(f"Failed to load CRP albedo CSV ({csv_path}): {ex}")
            raise

        self.get_logger().info(
            f"CRP albedo loaded from {csv_path}: "
            + ", ".join(
                f"{nm}nm={a:.4f}" for nm, a in zip(CAM0_BAND_NM, self._albedo)
            )
        )

        self._pub = self.create_publisher(
            Float32MultiArray, "/panel_cal/irradiance", _LATCHED_QOS
        )

        # cam0 is the only nadir-pointing camera.
        self.create_subscription(
            Image,
            "/cam0/camera_node/image_raw",
            self._img_cb,
            10,
        )

        self.create_timer(1.0, self._watchdog)
        self.get_logger().info(
            f"MicaCRPCal scan started — {SCAN_TIMEOUT_S:.0f} s window. "
            "Point cam0 at the CRP panel with the QR tag fully visible."
        )
        self.get_logger().warn(
            "PRE-FLIGHT CHECK: The calibration panel MUST be in direct sunlight "
            "with NO shadow on the reflective surface. Shadow on the panel at "
            "scan time will introduce a systematic reflectance bias across the "
            "entire flight. Abort and rescan if any shadow is present."
        )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _img_cb(self, msg: Image) -> None:
        if self._done:
            return

        try:
            raw = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
        except Exception as ex:
            self.get_logger().warn(
                f"imgmsg_to_cv2 failed: {ex}", throttle_duration_sec=5.0
            )
            return

        h, w = raw.shape[:2]
        slice_w = w // NUM_SLICES

        # Try QR detection on all slices. Printed QR codes have best contrast
        # in visible bands; NIR (slice 3, ~850 nm) often has poor ink contrast
        # and may not decode. Each slice gets its own corners where possible so
        # any per-camera geometric offset is handled naturally. A frame counts
        # as a confirmation if at least one slice detects the QR.
        bboxes: list[np.ndarray | None] = []
        detected_slices: list[int] = []
        detected_data: str | None = None

        for s in range(NUM_SLICES):
            band = raw[:, s * slice_w: (s + 1) * slice_w]
            gray = (band >> 8).astype(np.uint8) if raw.dtype != np.uint8 else band.copy()
            data, bbox, _ = self._detector.detectAndDecode(gray)
            if data:
                bboxes.append(bbox)
                detected_slices.append(s)
                detected_data = data
            else:
                bboxes.append(None)

        if detected_data is not None:
            self._confirm += 1
            self._last_raw = raw
            self._last_bboxes = bboxes
            self.get_logger().info(
                f"QR detected in slice(s) {detected_slices} "
                f"({self._confirm}/{CONFIRM_FRAMES}): '{detected_data}'"
            )
            if self._confirm >= CONFIRM_FRAMES:
                self._publish_calibration()
        else:
            self._confirm = 0

    def _watchdog(self) -> None:
        if self._done:
            return
        if time.monotonic() - self._start >= SCAN_TIMEOUT_S:
            self.get_logger().warn(
                "Panel scan timed out — no QR tag confirmed. "
                "stream_processor will use factor=1.0 (no spectral correction)."
            )
            rclpy.shutdown()

    # ------------------------------------------------------------------
    # Calibration factor computation
    # ------------------------------------------------------------------

    def _publish_calibration(self) -> None:
        self._done = True

        raw = self._last_raw
        bboxes = self._last_bboxes
        if raw is None or all(b is None for b in bboxes):
            self.get_logger().error(
                "No valid frame stored — cannot compute calibration."
            )
            rclpy.shutdown()
            return

        h, w = raw.shape[:2]
        slice_w = w // NUM_SLICES

        # dtype_max for normalisation: 65535 for 16-bit, 255 for 8-bit.
        if np.issubdtype(raw.dtype, np.integer):
            dtype_max = float(np.iinfo(raw.dtype).max)
        else:
            dtype_max = 1.0

        # Build the fallback corners from the first slice that detected the QR.
        # Used for any slice whose own detection failed.
        fallback_pts = next(
            b.reshape(4, 2).astype(np.float32) for b in bboxes if b is not None
        )
        fallback_idx = next(i for i, b in enumerate(bboxes) if b is not None)

        factors = []
        for i in range(NUM_SLICES):
            band = raw[:, i * slice_w: (i + 1) * slice_w]

            if bboxes[i] is not None:
                pts = bboxes[i].reshape(4, 2).astype(np.float32)
                corners_note = ""
            else:
                pts = fallback_pts
                corners_note = (
                    f" (QR not detected in this slice — "
                    f"using corners from slice {fallback_idx})"
                )

            panel_pts_int = np.round(_panel_roi_from_qr(pts)).astype(np.int32)

            mask = np.zeros(band.shape[:2], dtype=np.uint8)
            cv2.fillConvexPoly(mask, panel_pts_int, 255)

            pixels = band[mask > 0]
            if pixels.size == 0:
                self.get_logger().error(
                    f"Slice {i} ({CAM0_BAND_NM[i]} nm): panel mask is empty"
                    f"{corners_note}. Check panel position. "
                    "Falling back to factor=1.0."
                )
                factors.append(1.0)
                continue

            mean_dn = float(np.mean(pixels.astype(np.float64)))
            if mean_dn <= 0.0:
                self.get_logger().error(
                    f"Slice {i} ({CAM0_BAND_NM[i]} nm): mean panel DN is zero — "
                    "possible dead camera. Falling back to factor=1.0."
                )
                factors.append(1.0)
                continue

            # factor = albedo / (panel_DN / dtype_max)
            # C++ applies: corrected = (pixel_DN / dtype_max) * factor
            #            = (pixel_DN / panel_DN) * albedo  →  true reflectance
            # Irradiance at scan time is encoded in panel_DN; no separate
            # spectrometer correction is applied (panel may be in shade).
            factor = self._albedo[i] / (mean_dn / dtype_max)
            factors.append(factor)
            self.get_logger().info(
                f"Slice {i} ({CAM0_BAND_NM[i]} nm){corners_note}: "
                f"mean_DN={mean_dn:.1f}  albedo={self._albedo[i]:.4f}  "
                f"factor={factor:.4f}"
            )

        msg = Float32MultiArray()
        msg.data = [float(f) for f in factors]
        self._pub.publish(msg)
        self.get_logger().info(
            f"Panel calibration published ({NUM_SLICES} bands) on /panel_cal/irradiance"
        )
        rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = PanelScanNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
