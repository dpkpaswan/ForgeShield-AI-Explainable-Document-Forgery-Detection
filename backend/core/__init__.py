"""
ForgeShield AI — Core Detection Engine
Multi-layered document forensics with ELA, Grad-CAM, font analysis,
bilingual OCR (English + Tamil), and Gemini-powered explainability.
"""

from .detector import run_ela, generate_gradcam_heatmap, check_font_inconsistency, analyze_document
from .ocr import extract_text, detect_text_anomalies
from .explainer import generate_report

__all__ = [
    "run_ela",
    "generate_gradcam_heatmap",
    "check_font_inconsistency",
    "analyze_document",
    "extract_text",
    "detect_text_anomalies",
    "generate_report",
]
