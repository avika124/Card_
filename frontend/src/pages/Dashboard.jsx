import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import Badge from "../components/Badge";
import StatCard from "../components/StatCard";

export default function Dashboard() {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [subs, setSubs] = useState([]);
  const [notifs, setNotifs] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get("/analytics"),
      api.get("/submissions"),
      api.get("/notifications"),
    ])
      .then(([a, s, n]) => {
        setAnalytics(a);
        setSubs(s.submissions.slice(0, 8));
        setNotifs(n.notifications);
      })
      .catch((e) => setError(e.message));
  }, []);

  async function markAllRead() {
    await api.post("/notifications/mark-read", {});
    setNotifs(notifs.map((n) => ({ ...n, is_read: 1 })));
  }

  return (
    <div>
      <h2>👋 Welcome back, {user.name.split(" ")[0]}</h2>
      <p className="muted">{user.company} · {new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}</p>
      {error && <div className="alert alert-error">{error}</div>}
      {analytics && (
        <div className="stat-grid">
          <StatCard value={analytics.total_submissions} label="Total" />
          <StatCard value={analytics.pending} label="Pending" />
          <StatCard value={analytics.by_status.approved || 0} label="Approved" />
          <StatCard value={analytics.by_status.rejected || 0} label="Rejected" />
          <StatCard value={analytics.total_conflicts} label="Conflicts" />
        </div>
      )}
      <div className="row" style={{ alignItems: "flex-start" }}>
        <div style={{ flex: 2 }}>
          <h3>Recent Submissions</h3>
          {subs.length === 0 && <div className="alert alert-info">No submissions yet. Click <Link to="/submit">Submit Document</Link> to get started.</div>}
          {subs.map((s) => (
            <div className="card" key={s.id}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <strong>{s.title}</strong>
                  <br />
                  <span className="muted">{s.submitter_name || "?"} · {s.submitted_at.slice(0, 10)}</span>
                </div>
                <div>
                  <Badge status={s.status} />{" "}
                  <Link to={`/submissions/${s.id}`} className="btn">View →</Link>
                </div>
              </div>
            </div>
          ))}
        </div>
        <div style={{ flex: 1 }}>
          <h3>🔔 Notifications</h3>
          {notifs.length === 0 && <div className="alert alert-info">All caught up!</div>}
          {notifs.slice(0, 5).map((n) => (
            <div className="card" key={n.id}>
              <strong>{n.title}</strong> {!n.is_read && "🔵"}
              <div className="muted">{n.message}</div>
              <div className="muted">{n.created_at.slice(0, 16).replace("T", " ")}</div>
            </div>
          ))}
          {notifs.some((n) => !n.is_read) && (
            <button onClick={markAllRead}>Mark all read</button>
          )}
          {analytics && (
            <>
              <hr className="divider" />
              <h3>📊 Risk Breakdown</h3>
              {["high", "medium", "low", "pass"].map((risk) => {
                const n = analytics.by_risk[risk];
                if (!n) return null;
                return <div key={risk}><Badge status={risk} /> {n}</div>;
              })}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
