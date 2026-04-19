"""
ocr.py — Bilingual OCR (English + Tamil) with anomaly detection.

Uses EasyOCR with a two-reader strategy:
  • Fast pass: English-only reader (loads quickly, handles most docs)
  • Tamil pass: Bilingual reader (lazy-loaded only when Tamil is detected)

Runs OCR only ONCE per image and caches anomalies for detect_text_anomalies().
"""

import re
import cv2
import numpy as np

# ── Patch EasyOCR to tolerate model checkpoint mismatches ────
import torch.nn as nn

_original_load_state_dict = nn.Module.load_state_dict

def _flexible_load_state_dict(self, state_dict, strict=True, **kwargs):
    """Drop keys with shape mismatches, then load with strict=False."""
    try:
        return _original_load_state_dict(self, state_dict, strict=strict, **kwargs)
    except RuntimeError as e:
        if "size mismatch" in str(e):
            model_state = self.state_dict()
            filtered = {
                k: v for k, v in state_dict.items()
                if k in model_state and v.shape == model_state[k].shape
            }
            skipped = set(state_dict.keys()) - set(filtered.keys())
            print(f"[OCR] Dropped {len(skipped)} mismatched keys: {skipped}")
            return _original_load_state_dict(self, filtered, strict=False, **kwargs)
        raise

nn.Module.load_state_dict = _flexible_load_state_dict

import easyocr

# Tamil Unicode range
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")

# ── Two-reader strategy ──────────────────────
# English reader: loaded at startup (fast, ~2s)
# Tamil reader:   loaded lazily only when Tamil chars are detected
_reader_en = None
_reader_bilingual = None


def _get_reader(tamil=False):
    """Return cached EasyOCR reader. Tamil reader is lazy-loaded on demand."""
    global _reader_en, _reader_bilingual

    if tamil:
        if _reader_bilingual is None:
            print("[OCR] Tamil detected — loading bilingual reader (en + ta)...")
            try:
                _reader_bilingual = easyocr.Reader(["en", "ta"], gpu=False)
                print("[OCR] Bilingual reader ready")
            except Exception as e:
                print(f"[OCR] Bilingual reader failed ({e}), using English-only")
                _reader_bilingual = _reader_en or easyocr.Reader(["en"], gpu=False)
        return _reader_bilingual
    else:
        if _reader_en is None:
            print("[OCR] Loading English reader...")
            _reader_en = easyocr.Reader(["en"], gpu=False)
            print("[OCR] English reader ready")
        return _reader_en


# Pre-load English reader at import time (fast, ~2s)
print("[OCR] Pre-loading English reader...")
_get_reader(tamil=False)


def _load_image(file_path: str) -> np.ndarray | None:
    """Load image from path; for PDFs, render first page."""
    if file_path.lower().endswith(".pdf"):
        try:
            import fitz
            doc = fitz.open(file_path)
            page = doc[0]
            pix = page.get_pixmap(dpi=200)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            doc.close()
            if pix.n == 4:  # RGBA
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            return img
        except Exception as e:
            print(f"[OCR] PDF load error: {e}")
            return None
    else:
        return cv2.imread(file_path)


def _has_tamil(results: list) -> bool:
    """Check if any OCR result contains Tamil Unicode characters."""
    for _, text, _ in results:
        if _TAMIL_RE.search(text):
            return True
    return False


# ═══════════════════════════════════════════════
#  Text Extraction (single OCR pass)
# ═══════════════════════════════════════════════
def extract_text(file_path: str) -> dict:
    """
    Run EasyOCR on the file. Uses English-only reader first;
    if Tamil is detected, re-runs with bilingual reader for accuracy.

    Returns
    -------
    dict with keys:
        text, language_detected, word_count,
        tamil_words, english_words, confidence_avg
    """
    img = _load_image(file_path)
    if img is None:
        return {
            "text": "",
            "language_detected": "Unknown",
            "word_count": 0,
            "tamil_words": [],
            "english_words": [],
            "confidence_avg": 0.0,
        }

    # Fast pass — English only
    reader = _get_reader(tamil=False)
    results = reader.readtext(img)

    # If Tamil detected, re-run with bilingual reader for better accuracy
    if _has_tamil(results):
        print("[OCR] Tamil chars found — re-running with bilingual reader")
        reader = _get_reader(tamil=True)
        results = reader.readtext(img)

    # Process results
    all_text_parts = []
    tamil_words = []
    english_words = []
    confidences = []

    for bbox, text, conf in results:
        all_text_parts.append(text)
        confidences.append(conf)

        words = text.split()
        for w in words:
            if _TAMIL_RE.search(w):
                tamil_words.append(w)
            else:
                english_words.append(w)

    full_text = " ".join(all_text_parts)
    word_count = len(tamil_words) + len(english_words)

    if tamil_words and english_words:
        language_detected = "Mixed"
    elif tamil_words:
        language_detected = "Tamil"
    else:
        language_detected = "English"

    confidence_avg = round(float(np.mean(confidences)) if confidences else 0.0, 4)

    # Cache anomalies from this same OCR pass
    _cache_anomalies(results)

    return {
        "text": full_text,
        "language_detected": language_detected,
        "word_count": word_count,
        "tamil_words": tamil_words,
        "english_words": english_words,
        "confidence_avg": confidence_avg,
    }


# ═══════════════════════════════════════════════
#  Anomaly cache — computed during extract_text,
#  retrieved by detect_text_anomalies.
# ═══════════════════════════════════════════════
_anomaly_cache = {"anomalies": [], "anomaly_score": 0.0}


def _cache_anomalies(results: list) -> None:
    """Compute anomalies from OCR results and cache them."""
    global _anomaly_cache

    if not results:
        _anomaly_cache = {"anomalies": [], "anomaly_score": 0.0}
        return

    heights = []
    entries = []
    for bbox, text, conf in results:
        ys = [pt[1] for pt in bbox]
        h = max(ys) - min(ys)
        heights.append(h)
        entries.append({"text": text, "conf": conf, "height": h})

    heights_arr = np.array(heights)
    mean_h = float(heights_arr.mean())
    std_h = float(heights_arr.std()) if len(heights_arr) > 1 else 0

    anomalies = []

    for entry in entries:
        # Low confidence — only flag very poor OCR reads
        if entry["conf"] < 0.25:
            anomalies.append({
                "type": "low_confidence",
                "text": entry["text"],
                "confidence": round(float(entry["conf"]), 3),
                "details": f"Confidence {entry['conf']:.1%} is below 25% threshold.",
            })

        # Size outlier (> 3 std from mean)
        if std_h > 0:
            z = abs(entry["height"] - mean_h) / std_h
            if z > 3.0:
                direction = "larger" if entry["height"] > mean_h else "smaller"
                anomalies.append({
                    "type": "size_anomaly",
                    "text": entry["text"],
                    "height": round(float(entry["height"]), 1),
                    "details": f"Text region is significantly {direction} than average "
                               f"(height {entry['height']:.0f}px vs mean {mean_h:.0f}px, z={z:.1f}).",
                })

    anomaly_score = min(1.0, len(anomalies) * 0.1)

    _anomaly_cache = {
        "anomalies": anomalies,
        "anomaly_score": round(anomaly_score, 4),
    }


def detect_text_anomalies(file_path: str) -> dict:
    """
    Return cached anomalies computed during extract_text().
    MUST be called AFTER extract_text() on the same file.
    """
    return _anomaly_cache
