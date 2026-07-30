import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function CompanyMemory() {
  const { isRole } = useAuth();
  const canEdit = isRole("compliance", "legal", "admin");
  const [docTypes, setDocTypes] = useState({});
  const [stats, setStats] = useState({});
  const [docs, setDocs] = useState([]);
  const [filter, setFilter] = useState("all");
  const [source, setSource] = useState("");
  const [docType, setDocType] = useState("marketing");
  const [product, setProduct] = useState("");
  const [date, setDate] = useState("");
  const [version, setVersion] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);

  function refresh() {
    api.get("/memory/stats").then(setStats);
    api.get(`/memory/documents${filter !== "all" ? `?doc_type=${filter}` : ""}`).then((d) => setDocs(d.documents));
  }

  useEffect(() => {
    api.get("/memory/doc-types").then((d) => setDocTypes(d.doc_types));
  }, []);

  useEffect(refresh, [filter]);

  async function onAdd(e) {
    e.preventDefault();
    setError(""); setSuccess("");
    if (!source.trim() || (!file && !text.trim())) {
      setError("Provide a name and either a file or pasted text.");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("source", source);
      form.append("doc_type", docType);
      form.append("product", product || "general");
      form.append("date", date);
      form.append("version", version);
      if (file) form.append("file", file);
      else form.append("text", text);
      const res = await api.postForm("/memory/documents", form);
      setSuccess(`'${source}' — ${res.chunks_added} chunks indexed`);
      setSource(""); setText(""); setFile(null);
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function bulkLoad() {
    setBusy(true); setError(""); setSuccess("");
    try {
      const res = await api.post("/memory/bulk-load-samples", {});
      setSuccess(`Loaded ${res.loaded.length} sample documents`);
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteDoc(name) {
    await api.del(`/memory/documents/${encodeURIComponent(name)}`);
    refresh();
  }

  return (
    <div>
      <h2>🏢 Company Memory</h2>
      <p>Upload prior <strong>marketing, policies, agreements, scripts</strong> — every new submission is checked against these for contradictions.</p>
      <div className="stat-grid">
        {Object.entries(docTypes).map(([k, v]) => (
          <div className="stat-card" key={k}><div className="stat-num">{stats[k] || 0}</div><div className="stat-lbl">{v}</div></div>
        ))}
      </div>
      <hr className="divider" />
      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}
      {canEdit && (
        <>
          <form onSubmit={onAdd}>
            <div className="row">
              <div className="field">
                <label>File</label>
                <input type="file" accept=".txt,.pdf,.docx,.doc,.md" onChange={(e) => setFile(e.target.files[0])} />
              </div>
              <div className="field">
                <label>Name *</label>
                <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Q2 2024 Email Campaign" />
              </div>
              <div className="field">
                <label>Date</label>
                <input value={date} onChange={(e) => setDate(e.target.value)} placeholder="2024-06-01" />
              </div>
            </div>
            <div className="row">
              <div className="field">
                <label>Type</label>
                <select value={docType} onChange={(e) => setDocType(e.target.value)}>
                  {Object.entries(docTypes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div className="field">
                <label>Product</label>
                <input value={product} onChange={(e) => setProduct(e.target.value)} placeholder="Freedom Unlimited" />
              </div>
              <div className="field">
                <label>Version</label>
                <input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="v2.1" />
              </div>
            </div>
            <div className="field">
              <label>Or paste text directly</label>
              <textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} />
            </div>
            <button className="btn-primary" type="submit" disabled={busy}>📥 Add to Company Memory</button>
          </form>
          <hr className="divider" />
          <button onClick={bulkLoad} disabled={busy}>⚡ Bulk load Chase sample documents</button>
        </>
      )}
      <hr className="divider" />
      <h3>📋 Stored Documents</h3>
      <div className="field" style={{ maxWidth: 260 }}>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All types</option>
          {Object.entries(docTypes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {docs.length === 0 && <div className="alert alert-info">No documents stored.</div>}
      {docs.map((doc) => (
        <div className="list-row" key={doc.source}>
          <div>
            📄 <strong>{doc.source}</strong>{" "}
            <span className="muted">{docTypes[doc.doc_type] || ""} | {doc.product || "general"} | {doc.date || ""}</span>
          </div>
          {canEdit && <button onClick={() => deleteDoc(doc.source)}>🗑️</button>}
        </div>
      ))}
    </div>
  );
}
