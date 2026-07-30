export default function StatCard({ value, label }) {
  return (
    <div className="stat-card">
      <div className="stat-num">{value}</div>
      <div className="stat-lbl">{label}</div>
    </div>
  );
}
