import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../api/client";

export default function Layout() {
  const { user, logout, isRole } = useAuth();
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    api
      .get("/notifications?unread_only=true")
      .then((d) => setUnread(d.notifications.length))
      .catch(() => {});
  }, []);

  function signOut() {
    api.post("/auth/logout", {}).catch(() => {});
    logout();
    navigate("/login");
  }

  const canReview = isRole("compliance", "legal", "admin");

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">⚖️ Compliance</div>
        <div className="who">{user.name}</div>
        <div className="who-sub">{user.company} · {user.role.toUpperCase()}</div>
        <hr />
        <NavLink to="/" end className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>📊 Dashboard</NavLink>
        <NavLink to="/submit" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>➕ Submit Document</NavLink>
        <NavLink to="/my-submissions" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>📋 My Submissions</NavLink>
        {canReview && (
          <>
            <NavLink to="/review-queue" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>
              🔍 Review Queue{unread ? ` (${unread})` : ""}
            </NavLink>
            <NavLink to="/all-reviews" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>✅ All Reviews</NavLink>
          </>
        )}
        <NavLink to="/company-memory" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>🏢 Company Memory</NavLink>
        <NavLink to="/train-regulations" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>📚 Train Regulations</NavLink>
        <NavLink to="/reg-monitor" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>🛰️ Reg Monitor</NavLink>
        {canReview && (
          <>
            <NavLink to="/analytics" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>📈 Analytics</NavLink>
            <NavLink to="/audit-log" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>📜 Audit Log</NavLink>
          </>
        )}
        {isRole("admin") && (
          <NavLink to="/settings" className={({ isActive }) => `nav-btn${isActive ? " active" : ""}`}>⚙️ Settings</NavLink>
        )}
        <hr />
        <button className="nav-btn" onClick={signOut}>🚪 Sign Out</button>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
