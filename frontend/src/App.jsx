import React, { useState, useRef, useCallback, useEffect } from 'react';

const API = "https://forgeshield-ai-817820730147.us-central1.run.app";

/* ─── helpers ──────────────────────────────── */
function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

/* ─── Animated counter ─────────────────────── */
function AnimatedNumber({ value, suffix = '%', duration = 1200 }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let startTime = null;
    const end = value;
    function tick(now) {
      if (!startTime) startTime = now;
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(eased * end * 10) / 10);
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }, [value, duration]);
  return <>{display.toFixed(1)}{suffix}</>;
}

/* ─── ScoreBar ─────────────────────────────── */
function ScoreBar({ label, value, max = 1, color = '#00d4aa' }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div style={styles.scoreBarWrap}>
      <div style={styles.scoreBarHeader}>
        <span style={styles.scoreBarLabel}>{label}</span>
        <span style={{ ...styles.scoreBarValue, color }}>{(value * 100).toFixed(1)}%</span>
      </div>
      <div style={styles.scoreBarTrack}>
        <div style={{
          ...styles.scoreBarFill,
          width: `${pct}%`,
          background: `linear-gradient(90deg, ${color}, ${color}88)`,
        }} />
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════
   Main App
   ═══════════════════════════════════════════════ */
export default function App() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [reportLang, setReportLang] = useState('en');
  const inputRef = useRef(null);

  /* ── File handling ─────────────────────── */
  const handleFile = useCallback((f) => {
    if (!f) return;
    const ext = f.name.split('.').pop().toLowerCase();
    const allowed = ['jpg', 'jpeg', 'png', 'pdf'];
    if (!allowed.includes(ext)) {
      setError('Unsupported file type. Please upload JPG, PNG, or PDF.');
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setError('File too large. Maximum size is 10 MB.');
      return;
    }
    setFile(f);
    if (f.type.startsWith('image/')) {
      setPreview(URL.createObjectURL(f));
    } else {
      setPreview(null); // PDF — no preview
    }
    setResult(null);
    setError(null);
  }, []);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  }, [handleFile]);

  const onDragOver = useCallback((e) => { e.preventDefault(); setDragging(true); }, []);
  const onDragLeave = useCallback(() => setDragging(false), []);

  /* ── Upload & Analyse ──────────────────── */
  const analyze = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setLoadingStep(0);
    setReportLang('en');

    const stepTimer = setInterval(() => {
      setLoadingStep((s) => Math.min(s + 1, 3));
    }, 3000);

    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API}/api/analyze`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message || 'Analysis failed. Please try again.');
    } finally {
      clearInterval(stepTimer);
      setLoading(false);
    }
  };

  const reset = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    setReportLang('en');
  };

  /* ── Derived ───────────────────────────── */
  const isForged = result?.is_forged;
  const verdictColor = isForged ? '#ff4757' : '#00d4aa';
  const verdictText = isForged ? 'FORGED' : 'AUTHENTIC';

  const loadingSteps = [
    { icon: '🔬', text: 'Error Level Analysis' },
    { icon: '🧠', text: 'Grad-CAM Neural Inspection' },
    { icon: '📝', text: 'OCR & Anomaly Detection' },
    { icon: '🤖', text: 'AI Forensic Report Generation' },
  ];

  /* ═══════════════════════════════════════════
     RENDER
     ═══════════════════════════════════════════ */
  return (
    <div style={styles.app}>
      {/* Animated background grid */}
      <div style={styles.bgGrid} />

      <div style={styles.content}>
        {/* ── Header ──────────────────────── */}
        <header style={styles.header}>
          <div style={styles.logoWrap}>
            <div style={styles.logoIcon}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00d4aa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </div>
            <div>
              <h1 style={styles.logoTitle}>ForgeShield AI</h1>
              <p style={styles.logoSub}>Explainable Document Forensics</p>
            </div>
          </div>
          <div style={styles.headerBadge}>
            <span style={styles.statusDot} />
            System Online
          </div>
        </header>

        {/* ── Upload Zone ─────────────────── */}
        {!loading && !result && (
          <section style={styles.uploadSection}>
            <div
              style={{
                ...styles.uploadZone,
                ...(dragging ? styles.uploadZoneDrag : {}),
              }}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onClick={() => !file && inputRef.current?.click()}
              id="upload-zone"
            >
              <input
                ref={inputRef}
                style={styles.hiddenInput}
                type="file"
                accept=".jpg,.jpeg,.png,.pdf"
                onChange={(e) => handleFile(e.target.files[0])}
                id="file-input"
              />

              {!file ? (
                <>
                  <div style={styles.uploadIconWrap}>
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#00d4aa" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                      <polyline points="17 8 12 3 7 8"/>
                      <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                  </div>
                  <h2 style={styles.uploadTitle}>Drop your document here</h2>
                  <p style={styles.uploadSub}>or click to browse — we'll analyse it for signs of forgery</p>
                  <div style={styles.formatRow}>
                    {['JPG', 'PNG', 'PDF', 'Max 10 MB'].map(t => (
                      <span key={t} style={styles.formatTag}>{t}</span>
                    ))}
                  </div>
                </>
              ) : (
                <div style={styles.previewContainer} onClick={(e) => e.stopPropagation()}>
                  {preview ? (
                    <img src={preview} alt="Preview" style={styles.previewImg} />
                  ) : (
                    <div style={styles.pdfPreview}>
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#00d4aa" strokeWidth="1.5">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                        <polyline points="10 9 9 9 8 9"/>
                      </svg>
                      <span style={{ color: '#8892b0', marginTop: 8, fontSize: 13 }}>PDF Document</span>
                    </div>
                  )}
                  <div style={styles.previewInfo}>
                    <h3 style={styles.previewName}>{file.name}</h3>
                    <p style={styles.previewMeta}>{formatBytes(file.size)} · {file.name.split('.').pop().toUpperCase()}</p>
                    <div style={styles.previewActions}>
                      <button style={styles.btnPrimary} onClick={analyze} id="analyze-btn">
                        🔍 Analyse Document
                      </button>
                      <button style={styles.btnGhost} onClick={reset} id="reset-btn">
                        Change File
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {/* ── Loading ─────────────────────── */}
        {loading && (
          <section style={styles.loadingSection}>
            <div style={styles.spinner} />
            <h2 style={styles.loadingTitle}>Analysing Document…</h2>
            <p style={styles.loadingSub}>Running multi-layer forensic pipeline</p>
            <div style={styles.stepsWrap}>
              {loadingSteps.map((step, i) => (
                <div key={i} style={{
                  ...styles.stepRow,
                  opacity: i <= loadingStep ? 1 : 0.3,
                  color: i <= loadingStep ? '#00d4aa' : '#4a5568',
                }}>
                  <span style={styles.stepIcon}>{step.icon}</span>
                  <span>{step.text}</span>
                  {i < loadingStep && <span style={styles.stepCheck}>✓</span>}
                  {i === loadingStep && <span style={styles.stepPulse} />}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ── Error ───────────────────────── */}
        {error && (
          <div style={styles.errorCard}>
            <span style={{ fontSize: 36 }}>⚠️</span>
            <h3 style={styles.errorTitle}>Analysis Error</h3>
            <p style={styles.errorText}>{error}</p>
            <button style={styles.btnGhost} onClick={reset}>Try Again</button>
          </div>
        )}

        {/* ── Results ─────────────────────── */}
        {result && (
          <section style={styles.resultsSection}>
            {/* Verdict Badge */}
            <div style={{
              ...styles.verdictCard,
              borderColor: verdictColor + '40',
              boxShadow: `0 0 40px ${verdictColor}15`,
            }}>
              <div style={{
                ...styles.verdictBadge,
                background: verdictColor + '18',
                color: verdictColor,
                border: `2px solid ${verdictColor}60`,
              }}>
                <span style={{ fontSize: 28 }}>{isForged ? '🚨' : '✅'}</span>
                <span style={styles.verdictText}>{verdictText}</span>
              </div>
              <div style={{ ...styles.verdictScore, color: verdictColor }}>
                <AnimatedNumber value={result.overall_score * 100} />
              </div>
              <div style={styles.verdictLabel}>Overall Forgery Score</div>
            </div>

            {/* Score Stats */}
            <div style={styles.statsGrid}>
              <div style={styles.statCard}>
                <ScoreBar label="ELA Score" value={result.ela_score} color="#3b82f6" />
              </div>
              <div style={styles.statCard}>
                <ScoreBar label="Font Score" value={result.font_score} color="#a855f7" />
              </div>
              <div style={styles.statCard}>
                <ScoreBar label="OCR Confidence" value={result.ocr?.confidence_avg || 0} color="#f59e0b" />
              </div>
              <div style={styles.statCard}>
                <ScoreBar label="Anomaly Score" value={result.anomaly_score || 0} color="#ef4444" />
              </div>
            </div>

            {/* Heatmaps */}
            <div style={styles.sectionHeader}>
              <span style={{ fontSize: 20 }}>🔬</span>
              <h2 style={styles.sectionTitle}>Forensic Heatmaps</h2>
            </div>
            <div style={styles.heatmapGrid}>
              <div style={styles.heatmapCard}>
                <div style={styles.heatmapCardHeader}>
                  <span style={{ ...styles.labelDot, background: '#3b82f6' }} />
                  <h4 style={styles.heatmapCardTitle}>ELA Heatmap</h4>
                </div>
                <div style={styles.heatmapBody}>
                  {result.ela_heatmap_b64 ? (
                    <img
                      src={`data:image/png;base64,${result.ela_heatmap_b64}`}
                      alt="ELA Heatmap"
                      style={styles.heatmapImg}
                    />
                  ) : (
                    <div style={styles.emptyState}>No ELA heatmap generated</div>
                  )}
                </div>
              </div>
              <div style={styles.heatmapCard}>
                <div style={styles.heatmapCardHeader}>
                  <span style={{ ...styles.labelDot, background: '#a855f7' }} />
                  <h4 style={styles.heatmapCardTitle}>Grad-CAM Heatmap</h4>
                </div>
                <div style={styles.heatmapBody}>
                  {result.gradcam_heatmap_b64 ? (
                    <img
                      src={`data:image/png;base64,${result.gradcam_heatmap_b64}`}
                      alt="Grad-CAM Heatmap"
                      style={styles.heatmapImg}
                    />
                  ) : (
                    <div style={styles.emptyState}>No Grad-CAM heatmap generated</div>
                  )}
                </div>
              </div>
            </div>

            {/* Anomalies */}
            {result.anomalies && result.anomalies.length > 0 && (
              <>
                <div style={styles.sectionHeader}>
                  <span style={{ fontSize: 20 }}>🚩</span>
                  <h2 style={styles.sectionTitle}>Detected Anomalies</h2>
                </div>
                <div style={styles.anomaliesWrap}>
                  {result.anomalies.map((a, i) => (
                    <div key={i} style={styles.anomalyItem}>
                      <span style={styles.anomalyTag}>{a.type}</span>
                      <span style={styles.anomalyText}>"{a.text}"</span>
                      <span style={styles.anomalyDetail}>{a.details}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* Fonts detected */}
            {result.fonts_detected && result.fonts_detected.length > 0 && (
              <>
                <div style={styles.sectionHeader}>
                  <span style={{ fontSize: 20 }}>🔤</span>
                  <h2 style={styles.sectionTitle}>Fonts Detected</h2>
                </div>
                <div style={styles.fontsWrap}>
                  {result.fonts_detected.map((f, i) => (
                    <span key={i} style={styles.fontTag}>{f}</span>
                  ))}
                </div>
              </>
            )}

            {/* OCR Text */}
            {result.ocr?.text && (
              <>
                <div style={styles.sectionHeader}>
                  <span style={{ fontSize: 20 }}>📝</span>
                  <h2 style={styles.sectionTitle}>Extracted Text (OCR)</h2>
                </div>
                <div style={styles.ocrPanel}>
                  <div style={styles.ocrMeta}>
                    <span style={styles.ocrMetaTag}>Language: {result.ocr.language_detected}</span>
                    <span style={styles.ocrMetaTag}>Words: {result.ocr.word_count}</span>
                    <span style={styles.ocrMetaTag}>Confidence: {(result.ocr.confidence_avg * 100).toFixed(1)}%</span>
                  </div>
                  <div style={styles.ocrText}>{result.ocr.text}</div>
                </div>
              </>
            )}

            {/* AI Forensic Report */}
            {result.report && (
              <>
                <div style={styles.sectionHeader}>
                  <span style={{ fontSize: 20 }}>🤖</span>
                  <h2 style={styles.sectionTitle}>AI Forensic Report</h2>
                </div>
                <div style={styles.reportCard}>
                  {/* Report header with verdict */}
                  <div style={styles.reportHeader}>
                    <div>
                      <span style={{
                        ...styles.reportVerdict,
                        color: verdictColor,
                      }}>
                        {result.report.verdict}
                      </span>
                      <span style={styles.reportConfidence}>
                        Confidence: {result.report.confidence_level}
                      </span>
                    </div>
                    {/* Language toggle */}
                    <div style={styles.langToggle}>
                      <button
                        style={{
                          ...styles.langBtn,
                          ...(reportLang === 'en' ? styles.langBtnActive : {}),
                        }}
                        onClick={() => setReportLang('en')}
                        id="lang-en-btn"
                      >
                        English
                      </button>
                      <button
                        style={{
                          ...styles.langBtn,
                          ...(reportLang === 'ta' ? styles.langBtnActive : {}),
                        }}
                        onClick={() => setReportLang('ta')}
                        id="lang-ta-btn"
                      >
                        தமிழ்
                      </button>
                    </div>
                  </div>

                  {/* Reasons */}
                  {result.report.reasons && result.report.reasons.length > 0 && (
                    <div style={styles.reportSection}>
                      <h4 style={styles.reportSectionTitle}>Key Findings</h4>
                      {result.report.reasons.map((r, i) => (
                        <div key={i} style={styles.reasonItem}>
                          <span style={styles.reasonNum}>{i + 1}</span>
                          <span style={styles.reasonText}>{r}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Suspicious Sections */}
                  {result.report.suspicious_sections && result.report.suspicious_sections.length > 0 && (
                    <div style={styles.reportSection}>
                      <h4 style={styles.reportSectionTitle}>Suspicious Sections</h4>
                      {result.report.suspicious_sections.map((s, i) => (
                        <div key={i} style={styles.suspiciousItem}>🔴 {s}</div>
                      ))}
                    </div>
                  )}

                  {/* Full report text */}
                  <div style={styles.reportBody}>
                    <pre style={styles.reportText}>
                      {reportLang === 'en' ? result.report.report_en : result.report.report_ta}
                    </pre>
                  </div>

                  {/* Recommendation */}
                  {result.report.recommendation && (
                    <div style={styles.recommendationBox}>
                      <span style={{ fontSize: 18 }}>💡</span>
                      <span style={styles.recommendationText}>{result.report.recommendation}</span>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Pipeline Logs */}
            {result.pipeline_logs && result.pipeline_logs.length > 0 && (
              <>
                <div style={styles.sectionHeader}>
                  <span style={{ fontSize: 20 }}>📋</span>
                  <h2 style={styles.sectionTitle}>Pipeline Log</h2>
                </div>
                <div style={styles.logPanel}>
                  {result.pipeline_logs.map((entry, i) => {
                    const stageColors = {
                      UPLOAD: '#8b5cf6', ELA: '#3b82f6', 'GRAD-CAM': '#a855f7',
                      FONTS: '#ec4899', SCORE: '#f59e0b', OCR: '#06b6d4',
                      ANOMALY: '#ef4444', AI: '#10b981', DONE: '#00d4aa',
                    };
                    const color = stageColors[entry.stage] || '#8892b0';
                    return (
                      <div key={i} style={styles.logEntry}>
                        <span style={styles.logTime}>{String(entry.ms).padStart(5, ' ')}ms</span>
                        <span style={{
                          ...styles.logBadge,
                          background: color + '20',
                          color: color,
                          border: `1px solid ${color}40`,
                        }}>{entry.stage}</span>
                        <span style={styles.logMsg}>{entry.message}</span>
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {/* Processing time */}
            <div style={styles.processingTime}>
              ⏱ Processed in {result.processing_time_ms?.toLocaleString() || '—'} ms
            </div>

            {/* New Analysis */}
            <div style={{ textAlign: 'center', marginBottom: 48 }}>
              <button style={styles.btnPrimary} onClick={reset} id="new-analysis-btn">
                🔍 New Analysis
              </button>
            </div>
          </section>
        )}

        {/* ── Footer ──────────────────────── */}
        <footer style={styles.footer}>
          <p style={styles.footerText}>
            ForgeShield AI — Explainable Document Forgery Detection ·
            Built for <span style={{ color: '#00d4aa' }}>ThinkRoot × Vortex Hackathon 2026</span>
          </p>
        </footer>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════
   STYLES (all inline)
   ═══════════════════════════════════════════════ */
const styles = {
  app: {
    minHeight: '100vh',
    background: '#0a0a0f',
    color: '#e2e8f0',
    fontFamily: '"JetBrains Mono", "Fira Code", "SF Mono", "Cascadia Code", monospace',
    position: 'relative',
    overflow: 'hidden',
  },
  bgGrid: {
    position: 'fixed',
    inset: 0,
    backgroundImage: `
      linear-gradient(rgba(0, 212, 170, 0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0, 212, 170, 0.03) 1px, transparent 1px)
    `,
    backgroundSize: '40px 40px',
    pointerEvents: 'none',
    zIndex: 0,
  },
  content: {
    position: 'relative',
    zIndex: 1,
    maxWidth: 900,
    margin: '0 auto',
    padding: '0 20px',
  },

  /* ── Header ──────────────── */
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '24px 0',
    borderBottom: '1px solid #1a1a2e',
  },
  logoWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  logoIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    background: 'linear-gradient(135deg, #00d4aa15, #00d4aa08)',
    border: '1px solid #00d4aa30',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoTitle: {
    fontSize: 20,
    fontWeight: 700,
    color: '#f0f4f8',
    margin: 0,
    letterSpacing: '-0.5px',
  },
  logoSub: {
    fontSize: 11,
    color: '#00d4aa',
    margin: 0,
    textTransform: 'uppercase',
    letterSpacing: '1.5px',
  },
  headerBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 12,
    color: '#00d4aa',
    background: '#00d4aa10',
    padding: '6px 14px',
    borderRadius: 20,
    border: '1px solid #00d4aa25',
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: '50%',
    background: '#00d4aa',
    boxShadow: '0 0 8px #00d4aa80',
    display: 'inline-block',
  },

  /* ── Upload ──────────────── */
  uploadSection: {
    padding: '60px 0',
  },
  uploadZone: {
    border: '2px dashed #1e293b',
    borderRadius: 16,
    padding: '48px 32px',
    textAlign: 'center',
    cursor: 'pointer',
    transition: 'all 0.3s ease',
    background: '#0d0d15',
  },
  uploadZoneDrag: {
    borderColor: '#00d4aa',
    background: '#00d4aa08',
    boxShadow: '0 0 30px #00d4aa10',
  },
  hiddenInput: {
    display: 'none',
  },
  uploadIconWrap: {
    width: 72,
    height: 72,
    borderRadius: '50%',
    background: '#00d4aa10',
    border: '2px solid #00d4aa25',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    margin: '0 auto 20px',
  },
  uploadTitle: {
    fontSize: 22,
    fontWeight: 600,
    color: '#f0f4f8',
    margin: '0 0 8px',
  },
  uploadSub: {
    fontSize: 14,
    color: '#8892b0',
    margin: '0 0 20px',
  },
  formatRow: {
    display: 'flex',
    gap: 8,
    justifyContent: 'center',
    flexWrap: 'wrap',
  },
  formatTag: {
    fontSize: 11,
    color: '#8892b0',
    background: '#1a1a2e',
    padding: '4px 10px',
    borderRadius: 6,
    border: '1px solid #2a2a3e',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  previewContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: 24,
    textAlign: 'left',
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  previewImg: {
    maxWidth: 200,
    maxHeight: 200,
    borderRadius: 12,
    border: '1px solid #1e293b',
    objectFit: 'contain',
  },
  pdfPreview: {
    width: 160,
    height: 160,
    borderRadius: 12,
    border: '1px solid #1e293b',
    background: '#0d0d15',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
  },
  previewInfo: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  previewName: {
    fontSize: 16,
    fontWeight: 600,
    color: '#f0f4f8',
    margin: 0,
    wordBreak: 'break-all',
  },
  previewMeta: {
    fontSize: 13,
    color: '#8892b0',
    margin: 0,
  },
  previewActions: {
    display: 'flex',
    gap: 10,
    marginTop: 8,
    flexWrap: 'wrap',
  },

  /* ── Buttons ─────────────── */
  btnPrimary: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '12px 24px',
    fontSize: 14,
    fontWeight: 600,
    fontFamily: 'inherit',
    color: '#0a0a0f',
    background: 'linear-gradient(135deg, #00d4aa, #00b894)',
    border: 'none',
    borderRadius: 10,
    cursor: 'pointer',
    transition: 'all 0.2s',
    letterSpacing: '0.3px',
  },
  btnGhost: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '12px 24px',
    fontSize: 14,
    fontWeight: 500,
    fontFamily: 'inherit',
    color: '#8892b0',
    background: 'transparent',
    border: '1px solid #2a2a3e',
    borderRadius: 10,
    cursor: 'pointer',
    transition: 'all 0.2s',
  },

  /* ── Loading ─────────────── */
  loadingSection: {
    textAlign: 'center',
    padding: '80px 20px',
  },
  spinner: {
    width: 56,
    height: 56,
    border: '3px solid #1a1a2e',
    borderTop: '3px solid #00d4aa',
    borderRadius: '50%',
    margin: '0 auto 24px',
    animation: 'spin 1s linear infinite',
  },
  loadingTitle: {
    fontSize: 22,
    fontWeight: 600,
    color: '#f0f4f8',
    margin: '0 0 8px',
  },
  loadingSub: {
    fontSize: 14,
    color: '#8892b0',
    margin: '0 0 32px',
  },
  stepsWrap: {
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
    maxWidth: 320,
    margin: '0 auto',
    textAlign: 'left',
  },
  stepRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    fontSize: 13,
    transition: 'all 0.4s',
  },
  stepIcon: {
    fontSize: 18,
    width: 24,
    textAlign: 'center',
  },
  stepCheck: {
    marginLeft: 'auto',
    color: '#00d4aa',
    fontWeight: 700,
  },
  stepPulse: {
    marginLeft: 'auto',
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: '#00d4aa',
    boxShadow: '0 0 8px #00d4aa80',
    animation: 'pulse 1.5s ease-in-out infinite',
  },

  /* ── Error ───────────────── */
  errorCard: {
    textAlign: 'center',
    padding: '48px 24px',
    background: '#1a0a0a',
    border: '1px solid #ff475730',
    borderRadius: 16,
    margin: '40px 0',
  },
  errorTitle: {
    fontSize: 18,
    fontWeight: 600,
    color: '#ff4757',
    margin: '12px 0 8px',
  },
  errorText: {
    fontSize: 14,
    color: '#e2886a',
    margin: '0 0 20px',
  },

  /* ── Results ─────────────── */
  resultsSection: {
    padding: '40px 0',
  },

  /* Verdict */
  verdictCard: {
    textAlign: 'center',
    padding: '40px 24px',
    background: '#0d0d15',
    border: '1px solid',
    borderRadius: 20,
    marginBottom: 32,
  },
  verdictBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 12,
    padding: '14px 32px',
    borderRadius: 50,
    fontSize: 16,
    fontWeight: 700,
    letterSpacing: '3px',
    marginBottom: 16,
  },
  verdictText: {
    fontSize: 20,
    fontWeight: 800,
    letterSpacing: '4px',
  },
  verdictScore: {
    fontSize: 48,
    fontWeight: 800,
    lineHeight: 1.1,
  },
  verdictLabel: {
    fontSize: 13,
    color: '#8892b0',
    marginTop: 4,
    textTransform: 'uppercase',
    letterSpacing: '1.5px',
  },

  /* Stats */
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: 16,
    marginBottom: 40,
  },
  statCard: {
    background: '#0d0d15',
    border: '1px solid #1a1a2e',
    borderRadius: 14,
    padding: '20px',
  },

  /* Score bars */
  scoreBarWrap: {},
  scoreBarHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  scoreBarLabel: {
    fontSize: 12,
    color: '#8892b0',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  scoreBarValue: {
    fontSize: 14,
    fontWeight: 700,
  },
  scoreBarTrack: {
    height: 6,
    borderRadius: 3,
    background: '#1a1a2e',
    overflow: 'hidden',
  },
  scoreBarFill: {
    height: '100%',
    borderRadius: 3,
    transition: 'width 1s ease',
  },

  /* Sections */
  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 16,
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 600,
    color: '#f0f4f8',
    margin: 0,
  },

  /* Heatmaps */
  heatmapGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: 16,
    marginBottom: 40,
  },
  heatmapCard: {
    background: '#0d0d15',
    border: '1px solid #1a1a2e',
    borderRadius: 14,
    overflow: 'hidden',
  },
  heatmapCardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '14px 18px',
    borderBottom: '1px solid #1a1a2e',
  },
  labelDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    display: 'inline-block',
  },
  heatmapCardTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: '#c9d1d9',
    margin: 0,
  },
  heatmapBody: {
    padding: 12,
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: 200,
  },
  heatmapImg: {
    width: '100%',
    borderRadius: 8,
    objectFit: 'contain',
    maxHeight: 400,
  },
  emptyState: {
    color: '#4a5568',
    fontSize: 13,
    padding: '40px 0',
  },

  /* Anomalies */
  anomaliesWrap: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    marginBottom: 40,
  },
  anomalyItem: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    padding: '14px 18px',
    background: '#1a0a0a',
    border: '1px solid #ff475720',
    borderRadius: 10,
    flexWrap: 'wrap',
  },
  anomalyTag: {
    fontSize: 10,
    fontWeight: 700,
    color: '#ff4757',
    background: '#ff475718',
    padding: '3px 8px',
    borderRadius: 4,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    whiteSpace: 'nowrap',
  },
  anomalyText: {
    fontSize: 13,
    color: '#e2e8f0',
    fontWeight: 600,
  },
  anomalyDetail: {
    fontSize: 12,
    color: '#8892b0',
    width: '100%',
    marginTop: 4,
  },

  /* Fonts */
  fontsWrap: {
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
    marginBottom: 40,
  },
  fontTag: {
    fontSize: 12,
    color: '#a855f7',
    background: '#a855f710',
    padding: '6px 12px',
    borderRadius: 6,
    border: '1px solid #a855f725',
  },

  /* OCR */
  ocrPanel: {
    background: '#0d0d15',
    border: '1px solid #1a1a2e',
    borderRadius: 14,
    padding: '18px',
    marginBottom: 40,
  },
  ocrMeta: {
    display: 'flex',
    gap: 10,
    marginBottom: 14,
    flexWrap: 'wrap',
  },
  ocrMetaTag: {
    fontSize: 11,
    color: '#8892b0',
    background: '#1a1a2e',
    padding: '4px 10px',
    borderRadius: 6,
  },
  ocrText: {
    fontSize: 13,
    lineHeight: 1.7,
    color: '#c9d1d9',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    maxHeight: 240,
    overflowY: 'auto',
    padding: '12px',
    background: '#0a0a12',
    borderRadius: 8,
    border: '1px solid #1a1a2e',
  },

  /* Report */
  reportCard: {
    background: '#0d0d15',
    border: '1px solid #1a1a2e',
    borderRadius: 16,
    overflow: 'hidden',
    marginBottom: 40,
  },
  reportHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '18px 20px',
    borderBottom: '1px solid #1a1a2e',
    flexWrap: 'wrap',
    gap: 12,
  },
  reportVerdict: {
    fontSize: 16,
    fontWeight: 800,
    letterSpacing: '2px',
    marginRight: 14,
  },
  reportConfidence: {
    fontSize: 12,
    color: '#8892b0',
  },
  langToggle: {
    display: 'flex',
    gap: 0,
    borderRadius: 8,
    overflow: 'hidden',
    border: '1px solid #2a2a3e',
  },
  langBtn: {
    padding: '8px 18px',
    fontSize: 12,
    fontWeight: 600,
    fontFamily: 'inherit',
    color: '#8892b0',
    background: '#0a0a0f',
    border: 'none',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  langBtnActive: {
    color: '#0a0a0f',
    background: '#00d4aa',
  },
  reportSection: {
    padding: '16px 20px',
    borderBottom: '1px solid #1a1a2e',
  },
  reportSectionTitle: {
    fontSize: 13,
    fontWeight: 700,
    color: '#00d4aa',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    margin: '0 0 12px',
  },
  reasonItem: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    marginBottom: 10,
  },
  reasonNum: {
    width: 22,
    height: 22,
    borderRadius: '50%',
    background: '#00d4aa15',
    color: '#00d4aa',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 11,
    fontWeight: 700,
    flexShrink: 0,
  },
  reasonText: {
    fontSize: 13,
    color: '#c9d1d9',
    lineHeight: 1.5,
  },
  suspiciousItem: {
    fontSize: 13,
    color: '#ff8787',
    marginBottom: 8,
    paddingLeft: 4,
  },
  reportBody: {
    padding: '16px 20px',
    borderBottom: '1px solid #1a1a2e',
  },
  reportText: {
    fontSize: 12.5,
    lineHeight: 1.8,
    color: '#a0aec0',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    margin: 0,
    fontFamily: 'inherit',
    maxHeight: 400,
    overflowY: 'auto',
  },
  recommendationBox: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    padding: '16px 20px',
    background: '#00d4aa08',
    borderTop: '1px solid #00d4aa15',
  },
  recommendationText: {
    fontSize: 13,
    color: '#00d4aa',
    lineHeight: 1.6,
  },

  /* Pipeline Log */
  logPanel: {
    background: '#0d0d15',
    border: '1px solid #1a1a2e',
    borderRadius: 12,
    padding: '12px 16px',
    marginBottom: 32,
    fontFamily: '"JetBrains Mono", monospace',
    fontSize: 12,
    maxHeight: 320,
    overflowY: 'auto',
  },
  logEntry: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '5px 0',
    borderBottom: '1px solid #1a1a2e08',
  },
  logTime: {
    color: '#4a5568',
    fontSize: 11,
    fontVariantNumeric: 'tabular-nums',
    minWidth: 60,
    textAlign: 'right',
    whiteSpace: 'pre',
  },
  logBadge: {
    fontSize: 10,
    fontWeight: 700,
    padding: '2px 8px',
    borderRadius: 4,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    minWidth: 70,
    textAlign: 'center',
    flexShrink: 0,
  },
  logMsg: {
    color: '#8892b0',
    fontSize: 12,
    lineHeight: 1.5,
  },

  /* Processing time */
  processingTime: {
    textAlign: 'center',
    fontSize: 12,
    color: '#4a5568',
    marginBottom: 24,
  },

  /* Footer */
  footer: {
    textAlign: 'center',
    padding: '24px 0 40px',
    borderTop: '1px solid #1a1a2e',
  },
  footerText: {
    fontSize: 12,
    color: '#4a5568',
    margin: 0,
  },
};

/* Inject keyframes for spinner and pulse */
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(1.3); }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { margin: 0; }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #0a0a0f; }
  ::-webkit-scrollbar-thumb { background: #1a1a2e; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #2a2a3e; }
  button:hover { filter: brightness(1.1); }
`;
document.head.appendChild(styleSheet);
