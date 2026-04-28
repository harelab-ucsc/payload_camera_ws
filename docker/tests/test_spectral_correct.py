#!/usr/bin/env python3
"""
docker/tests/test_spectral_correct.py

Unit tests for the stream_processor.spectral_correct pybind11 extension.
No ROS required — imports the .so directly. Run with:
    pytest docker/tests/test_spectral_correct.py -v
"""

import numpy as np
import pytest

from stream_processor.spectral_correct import process_cam0, process_cam1

# Source-of-truth: src/stream_processor/src/spectral_correct/process.hpp
CAM0_ALIGNMENT = (0, 2, 9, 14)

H = 8
W = 16          # 4 slices of 4 px each — small for exact-arithmetic asserts
SLICE_W = W // 4


def make_gradient_u16():
    """Each slice gets a distinct constant offset so cross-slice mixups fail."""
    img = np.zeros((H, W), dtype=np.uint16)
    for i in range(4):
        img[:, i * SLICE_W:(i + 1) * SLICE_W] = (i + 1) * 1000
    return img


# ── process_cam0 ─────────────────────────────────────────────────────────────

def test_cam0_per_band_division():
    img = make_gradient_u16()
    spec = np.zeros(18, dtype=np.float32)
    spec[CAM0_ALIGNMENT[0]] = 10.0
    spec[CAM0_ALIGNMENT[1]] = 11.0
    spec[CAM0_ALIGNMENT[2]] = 12.0
    spec[CAM0_ALIGNMENT[3]] = 13.0

    outs = process_cam0(img, spec)
    assert len(outs) == 4
    expected_divisors = (10.0, 11.0, 12.0, 13.0)
    for i, out in enumerate(outs):
        assert out.dtype == np.float32
        assert out.shape == (H, SLICE_W)
        expected = np.full((H, SLICE_W), (i + 1) * 1000 / expected_divisors[i],
                           dtype=np.float32)
        np.testing.assert_allclose(out, expected, rtol=1e-5)


def test_cam0_owns_memory():
    """Output must outlive the input — pybind must allocate fresh buffers."""
    img = make_gradient_u16()
    spec = np.ones(18, dtype=np.float32)
    outs = process_cam0(img, spec)
    img[...] = 0   # mutate input
    assert outs[0][0, 0] != 0  # output unaffected -> not a view


def test_cam0_zero_irradiance_passthrough():
    """spec_vals[i] == 0 for slice i -> identity (cast to float32)."""
    img = make_gradient_u16()
    spec = np.zeros(18, dtype=np.float32)
    # Leave all 4 alignment indices at 0 -> all slices identity
    outs = process_cam0(img, spec)
    for i, out in enumerate(outs):
        expected = img[:, i * SLICE_W:(i + 1) * SLICE_W].astype(np.float32)
        np.testing.assert_array_equal(out, expected)


def test_cam0_nan_inf_passthrough():
    img = make_gradient_u16()
    spec = np.zeros(18, dtype=np.float32)
    spec[CAM0_ALIGNMENT[0]] = float('nan')
    spec[CAM0_ALIGNMENT[1]] = float('inf')
    spec[CAM0_ALIGNMENT[2]] = -5.0           # negative -> identity too
    spec[CAM0_ALIGNMENT[3]] = 13.0           # the only one that should divide

    outs = process_cam0(img, spec)
    for i in range(3):
        expected = img[:, i * SLICE_W:(i + 1) * SLICE_W].astype(np.float32)
        np.testing.assert_array_equal(outs[i], expected)
    expected3 = img[:, 3 * SLICE_W:].astype(np.float32) / 13.0
    np.testing.assert_allclose(outs[3], expected3, rtol=1e-5)


def test_cam0_none_spec_identity():
    img = make_gradient_u16()
    outs = process_cam0(img, None)
    for i, out in enumerate(outs):
        expected = img[:, i * SLICE_W:(i + 1) * SLICE_W].astype(np.float32)
        np.testing.assert_array_equal(out, expected)


def test_cam0_short_spec_identity_for_missing_indices():
    """spec_vals shorter than CAM0_ALIGNMENT[max]=14 -> identity for those."""
    img = make_gradient_u16()
    spec = np.array([10.0, 0, 11.0], dtype=np.float32)  # len 3 < 14
    outs = process_cam0(img, spec)
    # slice 0 -> spec[0]=10, slice 1 -> spec[2]=11, slices 2/3 -> identity
    np.testing.assert_allclose(
        outs[0], img[:, 0:SLICE_W].astype(np.float32) / 10.0, rtol=1e-5)
    np.testing.assert_allclose(
        outs[1], img[:, SLICE_W:2 * SLICE_W].astype(np.float32) / 11.0, rtol=1e-5)
    np.testing.assert_array_equal(
        outs[2], img[:, 2 * SLICE_W:3 * SLICE_W].astype(np.float32))
    np.testing.assert_array_equal(
        outs[3], img[:, 3 * SLICE_W:].astype(np.float32))


def test_cam0_uint8_input():
    img = (make_gradient_u16() // 8).astype(np.uint8)
    spec = np.full(18, 2.0, dtype=np.float32)
    outs = process_cam0(img, spec)
    for i, out in enumerate(outs):
        assert out.dtype == np.float32
        expected = img[:, i * SLICE_W:(i + 1) * SLICE_W].astype(np.float32) / 2.0
        np.testing.assert_allclose(out, expected, rtol=1e-5)


def test_cam0_rejects_non_2d():
    img3d = np.zeros((H, W, 3), dtype=np.uint8)
    with pytest.raises(Exception):
        process_cam0(img3d, np.ones(18, dtype=np.float32))


def test_cam0_rejects_non_4_slices():
    img = make_gradient_u16()
    with pytest.raises(Exception):
        process_cam0(img, np.ones(18, dtype=np.float32), num_slices=3)


# ── process_cam1 ─────────────────────────────────────────────────────────────

def make_bayer_u16(width=W):
    """Synthetic SBGGR16 mosaic: B in even/even, R in odd/odd, G elsewhere."""
    img = np.zeros((H, width), dtype=np.uint16)
    img[0::2, 0::2] = 4000   # B
    img[0::2, 1::2] = 8000   # G
    img[1::2, 0::2] = 12000  # G
    img[1::2, 1::2] = 16000  # R
    return img


def test_cam1_shapes_and_dtype():
    img = make_bayer_u16()
    outs = process_cam1(img)
    assert len(outs) == 4
    for out in outs:
        assert out.shape == (H, SLICE_W, 3)
        assert out.dtype == np.uint16


def test_cam1_uint8_input():
    img = (make_bayer_u16() // 64).astype(np.uint8)
    outs = process_cam1(img)
    for out in outs:
        assert out.shape == (H, SLICE_W, 3)
        assert out.dtype == np.uint8


def test_cam1_debayer_produces_color():
    """Synthetic mosaic should debayer into nontrivial RGB (not all zeros, not
    a flat grey)."""
    img = make_bayer_u16()
    outs = process_cam1(img)
    for out in outs:
        # All three channels should have some signal
        for c in range(3):
            assert out[:, :, c].max() > 0
        # And the image shouldn't collapse to a single channel
        assert not np.array_equal(out[:, :, 0], out[:, :, 1])


def test_cam1_owns_memory():
    img = make_bayer_u16()
    outs = process_cam1(img)
    img[...] = 0
    assert outs[0].max() > 0


def test_cam1_rejects_odd_slice_width():
    """slice_w must be even to preserve Bayer phase."""
    # width 18 / 4 = 4 with remainder; but more clearly: width = 12 with
    # num_slices = 4 -> slice_w = 3 (odd) should fail.
    img = np.zeros((H, 12), dtype=np.uint16)
    with pytest.raises(Exception):
        process_cam1(img, num_slices=4)


def test_cam1_rejects_non_2d():
    img3d = np.zeros((H, W, 3), dtype=np.uint8)
    with pytest.raises(Exception):
        process_cam1(img3d)
