export default function Badge({ status, children }) {
  const label = children ?? status.replace(/_/g, " ").toUpperCase();
  return <span className={`badge badge-${status}`}>{label}</span>;
}
