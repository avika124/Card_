import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Badge from "../components/Badge";

export default function ReviewQueue() {
  const [statusFilter, setStatusFilter] = useState("pending");
  const [productFilter, setProductFilter] = useState("");
  const [subs, setSubs] = useState(null);

  useEffect(() => {
    api.post("/notifications/mark-read", {}).catch(() => {});
  }, []);

  useEffect(() => {
    const q = statusFilter === "all" ? "" : `?status=${statusFilter}`;
    api.get(`/submissions${q}`).then((d) => setSubs(d.submissions));
  }, [statusFilter]);

  if (!subs) return null;
  const filtered = productFilter
    ? subs.filter((s) => (s.product || "").toLowerCase().includes(productFilter.toLowerCase()))
    : subs;

  return (
    <div>
      <h2>🔍 Review Queue</h2>
      <div className="row">
        <div className="field">
          <label>Status</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="pending">Pending</option>
            <option value="in_review">In Review</option>
            <option value="all">All</option>
          </select>
        </div>
        <div className="field">
          <label>Product filter</label>
          <input value={productFilter} onChange={(e) => setProductFilter(e.target.value)} />
        </div>
      </div>
      {filtered.length === 0 && <div className="alert alert-info">No submissions match your filters.</div>}
      {filtered.map((s) => (
        <div className="list-row" key={s.id}>
          <div>
            <strong>{(s.priority === "urgent" || s.priority === "high") ? "🚨 " : ""}{s.title}</strong>
            <div className="muted">{s.submitter_name || "?"}</div>
          </div>
          <Badge status={s.status} />
          <Link to={`/submissions/${s.id}`} className="btn btn-primary">Review →</Link>
        </div>
      ))}
    </div>
  );
}
