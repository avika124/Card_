import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function RegMonitor() {
  const { isRole } = useAuth();
  const canEdit = isRole("compliance", "legal", "admin");
  const [watches, setWatches] = useState(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [regulation, setRegulation] = useState("general");
  const [regulations, setRegulations] = useState({});

  function refresh() {
    api.get("/reg-monitor/watches").then((d) => setWatches(d.watches));
  }

  useEffect(() => {
    refresh();
    api.get("/regulations").then((d) => setRegulations(d.regulations));
  }, []);

  async function runCheck() {
    setBusy(true); setStatus("");
    try {
      const res = await api.post("/reg-monitor/run-check", {});
      setStatus(`Done: ${res.checked} checked, ${res.changed} changed`);
      refresh();
    } catch (err) {
      setStatus(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function seedDefaults() {
    setBusy(true);
    await api.post("/reg-monitor/seed-defaults", {});
    setBusy(false);
    refresh();
  }

  async function addWatch(e) {
    e.preventDefault();
    if (!url.trim() || !name.trim()) return;
    await api.post("/reg-monitor/watches", { url, name, regulation });
    setUrl(""); setName("");
    refresh();
  }

  if (!watches) return null;

  return (
    <div>
      <h2>🛰️ Regulatory Change Monitor</h2>
      <p className="muted">Watches government websites for changes and alerts your compliance team.</p>
      <div className="row" style={{ alignItems: "center" }}>
        <div className="alert alert-info" style={{ flex: 3 }}><strong>{watches.length}</strong> sources monitored</div>
        {canEdit && (
          <button className="btn-primary" style={{ flex: 1 }} onClick={runCheck} disabled={busy}>▶️ Run Check Now</button>
        )}
      </div>
      {status && <div className="alert alert-success">{status}</div>}
      <hr className="divider" />
      {watches.length === 0 ? (
        canEdit && <button className="btn-primary" onClick={seedDefaults} disabled={busy}>⚡ Load all default sources</button>
      ) : (
        watches.map((w) => (
          <div className="list-row" key={w.id}>
            <div>
              <strong>{w.source_name}</strong>{" "}
              <span className="muted">{w.regulation.toUpperCase()} · Last: {(w.last_checked || "Never").slice(0, 10)}</span>
            </div>
            <span>{w.is_active ? "✅ Active" : "⏸️ Paused"}</span>
          </div>
        ))
      )}
      {canEdit && (
        <>
          <hr className="divider" />
          <h3>➕ Add Custom Source</h3>
          <form onSubmit={addWatch}>
            <div className="row">
              <div className="field">
                <label>URL</label>
                <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.cfpb.gov/..." />
              </div>
              <div className="field">
                <label>Name</label>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="CFPB Final Rules" />
              </div>
              <div className="field">
                <label>Regulation</label>
                <select value={regulation} onChange={(e) => setRegulation(e.target.value)}>
                  <option value="general">general</option>
                  {Object.entries(regulations).map(([id, r]) => <option key={id} value={id}>{id} — {r.label}</option>)}
                </select>
              </div>
            </div>
            <button className="btn-primary" type="submit">Add Watch</button>
          </form>
        </>
      )}
    </div>
  );
}
