"""Image preprocessing for receipt OCR: orient → upscale → denoise → deskew →
(optional) perspective correction → CLAHE.

Returns a clean grayscale numpy array for PaddleOCR plus a PNG-encoded bytes
blob for the OpenAI multimodal API."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageOps


TARGET_SHORT_SIDE = 1600  # ~300 DPI equivalent for an A6 receipt
DEBUG_DIR = Path(os.environ.get("OOCR_DEBUG_DIR", "debug"))


def _load_oriented_grayscale(path: str) -> np.ndarray:
    pil = Image.open(path)
    pil = ImageOps.exif_transpose(pil).convert("L")
    return np.array(pil)


def _upscale(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    short = min(h, w)
    if short >= TARGET_SHORT_SIDE:
        return img
    scale = TARGET_SHORT_SIDE / short
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)


def _denoise(img: np.ndarray) -> np.ndarray:
    # h=10 is mild; aggressive denoise erodes Arabic diacritics.
    return cv2.fastNlMeansDenoising(img, None, h=10, templateWindowSize=7, searchWindowSize=21)


def _estimate_skew_angle(img: np.ndarray) -> float:
    """Return rotation in degrees needed to make text horizontal."""
    bin_img = cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 10
    )
    coords = np.column_stack(np.where(bin_img > 0))
    if coords.size == 0:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    # cv2 returns angle in [-90, 0). Normalize to small absolute value.
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    # Don't bother rotating tiny angles — costs interpolation quality.
    return angle if abs(angle) > 0.5 else 0.0


def _deskew(img: np.ndarray) -> np.ndarray:
    angle = _estimate_skew_angle(img)
    if angle == 0.0:
        return img
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        img, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _maybe_perspective_correct(img: np.ndarray) -> np.ndarray:
    """If a clear receipt quadrilateral occupies <70% of the frame, warp it
    to a flat rectangle. Otherwise leave the image alone."""
    h, w = img.shape[:2]
    blur = cv2.GaussianBlur(img, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img

    largest = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(largest) / float(h * w)
    if area_ratio >= 0.70 or area_ratio < 0.10:
        # Fills the frame already, or too small to be the receipt.
        return img

    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
    if len(approx) != 4:
        return img

    pts = approx.reshape(4, 2).astype("float32")
    # Order points: tl, tr, br, bl
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()
    ordered = np.array([
        pts[np.argmin(s)],      # tl
        pts[np.argmin(diff)],   # tr
        pts[np.argmax(s)],      # br
        pts[np.argmax(diff)],   # bl
    ], dtype="float32")

    (tl, tr, br, bl) = ordered
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_w = int(max(width_a, width_b))
    max_h = int(max(height_a, height_b))
    if max_w < 100 or max_h < 100:
        return img

    dst = np.array([
        [0, 0],
        [max_w - 1, 0],
        [max_w - 1, max_h - 1],
        [0, max_h - 1],
    ], dtype="float32")
    M = cv2.getPerspectiveTransform(ordered, dst)
    return cv2.warpPerspective(img, M, (max_w, max_h))


def _clahe(img: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(img)


def preprocess(
    path: str,
    save_debug: bool = False,
    mode: str = "light",
) -> tuple[np.ndarray, bytes]:
    """Prepare an image for the LLM.

    Args:
        path: image file.
        save_debug: write the result to debug/<stem>_preprocessed.png.
        mode: 'light' (default) keeps the image close to the original —
              EXIF-orient + (small-image-only) upscale, in color. This is
              best for clean phone photos: aggressive enhancement was
              washing out detail and dropping items.
              'full' runs the OpenCV pipeline (denoise + deskew +
              perspective correction + CLAHE) on a grayscale copy. Useful
              for low-quality scans; can over-process clean photos.

    Returns:
        (image_ndarray, png_bytes). The PNG is what we send to gpt-4o.
    """
    if mode not in {"light", "full"}:
        raise ValueError(f"Unknown preprocessing mode: {mode!r}")

    if mode == "light":
        # Keep the image colour and original sharpness.
        from PIL import Image as _Image
        pil = _Image.open(path)
        pil = ImageOps.exif_transpose(pil).convert("RGB")
        img_rgb = np.array(pil)
        # Cheap upscale only if the image is genuinely tiny.
        h, w = img_rgb.shape[:2]
        if min(h, w) < 800:
            scale = 800 / min(h, w)
            img_rgb = cv2.resize(
                img_rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC
            )
        img_for_save = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        ok, encoded = cv2.imencode(".png", img_for_save)
        if not ok:
            raise RuntimeError("Failed to PNG-encode preprocessed image.")
        png_bytes = encoded.tobytes()
        if save_debug:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            stem = Path(path).stem
            cv2.imwrite(str(DEBUG_DIR / f"{stem}_preprocessed.png"), img_for_save)
        return img_rgb, png_bytes

    # mode == "full" — heavy pipeline, grayscale.
    img = _load_oriented_grayscale(path)
    img = _upscale(img)
    img = _denoise(img)
    img = _deskew(img)
    img = _maybe_perspective_correct(img)
    img = _clahe(img)

    ok, encoded = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("Failed to PNG-encode preprocessed image.")
    png_bytes = encoded.tobytes()

    if save_debug:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        stem = Path(path).stem
        cv2.imwrite(str(DEBUG_DIR / f"{stem}_preprocessed.png"), img)

    return img, png_bytes


__all__ = ["preprocess"]
