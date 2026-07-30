import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export default function Submit() {
  const navigate = useNavigate();
  const [regulations, setRegulations] = useState({});
  const [docTypes, setDocTypes] = useState({});
  const [title, setTitle] = useState("");
  const [product, setProduct] = useState("");
  const [priority, setPriority] = useState("normal");
  const [docType, setDocType] = useState("marketing");
  const [channel, setChannel] = useState("email");
  const [method, setMethod] = useState("text");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [selectedRegs, setSelectedRegs] = useState({});
  const [runConflict, setRunConflict] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.get("/regulations").then((d) => {
      setRegulations(d.regulations);
      const all = {};
      Object.keys(d.regulations).forEach((r) => (all[r] = true));
      setSelectedRegs(all);
    });
    api.get("/memory/doc-types").then((d) => setDocTypes(d.doc_types));
  }, []);

  function toggleAll(checked) {
    const all = {};
    Object.keys(regulations).forEach((r) => (all[r] = checked));
    setSelectedRegs(all);
  }

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    const activeRegs = Object.keys(selectedRegs).filter((r) => selectedRegs[r]);
    if (!title.trim() || activeRegs.length === 0 || (method === "text" && !text.trim()) || (method === "file" && !file)) {
      setError("Title, content, and at least one regulation are required.");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("title", title);
      form.append("doc_type", docType);
      form.append("product", product || "general");
      form.append("channel", channel);
      form.append("priority", priority);
      form.append("regulations", activeRegs.join(","));
      form.append("run_conflict", runConflict);
      if (method === "text") form.append("text", text);
      else form.append("file", file);

      const data = await api.postForm("/submissions", form);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    const findingCount = result.result.findings?.length || 0;
    const conflictCount = result.result.conflict_check?.conflicts?.length || 0;
    return (
      <div>
        <h2>✅ Submitted!</h2>
        <div className="alert alert-success">
          {findingCount} regulatory findings, {conflictCount} conflicts. Overall risk: {(result.result.overall_risk || "?").toUpperCase()}
        </div>
        <div className="row">
          <button className="btn-primary" onClick={() => navigate(`/submissions/${result.id}`)}>View full results →</button>
          <button onClick={() => { setResult(null); setTitle(""); setText(""); setFile(null); }}>Submit another</button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2>➕ Submit Document for Compliance Review</h2>
      {error && <div className="alert alert-error">{error}</div>}
      <form onSubmit={onSubmit}>
        <div className="row">
          <div className="field">
            <label>Document title *</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Q2 2025 Freedom Unlimited Campaign" />
          </div>
          <div className="field">
            <label>Product</label>
            <input value={product} onChange={(e) => setProduct(e.target.value)} placeholder="Freedom Unlimited" />
          </div>
          <div className="field">
            <label>Priority</label>
            <select value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </div>
        </div>
        <div className="row">
          <div className="field">
            <label>Document type</label>
            <select value={docType} onChange={(e) => setDocType(e.target.value)}>
              {Object.entries(docTypes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Channel</label>
            <select value={channel} onChange={(e) => setChannel(e.target.value)}>
              {["email", "web", "print", "in-branch", "mobile", "call-center", "general"].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        <h3>Content</h3>
        <div className="row" style={{ marginBottom: 8 }}>
          <label className="checkbox-item"><input type="radio" checked={method === "text"} onChange={() => setMethod("text")} /> Paste text</label>
          <label className="checkbox-item"><input type="radio" checked={method === "file"} onChange={() => setMethod("file")} /> Upload file</label>
        </div>
        {method === "text" ? (
          <div className="field">
            <textarea rows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste marketing copy, agreement, policy, script…" />
          </div>
        ) : (
          <div className="field">
            <input type="file" accept=".txt,.pdf,.docx,.doc" onChange={(e) => setFile(e.target.files[0])} />
          </div>
        )}

        <h3>Regulations & Options</h3>
        <div className="row">
          <div style={{ flex: 1 }}>
            <label className="checkbox-item">
              <input type="checkbox" checked={Object.values(selectedRegs).every(Boolean)} onChange={(e) => toggleAll(e.target.checked)} /> All regulations
            </label>
            <div className="checkbox-grid" style={{ marginTop: 8 }}>
              {Object.entries(regulations).map(([id, r]) => (
                <label className="checkbox-item" key={id}>
                  <input type="checkbox" checked={!!selectedRegs[id]} onChange={(e) => setSelectedRegs({ ...selectedRegs, [id]: e.target.checked })} />
                  {r.label}
                </label>
              ))}
            </div>
          </div>
          <div style={{ flex: 1 }}>
            <label className="checkbox-item">
              <input type="checkbox" checked={runConflict} onChange={(e) => setRunConflict(e.target.checked)} /> Check against prior company communications
            </label>
            <p className="muted">Upload your prior materials in Company Memory to enable this.</p>
          </div>
        </div>

        <button className="btn-primary" type="submit" disabled={busy}>
          {busy ? "Running compliance analysis… 30–60 seconds" : "🔍 Submit for Analysis"}
        </button>
      </form>
    </div>
  );
}
