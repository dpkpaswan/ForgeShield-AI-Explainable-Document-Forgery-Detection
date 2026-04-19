"""
detector.py — Multi-layer document forgery detection.

Provides:
  • run_ela(image_path)              → ELA heatmap (base64) + ela_score
  • generate_gradcam_heatmap(path)   → Grad-CAM heatmap (base64)
  • check_font_inconsistency(path)   → font_score + font_list  (PDF only)
  • analyze_document(file_path)      → combined result dict
"""

import os
import io
import cv2
import base64
import numpy as np
from PIL import Image

# ── PDF handling ──────────────────────────────
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# ── PyTorch ResNet50 (lazy-loaded) ────────────
_torch_model = None


def _get_resnet():
    """Lazy-load PyTorch ResNet50 so the import doesn't block startup."""
    global _torch_model
    if _torch_model is None:
        import torch
        from torchvision import models
        _torch_model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
        _torch_model.eval()
    return _torch_model


# ═══════════════════════════════════════════════
#  Helper: convert first page of PDF → image path
# ═══════════════════════════════════════════════
def _pdf_first_page_to_image(pdf_path: str) -> str:
    """Render first page of a PDF to a temp PNG file, return path."""
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed.")
    doc = fitz.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(dpi=200)
    out_path = pdf_path + "_page0.png"
    pix.save(out_path)
    doc.close()
    return out_path


def _is_pdf(path: str) -> bool:
    return path.lower().endswith(".pdf")


def _to_base64_png(img_bgr: np.ndarray) -> str:
    """Encode an OpenCV BGR image as base64 PNG."""
    _, buf = cv2.imencode(".png", img_bgr)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


# ═══════════════════════════════════════════════
#  1. Error Level Analysis
# ═══════════════════════════════════════════════
def run_ela(image_path: str, quality: int = 90) -> dict:
    """
    Resave the image as JPEG at *quality*, diff against original,
    amplify ×10, and apply a JET colourmap.

    Returns
    -------
    dict  with keys  ela_heatmap_b64 (str)  and  ela_score (float 0-1)
    """
    original = cv2.imread(image_path)
    if original is None:
        return {"ela_heatmap_b64": "", "ela_score": 0.0}

    # Re-compress in memory
    pil_img = Image.open(image_path).convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    recompressed = np.array(Image.open(buf))[:, :, ::-1]  # RGB → BGR

    # Match sizes (EXIF rotation may change dims)
    if recompressed.shape[:2] != original.shape[:2]:
        recompressed = cv2.resize(recompressed, (original.shape[1], original.shape[0]))

    # Difference, amplify ×10
    diff = cv2.absdiff(original, recompressed)
    diff_amplified = np.clip(diff.astype(np.float32) * 10, 0, 255).astype(np.uint8)

    gray = cv2.cvtColor(diff_amplified, cv2.COLOR_BGR2GRAY)
    heatmap = cv2.applyColorMap(gray, cv2.COLORMAP_JET)

    # Score: normalised mean intensity (0 – 1)
    ela_score = float(np.clip(gray.mean() / 255.0, 0, 1))

    return {
        "ela_heatmap_b64": _to_base64_png(heatmap),
        "ela_score": round(ela_score, 4),
    }


# ═══════════════════════════════════════════════
#  2. Grad-CAM with ResNet50 (PyTorch)
# ═══════════════════════════════════════════════
def generate_gradcam_heatmap(image_path: str) -> str:
    """
    Load PyTorch ResNet50, compute Grad-CAM on the predicted class,
    and return the heatmap blended on the original as base64 PNG.
    """
    try:
        import torch
        from torchvision import transforms

        model = _get_resnet()

        # Hook to capture layer4 activations & gradients
        activations = {}
        gradients = {}

        def fwd_hook(module, inp, out):
            activations["value"] = out.detach()

        def bwd_hook(module, grad_in, grad_out):
            gradients["value"] = grad_out[0].detach()

        handle_fwd = model.layer4.register_forward_hook(fwd_hook)
        handle_bwd = model.layer4.register_full_backward_hook(bwd_hook)

        # Load & preprocess
        img_pil = Image.open(image_path).convert("RGB")
        preprocess = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])
        img_tensor = preprocess(img_pil).unsqueeze(0)
        img_tensor.requires_grad_(True)

        # Forward + backward
        output = model(img_tensor)
        top_class = output.argmax(dim=1)
        score = output[0, top_class]
        model.zero_grad()
        score.backward()

        # Compute Grad-CAM
        grads = gradients["value"]          # [1, 2048, 7, 7]
        acts = activations["value"]         # [1, 2048, 7, 7]
        weights = grads.mean(dim=(2, 3), keepdim=True)
        cam = (weights * acts).sum(dim=1, keepdim=True)
        cam = torch.relu(cam)
        cam = cam.squeeze().numpy()

        # Normalize 0-1
        cam = cam - cam.min()
        cam = cam / (cam.max() + 1e-8)

        # Overlay on original image
        original = cv2.imread(image_path)
        h, w = original.shape[:2]
        cam_resized = cv2.resize(cam, (w, h))
        cam_uint8 = np.uint8(255 * cam_resized)
        heatmap_color = cv2.applyColorMap(cam_uint8, cv2.COLORMAP_JET)
        blended = cv2.addWeighted(original, 0.6, heatmap_color, 0.4, 0)

        # Cleanup hooks
        handle_fwd.remove()
        handle_bwd.remove()

        return _to_base64_png(blended)

    except Exception as e:
        print(f"[Grad-CAM] Error: {e}")
        return ""


# ═══════════════════════════════════════════════
#  3. Font Inconsistency (PDF only)
# ═══════════════════════════════════════════════
def check_font_inconsistency(file_path: str) -> dict:
    """
    Extract all font names from a PDF via PyMuPDF.
    More unique fonts → higher suspicion.

    Returns  font_score (0-1)  and  font_list [str]
    """
    if not _is_pdf(file_path):
        return {"font_score": 0.0, "font_list": []}

    if fitz is None:
        return {"font_score": 0.0, "font_list": [], "error": "PyMuPDF not installed"}

    try:
        doc = fitz.open(file_path)
        fonts_set = set()
        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            font_name = span.get("font", "")
                            if font_name:
                                fonts_set.add(font_name)
        doc.close()

        font_list = sorted(fonts_set)
        # Heuristic: ≤2 fonts is normal; each extra font adds 0.15
        unique_count = len(font_list)
        if unique_count <= 2:
            font_score = 0.0
        else:
            font_score = min(1.0, (unique_count - 2) * 0.15)

        return {
            "font_score": round(font_score, 4),
            "font_list": font_list,
        }

    except Exception as e:
        print(f"[Font check] Error: {e}")
        return {"font_score": 0.0, "font_list": [], "error": str(e)}


# ═══════════════════════════════════════════════
#  4. Full analysis pipeline
# ═══════════════════════════════════════════════
def analyze_document(file_path: str) -> dict:
    """
    Run ELA + Grad-CAM + font check and return aggregated result.

    overall_score = ela_score × 0.6 + font_score × 0.4
    is_forged = overall_score > 0.3
    """
    image_path = file_path
    temp_image = None

    # If PDF, render first page to image
    if _is_pdf(file_path):
        try:
            image_path = _pdf_first_page_to_image(file_path)
            temp_image = image_path
        except Exception as e:
            return {
                "ela_score": 0,
                "font_score": 0,
                "overall_score": 0,
                "is_forged": False,
                "ela_heatmap_b64": "",
                "gradcam_heatmap_b64": "",
                "fonts_detected": [],
                "error": f"PDF conversion failed: {e}",
            }

    # Run layers
    ela_result = run_ela(image_path)
    gradcam_b64 = generate_gradcam_heatmap(image_path)
    font_result = check_font_inconsistency(file_path)

    ela_score = ela_result["ela_score"]
    font_score = font_result["font_score"]
    overall_score = round(ela_score * 0.6 + font_score * 0.4, 4)
    is_forged = overall_score > 0.3

    # Cleanup temp image
    if temp_image and os.path.exists(temp_image):
        try:
            os.remove(temp_image)
        except OSError:
            pass

    return {
        "ela_score": ela_score,
        "font_score": font_score,
        "overall_score": overall_score,
        "is_forged": is_forged,
        "ela_heatmap_b64": ela_result["ela_heatmap_b64"],
        "gradcam_heatmap_b64": gradcam_b64,
        "fonts_detected": font_result["font_list"],
    }
