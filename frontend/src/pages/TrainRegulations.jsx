import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function TrainRegulations() {
  const { isRole } = useAuth();
  const canEdit = isRole("compliance", "legal", "admin");
  const [stats, setStats] = useState({});
  const [presets, setPresets] = useState([]);
  const [regulations, setRegulations] = useState({});
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);

  const [upFile, setUpFile] = useState(null);
  const [upSource, setUpSource] = useState("");
  const [upReg, setUpReg] = useState("general");

  const [urlInput, setUrlInput] = useState("");
  const [urlSource, setUrlSource] = useState("");
  const [urlReg, setUrlReg] = useState("general");

  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);

  function refresh() {
    api.get("/kb/stats").then(setStats);
  }

  useEffect(() => {
    refresh();
    api.get("/kb/presets").then((d) => setPresets(d.presets));
    api.get("/regulations").then((d) => setRegulations(d.regulations));
  }, []);

  async function loadPreset(name) {
    setBusy(true); setError(""); setSuccess("");
    try {
      const res = await api.post("/kb/load-preset", { name });
      setSuccess(`✅ ${res.chunks_added} chunks added from ${name}`);
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function uploadFile(e) {
    e.preventDefault();
    if (!upFile || !upSource.trim()) return;
    setBusy(true); setError(""); setSuccess("");
    try {
      const form = new FormData();
      form.append("file", upFile);
      form.append("source", upSource);
      form.append("regulation", upReg);
      const res = await api.postForm("/kb/ingest", form);
      setSuccess(`✅ ${res.chunks_added} chunks added`);
      setUpFile(null); setUpSource("");
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function scrapeUrl(e) {
    e.preventDefault();
    if (!urlInput.trim() || !urlSource.trim()) return;
    setBusy(true); setError(""); setSuccess("");
    try {
      const res = await api.post("/kb/ingest-url", { url: urlInput, source: urlSource, regulation: urlReg });
      setSuccess(`✅ ${res.chunks_added} chunks added`);
      setUrlInput(""); setUrlSource("");
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function retrieve() {
    if (!query.trim()) return;
    const d = await api.get(`/kb/retrieve?q=${encodeURIComponent(query)}&top_k=5`);
    setResults(d.results);
  }

  return (
    <div>
      <h2>📚 Train — Regulatory Knowledge Base</h2>
      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}
      <div className="stat-grid">
        <div className="stat-card"><div className="stat-num">{stats.total_chunks || 0}</div><div className="stat-lbl">Total Chunks</div></div>
        <div className="stat-card"><div className="stat-num">{stats.regulations || 0}</div><div className="stat-lbl">Regulations</div></div>
        <div className="stat-card"><div className="stat-num">{stats.policies || 0}</div><div className="stat-lbl">Policies</div></div>
        <div className="stat-card"><div className="stat-num">{stats.agreements || 0}</div><div className="stat-lbl">Agreements</div></div>
      </div>
      <hr className="divider" />
      {canEdit && (
        <>
          <h3>⚡ One-Click Load — Official Regulations</h3>
          <div className="checkbox-grid">
            {presets.map((p) => (
              <button key={p.name} onClick={() => loadPreset(p.name)} disabled={busy}>📥 {p.name}</button>
            ))}
          </div>
          <hr className="divider" />
          <h3>Upload or Scrape</h3>
          <div className="row">
            <form onSubmit={uploadFile}>
              <div className="field">
                <label>File</label>
                <input type="file" accept=".txt,.pdf,.docx" onChange={(e) => setUpFile(e.target.files[0])} />
              </div>
              <div className="field">
                <label>Source name</label>
                <input value={upSource} onChange={(e) => setUpSource(e.target.value)} />
              </div>
              <div className="field">
                <label>Regulation</label>
                <select value={upReg} onChange={(e) => setUpReg(e.target.value)}>
                  <option value="general">general</option>
                  {Object.entries(regulations).map(([id, r]) => <option key={id} value={id}>{id} — {r.label}</option>)}
                </select>
              </div>
              <button className="btn-primary" type="submit" disabled={busy}>📥 Add</button>
            </form>
            <form onSubmit={scrapeUrl}>
              <div className="field">
                <label>URL</label>
                <input value={urlInput} onChange={(e) => setUrlInput(e.target.value)} placeholder="https://www.consumerfinance.gov/..." />
              </div>
              <div className="field">
                <label>Source name</label>
                <input value={urlSource} onChange={(e) => setUrlSource(e.target.value)} />
              </div>
              <div className="field">
                <label>Regulation</label>
                <select value={urlReg} onChange={(e) => setUrlReg(e.target.value)}>
                  <option value="general">general</option>
                  {Object.entries(regulations).map(([id, r]) => <option key={id} value={id}>{id} — {r.label}</option>)}
                </select>
              </div>
              <button className="btn-primary" type="submit" disabled={busy}>🌐 Scrape & Add</button>
            </form>
          </div>
          <hr className="divider" />
        </>
      )}
      <h3>🔍 Test Retrieval</h3>
      <div className="row">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="APR disclosure in advertising" />
        <button onClick={retrieve}>Search</button>
      </div>
      {results && results.map((r, i) => (
        <div className="card" key={i}>
          <strong>[{r.score}] {r.source}</strong> — {r.regulation}
          <p className="muted">{r.text}</p>
        </div>
      ))}
    </div>
  );
}
