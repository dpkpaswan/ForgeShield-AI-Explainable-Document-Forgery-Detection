# ForgeGuard — AI Document Forgery Detection

> **ThinkRoot × Vortex Hackathon 2026**

AI-powered document forgery detection platform featuring multi-layered image forensics, OCR text extraction, and visual explainability.

---

## ✨ Features

| Layer | Technique | What it detects |
|-------|-----------|-----------------|
| **ELA** | Error Level Analysis | Compression inconsistencies from image editing |
| **Noise** | Laplacian noise profiling | Inconsistent noise patterns across quadrants |
| **Metadata** | EXIF / tag inspection | Editor software signatures, date mismatches |
| **Copy-Move** | ORB feature matching | Duplicated (copy-pasted) regions in the image |
| **OCR** | EasyOCR | Extracts all text content from the document |
| **Explainability** | Heatmap + annotations | Visual + textual explanation of findings |

## 🛠 Tech Stack

- **Backend:** Python · FastAPI · OpenCV · EasyOCR · Pillow
- **Frontend:** React 18 · Vite · Framer Motion · Lucide Icons
- **Design:** Glassmorphism dark theme · Micro-animations · Responsive

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** and **npm**

### 1. Backend

```bash
cd forgery-detection/backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Start the server
python main.py
```

The API will be available at `http://localhost:8000`.

### 2. Frontend

```bash
cd forgery-detection/frontend

# Install dependencies
npm install

# Start dev server (proxies /api to backend)
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## 📡 API

### `GET /api/health`

Returns service health status.

### `POST /api/analyze`

Upload an image for full forensic analysis.

**Request:** `multipart/form-data` with field `file` (JPEG/PNG/WebP, ≤ 10 MB)

**Response:**
```json
{
  "filename": "document.jpg",
  "detection": {
    "verdict": "FORGED | SUSPICIOUS | AUTHENTIC",
    "confidence": 87.5,
    "ela_score": 92,
    "noise_score": 78,
    "metadata_score": 85,
    "copymove_score": 40,
    "ela_details": { ... },
    "noise_details": { ... },
    "metadata_details": { ... },
    "copymove_details": { ... },
    "ela_heatmap_base64": "..."
  },
  "ocr": {
    "full_text": "...",
    "lines": [ { "text": "...", "confidence": 98.5, "bbox": [...] } ]
  },
  "explainability": {
    "overlay_b64": "...",
    "annotated_b64": "...",
    "region_explanations": [ "..." ]
  }
}
```

---

## 📁 Project Structure

```
forgery-detection/
├── backend/
│   ├── core/
│   │   ├── __init__.py        # Package init
│   │   ├── detector.py        # 4-layer detection engine
│   │   ├── ocr.py             # EasyOCR wrapper
│   │   └── explainer.py       # Visual explainability
│   ├── main.py                # FastAPI server
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Main React component
│   │   ├── main.jsx           # Entry point
│   │   └── index.css          # Design system
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── README.md
```

---

## 👥 Team

Built with ❤️ for the ThinkRoot × Vortex Hackathon 2026.

## 📄 License

MIT
