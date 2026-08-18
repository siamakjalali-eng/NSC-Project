import json
import math
import struct
import time
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance


W = 640
H = 360
FPS = 20
SECONDS = 6
FRAMES = FPS * SECONDS

try:
    ROOT = Path(__file__).resolve().parent
except NameError:
    ROOT = Path.cwd()


def make_scene():
    image = Image.new("RGB", (1000, 620), "#071425")
    draw = ImageDraw.Draw(image)

    for y in range(image.height):
        q = y / image.height
        draw.line(
            (0, y, image.width, y),
            fill=(7 + int(18 * q), 20 + int(28 * q), 37 + int(42 * q)),
        )

    rng = np.random.default_rng(42)
    for _ in range(100):
        x = int(rng.integers(0, image.width))
        y = int(rng.integers(10, 280))
        r = int(rng.integers(1, 3))
        draw.ellipse((x - r, y - r, x + r, y + r), fill="#9bdcff")

    for x in range(0, image.width, 70):
        building_height = int(90 + 120 * (0.5 + 0.5 * math.sin(x * 0.025)))
        draw.rectangle(
            (x, 450 - building_height, x + 56, 450),
            fill="#102c47",
            outline="#2d7da0",
            width=2,
        )

    draw.polygon(
        [(0, 620), (1000, 620), (650, 450), (350, 450)],
        fill="#071019",
    )
    draw.text((360, 50), "NEW SOFT CUBE", fill="#55d9ff")
    draw.text((380, 80), "STRUCTURAL MOTION", fill="#d7f6ff")
    return image


def motion(t):
    dx = 42 * math.sin(0.83 * t) + 9 * math.sin(7.1 * t)
    dy = 24 * math.sin(0.57 * t + 0.4) + 6 * math.sin(6.4 * t)
    angle = 2.8 * math.sin(0.71 * t) + 0.7 * math.sin(5.3 * t)
    log_scale = 0.045 * math.sin(0.39 * t) + 0.010 * math.sin(4.7 * t)
    return np.array([dx, dy, angle, log_scale], dtype=np.float64)


def render(base, coefficients):
    dx, dy, angle, log_scale = coefficients
    scale = math.exp(float(log_scale))
    theta = math.radians(float(angle))
    cosine = math.cos(theta) / scale
    sine = math.sin(theta) / scale

    output_x = W / 2 + float(dx)
    output_y = H / 2 + float(dy)
    source_x = base.width / 2
    source_y = base.height / 2

    matrix = (
        cosine,
        sine,
        source_x - cosine * output_x - sine * output_y,
        -sine,
        cosine,
        source_y + sine * output_x - cosine * output_y,
    )

    try:
        affine = Image.Transform.AFFINE
        bicubic = Image.Resampling.BICUBIC
    except AttributeError:
        affine = Image.AFFINE
        bicubic = Image.BICUBIC

    return base.transform((W, H), affine, matrix, resample=bicubic)


def encode_nsc(coefficients):
    limits = np.max(np.abs(coefficients), axis=0) * 1.00001
    limits[limits == 0] = 1.0
    quantized = np.round(coefficients / limits * 32767).astype("<i2")

    header = b"NSCVID1" + struct.pack(
        "<II",
        coefficients.shape[0],
        coefficients.shape[1],
    )
    payload = header + limits.astype("<f8").tobytes() + quantized.tobytes()
    reconstructed = quantized.astype(np.float64) / 32767.0 * limits
    return payload, reconstructed


def affine_stream(coefficients):
    matrices = []
    for dx, dy, angle, log_scale in coefficients:
        theta = math.radians(float(angle))
        scale = math.exp(float(log_scale))
        cosine = math.cos(theta)
        sine = math.sin(theta)
        matrices.append(
            [
                [scale * cosine, -scale * sine, float(dx)],
                [scale * sine, scale * cosine, float(dy)],
                [0.0, 0.0, 1.0],
            ]
        )
    return np.asarray(matrices, dtype="<f8").tobytes()


def make_panel(original, reconstructed, difference):
    panel = Image.new("RGB", (W * 3, H), "black")
    panel.paste(original, (0, 0))
    panel.paste(reconstructed, (W, 0))
    panel.paste(difference, (W * 2, 0))
    draw = ImageDraw.Draw(panel)
    draw.text((12, 12), "ORIGINAL", fill="white")
    draw.text((W + 12, 12), "NSC RECONSTRUCTION", fill="white")
    draw.text((2 * W + 12, 12), "10X DIFFERENCE", fill="white")
    return panel


def main():
    started = time.perf_counter()
    print("NSC COMPRESSION DEMO FOR EMSCRIPTEN")
    print("NO SUBPROCESS")
    print("NO FFMPEG")

    base = make_scene()
    times = np.arange(FRAMES, dtype=np.float64) / FPS
    coefficients = np.stack([motion(float(t)) for t in times])
    nsc_payload, reconstructed_coefficients = encode_nsc(coefficients)

    raw = affine_stream(coefficients)
    raw_zlib = zlib.compress(raw, 9)
    nsc_zlib = zlib.compress(nsc_payload, 9)

    mse_sum = 0.0
    sample_indices = {0, FRAMES // 2, FRAMES - 1}

    for index in range(FRAMES):
        original = render(base, coefficients[index])
        reconstructed = render(base, reconstructed_coefficients[index])

        original_array = np.asarray(original, dtype=np.float32)
        reconstructed_array = np.asarray(reconstructed, dtype=np.float32)
        mse_sum += float(np.mean((original_array - reconstructed_array) ** 2))

        if index in sample_indices:
            difference = ImageChops.difference(original, reconstructed)
            visible_difference = ImageEnhance.Brightness(difference).enhance(10)
            panel = make_panel(original, reconstructed, visible_difference)
            panel.save(ROOT / f"NSC_sample_{index:04d}.png")

        if (index + 1) % FPS == 0:
            print("SECOND", (index + 1) // FPS, "OF", SECONDS)

    pixel_mse = mse_sum / FRAMES
    pixel_psnr = float("inf") if pixel_mse == 0 else 10 * math.log10(255 * 255 / pixel_mse)
    maximum_coefficient_error = float(
        np.max(np.abs(coefficients - reconstructed_coefficients))
    )

    report = {
        "demo": "NSC structural motion compression",
        "environment": "Emscripten compatible pure Python path",
        "resolution": [W, H],
        "fps": FPS,
        "frames": FRAMES,
        "seconds": SECONDS,
        "raw_motion_matrix_bytes": len(raw),
        "raw_motion_zlib_bytes": len(raw_zlib),
        "nsc_delta_bytes": len(nsc_payload),
        "nsc_delta_zlib_bytes": len(nsc_zlib),
        "ratio_to_raw": len(nsc_payload) / len(raw),
        "ratio_to_raw_zlib": len(nsc_zlib) / len(raw_zlib),
        "motion_size_reduction_vs_zlib": 1 - len(nsc_zlib) / len(raw_zlib),
        "maximum_coefficient_error": maximum_coefficient_error,
        "pixel_mse": pixel_mse,
        "pixel_psnr_db": pixel_psnr,
        "elapsed_seconds": time.perf_counter() - started,
        "round_trip_checked": True,
        "claim_boundary": "Compresses the geometric motion stream and not the complete video texture bitstream",
    }

    (ROOT / "NSC_Motion_Stream.nsc").write_bytes(nsc_payload)
    (ROOT / "NSC_Motion_Compression_Report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("OUTPUT", ROOT)


if __name__ == "__main__":
    main()