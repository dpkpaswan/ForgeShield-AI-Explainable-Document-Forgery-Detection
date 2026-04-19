"""
ForgeShield AI — FastAPI Backend
=================================
Exposes analysis endpoints that run the full
detection → OCR → Gemini explainability pipeline.
"""

import os
import time
import uuid
import tempfile
from typing import List

import numpy as np

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core import analyze_document, extract_text, detect_text_anomalies, generate_report

load_dotenv()

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10_485_760))  # 10 MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

# ── App ──────────────────────────────────────
app = FastAPI(
    title="ForgeShield AI API",
    version="1.0.0",
    description="AI-powered document forgery detection with ELA, Grad-CAM, "
                "font analysis, bilingual OCR, and Gemini explainability.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ──────────────────────────────────
def _get_extension(filename: str) -> str:
    """Return lowercased file extension including the dot."""
    _, ext = os.path.splitext(filename or "")
    return ext.lower()


def _validate_file(file: UploadFile) -> None:
    """Raise HTTPException if file is invalid."""
    ext = _get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. "
                   f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}.",
        )


async def _save_temp(file: UploadFile) -> str:
    """Read upload into a temp file, return its path."""
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(content)} bytes). "
                   f"Max allowed: {MAX_FILE_SIZE} bytes.",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    ext = _get_extension(file.filename)
    tmp_name = f"forge_{uuid.uuid4().hex}{ext}"
    tmp_path = os.path.join(tempfile.gettempdir(), tmp_name)

    with open(tmp_path, "wb") as f:
        f.write(content)

    return tmp_path


def _cleanup(path: str) -> None:
    """Delete a temp file silently."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _numpy_safe(obj):
    """Recursively convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _numpy_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_numpy_safe(i) for i in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


class PipelineLogger:
    """Collect timestamped log entries during pipeline execution."""

    def __init__(self):
        self._start = time.perf_counter()
        self.entries = []

    def log(self, stage: str, message: str):
        elapsed = round((time.perf_counter() - self._start) * 1000)
        entry = {"ms": elapsed, "stage": stage, "message": message}
        self.entries.append(entry)
        print(f"  [{elapsed:>6}ms] [{stage}] {message}")


def _run_pipeline(tmp_path: str, filename: str) -> dict:
    """Execute the full detection → OCR → explainer pipeline with logging."""
    start = time.perf_counter()
    log = PipelineLogger()

    log.log("UPLOAD", f"File received: {filename}")

    # 1. Detection (ELA + Grad-CAM + Font)
    log.log("ELA", "Starting Error Level Analysis...")
    t0 = time.perf_counter()
    detection = analyze_document(tmp_path)
    dt = round((time.perf_counter() - t0) * 1000)
    log.log("ELA", f"ELA score: {detection['ela_score']:.4f} ({dt}ms)")

    if detection.get("gradcam_heatmap_b64"):
        log.log("GRAD-CAM", f"Grad-CAM heatmap generated via PyTorch ResNet50")
    else:
        log.log("GRAD-CAM", "Grad-CAM skipped or failed")

    if detection.get("fonts_detected"):
        log.log("FONTS", f"Detected {len(detection['fonts_detected'])} font(s): {', '.join(detection['fonts_detected'][:5])}")
    else:
        log.log("FONTS", "No font data (image file or no text)")

    log.log("SCORE", f"Overall forgery score: {detection['overall_score']:.4f} → {'FORGED' if detection['is_forged'] else 'AUTHENTIC'}")

    # 2. OCR
    log.log("OCR", "Running bilingual OCR (English + Tamil)...")
    t0 = time.perf_counter()
    ocr_text_result = extract_text(tmp_path)
    ocr_anomaly_result = detect_text_anomalies(tmp_path)
    dt = round((time.perf_counter() - t0) * 1000)
    ocr_combined = {**ocr_text_result, **ocr_anomaly_result}
    log.log("OCR", f"Extracted {ocr_combined.get('word_count', 0)} words in {dt}ms | Language: {ocr_combined.get('language_detected', 'Unknown')} | Confidence: {ocr_combined.get('confidence_avg', 0):.1%}")

    anomaly_count = len(ocr_combined.get("anomalies", []))
    if anomaly_count:
        log.log("ANOMALY", f"Detected {anomaly_count} text anomalie(s) | Score: {ocr_combined.get('anomaly_score', 0):.2%}")
    else:
        log.log("ANOMALY", "No text anomalies detected")

    # 3. Explainability (Gemini or fallback)
    log.log("AI", "Generating forensic report (gemini-2.5-flash → gemma-3-27b-it → rule-based)...")
    t0 = time.perf_counter()
    report = generate_report(detection, ocr_combined)
    dt = round((time.perf_counter() - t0) * 1000)
    log.log("AI", f"Report generated in {dt}ms | Verdict: {report.get('verdict', 'N/A')} | Confidence: {report.get('confidence_level', 'N/A')}")

    elapsed_ms = round((time.perf_counter() - start) * 1000)
    log.log("DONE", f"Pipeline complete in {elapsed_ms}ms")

    # 4. Build response
    return _numpy_safe({
        "filename": filename,
        "is_forged": detection["is_forged"],
        "overall_score": detection["overall_score"],
        "ela_score": detection["ela_score"],
        "font_score": detection["font_score"],
        "ela_heatmap_b64": detection["ela_heatmap_b64"],
        "gradcam_heatmap_b64": detection["gradcam_heatmap_b64"],
        "fonts_detected": detection["fonts_detected"],
        "ocr": {
            "text": ocr_combined.get("text", ""),
            "language_detected": ocr_combined.get("language_detected", "Unknown"),
            "word_count": ocr_combined.get("word_count", 0),
            "tamil_words": ocr_combined.get("tamil_words", []),
            "english_words": ocr_combined.get("english_words", []),
            "confidence_avg": ocr_combined.get("confidence_avg", 0),
        },
        "anomalies": ocr_combined.get("anomalies", []),
        "anomaly_score": ocr_combined.get("anomaly_score", 0),
        "report": report,
        "processing_time_ms": elapsed_ms,
        "pipeline_logs": log.entries,
    })


# ── Routes ───────────────────────────────────
@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "forgeshield-ai"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    """
    Upload a single document (JPG, PNG, PDF) and receive a full
    forgery analysis with detection scores, heatmaps, OCR, and AI report.
    """
    _validate_file(file)
    tmp_path = await _save_temp(file)

    try:
        result = _run_pipeline(tmp_path, file.filename)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(exc)}",
        )
    finally:
        _cleanup(tmp_path)
        # Also cleanup any PDF→image temp file created by detector
        _cleanup(tmp_path + "_page0.png")

    return result


@app.post("/api/batch")
async def batch_analyze(files: List[UploadFile] = File(...)):
    """
    Upload multiple documents and receive a list of analysis results.
    """
    results = []
    for file in files:
        tmp_path = None
        try:
            _validate_file(file)
            tmp_path = await _save_temp(file)
            result = _run_pipeline(tmp_path, file.filename)
            results.append(result)
        except HTTPException as he:
            results.append({
                "filename": file.filename,
                "error": he.detail,
            })
        except Exception as exc:
            results.append({
                "filename": file.filename,
                "error": f"Analysis failed: {str(exc)}",
            })
        finally:
            if tmp_path:
                _cleanup(tmp_path)
                _cleanup(tmp_path + "_page0.png")

    return results


# ── Entrypoint ───────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
