"""
explainer.py — AI-powered forensic report generation using Google Gemini.

Generates bilingual (English + Tamil) explainability reports for
document forgery analysis results.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini setup (lazy) ──────────────────────
_genai_configured = False

# Model priority: gemini-2.5-flash → gemma-3-27b-it → rule-based fallback
_MODEL_CHAIN = ["gemini-2.5-flash", "gemma-3-27b-it"]


def _configure_genai():
    """Configure the google.generativeai SDK once."""
    global _genai_configured
    if not _genai_configured:
        try:
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key or api_key == "your_key_here":
                raise ValueError("GEMINI_API_KEY not configured")
            genai.configure(api_key=api_key)
            _genai_configured = True
        except Exception as e:
            print(f"[Explainer] Gemini config failed: {e}")
    return _genai_configured


# ═══════════════════════════════════════════════
#  Gemini-powered Report
# ═══════════════════════════════════════════════
def generate_report(analysis_result: dict, ocr_result: dict) -> dict:
    """
    Build a prompt with all detection scores and anomalies, then
    call Gemini to generate a forensic report in English AND Tamil.

    Model chain: gemini-2.5-flash → gemma-3-27b-it → rule-based fallback.

    Parameters
    ----------
    analysis_result : dict
        Output from analyze_document() — contains ela_score, font_score,
        overall_score, is_forged, fonts_detected.
    ocr_result : dict
        Combined OCR data — text, anomalies, language_detected, etc.

    Returns
    -------
    dict with keys:
        verdict           : str   – "FORGED" or "AUTHENTIC"
        confidence_level  : str   – "High", "Medium", or "Low"
        reasons           : list[str]
        suspicious_sections : list[str]
        recommendation    : str
        report_en         : str   – Full English report
        report_ta         : str   – Full Tamil report
    """
    ela_score = float(analysis_result.get("ela_score", 0))
    font_score = float(analysis_result.get("font_score", 0))
    overall_score = float(analysis_result.get("overall_score", 0))
    is_forged = bool(analysis_result.get("is_forged", False))
    fonts = list(analysis_result.get("fonts_detected", []))
    anomalies = list(ocr_result.get("anomalies", []))
    anomaly_score = float(ocr_result.get("anomaly_score", 0))
    ocr_text = str(ocr_result.get("text", ""))
    language = str(ocr_result.get("language_detected", "Unknown"))
    confidence_avg = float(ocr_result.get("confidence_avg", 0))
    word_count = int(ocr_result.get("word_count", 0))

    # Build the prompt
    prompt = _build_prompt(
        ela_score=ela_score,
        font_score=font_score,
        overall_score=overall_score,
        is_forged=is_forged,
        fonts=fonts,
        anomalies=anomalies,
        anomaly_score=anomaly_score,
        ocr_text=ocr_text[:500],  # Truncate for prompt size
        language=language,
        confidence_avg=confidence_avg,
        word_count=word_count,
    )

    # Try each model in the chain
    if _configure_genai():
        import google.generativeai as genai
        for model_name in _MODEL_CHAIN:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                report_text = response.text
                print(f"[Explainer] Report generated using {model_name}")
                parsed = _parse_gemini_response(report_text, is_forged, overall_score)
                return parsed
            except Exception as e:
                print(f"[Explainer] {model_name} failed: {e}")
                continue

    # Final fallback: rule-based report
    print("[Explainer] All models failed, using rule-based report")
    return _rule_based_report(
        ela_score=ela_score,
        font_score=font_score,
        overall_score=overall_score,
        is_forged=is_forged,
        fonts=fonts,
        anomalies=anomalies,
        anomaly_score=anomaly_score,
        language=language,
        confidence_avg=confidence_avg,
    )


def _build_prompt(**kwargs) -> str:
    """Construct the Gemini prompt with analysis data."""
    verdict = "FORGED" if kwargs["is_forged"] else "AUTHENTIC"
    anomaly_texts = []
    for a in kwargs.get("anomalies", []):
        anomaly_texts.append(f"  - [{a.get('type', 'unknown')}] \"{a.get('text', '')}\" — {a.get('details', '')}")
    anomaly_block = "\n".join(anomaly_texts) if anomaly_texts else "  None detected."

    fonts_block = ", ".join(kwargs.get("fonts", [])) if kwargs.get("fonts") else "N/A (image file or no fonts)"

    return f"""You are a digital forensics expert. Analyze the following document forgery detection results and produce a structured forensic report.

## Detection Results
- **ELA Score**: {kwargs['ela_score']:.4f} (0 = uniform compression, 1 = severe inconsistency)
- **Font Inconsistency Score**: {kwargs['font_score']:.4f} (0 = consistent, 1 = highly inconsistent)
- **Overall Forgery Score**: {kwargs['overall_score']:.4f} (threshold: 0.3)
- **Verdict**: {verdict}
- **Fonts Detected**: {fonts_block}

## OCR Results
- **Language Detected**: {kwargs['language']}
- **Word Count**: {kwargs['word_count']}
- **Average OCR Confidence**: {kwargs['confidence_avg']:.2%}
- **Text Excerpt**: "{kwargs.get('ocr_text', 'N/A')[:300]}"

## Text Anomalies (anomaly_score: {kwargs.get('anomaly_score', 0):.4f})
{anomaly_block}

## Instructions
Provide the report in the following exact format with two sections:

### ENGLISH REPORT
1. **Verdict**: {verdict}
2. **Confidence Level**: High/Medium/Low
3. **Reasons for this verdict** (numbered list, 3-5 reasons)
4. **Suspicious Sections** (if any)
5. **Recommendation** for the document handler

### TAMIL REPORT (தமிழ் அறிக்கை)
Provide the COMPLETE translation of the above report in Tamil language.

Be specific, professional, and cite the exact scores in your analysis."""


def _parse_gemini_response(text: str, is_forged: bool, overall_score: float) -> dict:
    """Parse Gemini's free-form response into structured data."""
    verdict = "FORGED" if is_forged else "AUTHENTIC"

    # Determine confidence level from overall_score
    if overall_score >= 0.7:
        confidence_level = "High"
    elif overall_score >= 0.4:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"

    # Extract reasons from the response
    reasons = []
    suspicious_sections = []
    lines = text.split("\n")
    in_reasons = False
    in_suspicious = False

    for line in lines:
        stripped = line.strip()

        # Detect reason lines (numbered items)
        if any(stripped.startswith(f"{i}.") or stripped.startswith(f"{i})") for i in range(1, 10)):
            if in_reasons:
                cleaned = stripped.lstrip("0123456789.)- ").strip()
                if cleaned:
                    reasons.append(cleaned)
            elif in_suspicious:
                cleaned = stripped.lstrip("0123456789.)- ").strip()
                if cleaned:
                    suspicious_sections.append(cleaned)

        # Detect bullet points
        if stripped.startswith("-") or stripped.startswith("•"):
            cleaned = stripped.lstrip("-•● ").strip()
            if in_reasons and cleaned:
                reasons.append(cleaned)
            elif in_suspicious and cleaned:
                suspicious_sections.append(cleaned)

        # Section detection
        lower = stripped.lower()
        if "reason" in lower and ("verdict" in lower or "forgery" in lower or "this" in lower):
            in_reasons = True
            in_suspicious = False
        elif "suspicious" in lower and ("section" in lower or "area" in lower or "region" in lower):
            in_reasons = False
            in_suspicious = True
        elif "recommendation" in lower or "tamil" in lower.replace("தமிழ்", "tamil"):
            in_reasons = False
            in_suspicious = False

    # Fallback if parsing found nothing
    if not reasons:
        reasons = [
            f"Overall forgery score is {overall_score:.2%}",
            "Analysis completed using ELA and font consistency checks.",
            f"Document classified as {verdict} based on combined metrics.",
        ]

    # Split English and Tamil reports
    report_en = ""
    report_ta = ""

    # Try splitting on Tamil header markers
    tamil_markers = ["### TAMIL", "TAMIL REPORT", "தமிழ் அறிக்கை", "## தமிழ்"]
    split_idx = -1
    text_upper = text.upper()
    for marker in tamil_markers:
        idx = text.find(marker) if not marker.isupper() else text_upper.find(marker)
        if idx > 0:
            split_idx = idx
            break

    if split_idx > 0:
        report_en = text[:split_idx].strip()
        report_ta = text[split_idx:].strip()
    else:
        report_en = text.strip()
        report_ta = _generate_tamil_fallback(verdict, overall_score, reasons)

    # Extract recommendation
    recommendation = ""
    for line in lines:
        lower = line.strip().lower()
        if "recommendation" in lower and ":" in line:
            recommendation = line.split(":", 1)[1].strip().strip("*").strip()
            break

    if not recommendation:
        if is_forged:
            recommendation = "This document should be flagged for manual review by a forensic specialist. Do not accept it as authentic without further verification."
        else:
            recommendation = "This document shows no significant signs of tampering. Standard verification procedures apply."

    return {
        "verdict": verdict,
        "confidence_level": confidence_level,
        "reasons": reasons[:5],
        "suspicious_sections": suspicious_sections,
        "recommendation": recommendation,
        "report_en": report_en,
        "report_ta": report_ta,
    }


def _generate_tamil_fallback(verdict: str, score: float, reasons: list) -> str:
    """Generate a basic Tamil report when Gemini doesn't provide one."""
    verdict_ta = "போலியானது" if verdict == "FORGED" else "உண்மையானது"
    lines = [
        f"## தமிழ் அறிக்கை",
        f"",
        f"**தீர்ப்பு**: {verdict_ta}",
        f"**மொத்த மதிப்பெண்**: {score:.2%}",
        f"",
        f"### காரணங்கள்:",
    ]
    for i, reason in enumerate(reasons[:5], 1):
        lines.append(f"{i}. {reason}")
    lines.append("")
    if verdict == "FORGED":
        lines.append("**பரிந்துரை**: இந்த ஆவணம் தகுதிவாய்ந்த நிபுணரால் மேலும் ஆய்வு செய்யப்பட வேண்டும்.")
    else:
        lines.append("**பரிந்துரை**: இந்த ஆவணம் சரியானதாகத் தெரிகிறது. சாதாரண சரிபார்ப்பு நடைமுறைகள் பொருந்தும்.")
    return "\n".join(lines)


# ═══════════════════════════════════════════════
#  Fallback: Rule-based report
# ═══════════════════════════════════════════════
def _rule_based_report(**kwargs) -> dict:
    """Generate a structured report without Gemini API."""
    is_forged = kwargs["is_forged"]
    ela_score = kwargs["ela_score"]
    font_score = kwargs["font_score"]
    overall_score = kwargs["overall_score"]
    anomaly_score = kwargs.get("anomaly_score", 0)
    anomalies = kwargs.get("anomalies", [])
    fonts = kwargs.get("fonts", [])
    confidence_avg = kwargs.get("confidence_avg", 0)

    verdict = "FORGED" if is_forged else "AUTHENTIC"

    if overall_score >= 0.7:
        confidence_level = "High"
    elif overall_score >= 0.4:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"

    reasons = []
    suspicious_sections = []

    # ELA-based reasons
    if ela_score > 0.5:
        reasons.append(f"High ELA score ({ela_score:.2%}) indicates significant compression inconsistencies, suggesting the image has been edited or spliced.")
    elif ela_score > 0.2:
        reasons.append(f"Moderate ELA score ({ela_score:.2%}) shows some compression variations that may indicate minor edits.")
    else:
        reasons.append(f"Low ELA score ({ela_score:.2%}) shows uniform compression, consistent with an unedited document.")

    # Font-based reasons
    if font_score > 0.3:
        reasons.append(f"Font inconsistency score ({font_score:.2%}) is elevated. {len(fonts)} different fonts detected: {', '.join(fonts[:5])}.")
        suspicious_sections.append(f"Multiple fonts detected: {', '.join(fonts[:5])}")
    elif fonts:
        reasons.append(f"Font analysis normal. {len(fonts)} font(s) detected: {', '.join(fonts[:3])}.")

    # OCR anomaly reasons
    if anomaly_score > 0.3:
        reasons.append(f"Text anomaly score ({anomaly_score:.2%}) indicates suspicious text regions.")
        for a in anomalies[:3]:
            suspicious_sections.append(f"[{a.get('type', 'anomaly')}] {a.get('text', '')[:50]}: {a.get('details', '')}")
    elif anomalies:
        reasons.append(f"Minor text anomalies detected ({len(anomalies)} region(s) flagged).")

    # Confidence reason
    if confidence_avg < 0.5 and confidence_avg > 0:
        reasons.append(f"Low average OCR confidence ({confidence_avg:.2%}) suggests degraded or manipulated text.")

    # Overall
    reasons.append(f"Combined forgery score: {overall_score:.2%} (threshold: 30%).")

    # Recommendation
    if is_forged:
        recommendation = "This document exhibits signs of tampering. It should be escalated for manual forensic review. Do not accept as authentic without additional verification."
    else:
        recommendation = "This document does not show significant signs of forgery. Standard document handling procedures may be followed."

    # English report
    report_en_lines = [
        "# ForgeShield AI — Forensic Analysis Report",
        "",
        f"## Verdict: {verdict}",
        f"**Confidence Level**: {confidence_level}",
        "",
        "## Analysis Scores",
        f"- Error Level Analysis (ELA): {ela_score:.2%}",
        f"- Font Inconsistency: {font_score:.2%}",
        f"- Text Anomaly: {anomaly_score:.2%}",
        f"- **Overall Forgery Score: {overall_score:.2%}**",
        "",
        "## Reasons",
    ]
    for i, r in enumerate(reasons, 1):
        report_en_lines.append(f"{i}. {r}")

    if suspicious_sections:
        report_en_lines.append("")
        report_en_lines.append("## Suspicious Sections")
        for s in suspicious_sections:
            report_en_lines.append(f"- {s}")

    report_en_lines.extend(["", f"## Recommendation", recommendation])
    report_en = "\n".join(report_en_lines)

    # Tamil report
    verdict_ta = "போலியானது" if is_forged else "உண்மையானது"
    conf_ta = {"High": "உயர்", "Medium": "நடுத்தர", "Low": "குறைந்த"}.get(confidence_level, confidence_level)
    report_ta_lines = [
        "# ForgeShield AI — தடயவியல் பகுப்பாய்வு அறிக்கை",
        "",
        f"## தீர்ப்பு: {verdict_ta}",
        f"**நம்பிக்கை நிலை**: {conf_ta}",
        "",
        "## பகுப்பாய்வு மதிப்பெண்கள்",
        f"- பிழை நிலை பகுப்பாய்வு (ELA): {ela_score:.2%}",
        f"- எழுத்துரு முரண்பாடு: {font_score:.2%}",
        f"- உரை ஒழுங்கின்மை: {anomaly_score:.2%}",
        f"- **ஒட்டுமொத்த போலி மதிப்பெண்: {overall_score:.2%}**",
        "",
        "## காரணங்கள்",
    ]
    for i, r in enumerate(reasons, 1):
        report_ta_lines.append(f"{i}. {r}")

    if is_forged:
        report_ta_lines.extend([
            "",
            "## பரிந்துரை",
            "இந்த ஆவணம் சேதம் அடையாளங்களைக் காட்டுகிறது. கையேடு தடயவியல் மதிப்பாய்வுக்கு அனுப்ப வேண்டும்.",
        ])
    else:
        report_ta_lines.extend([
            "",
            "## பரிந்துரை",
            "இந்த ஆவணம் போலியின் குறிப்பிடத்தக்க அறிகுறிகளைக் காட்டவில்லை. சாதாரண ஆவண கையாளுதல் நடைமுறைகளை பின்பற்றலாம்.",
        ])
    report_ta = "\n".join(report_ta_lines)

    return {
        "verdict": verdict,
        "confidence_level": confidence_level,
        "reasons": reasons[:5],
        "suspicious_sections": suspicious_sections,
        "recommendation": recommendation,
        "report_en": report_en,
        "report_ta": report_ta,
    }
