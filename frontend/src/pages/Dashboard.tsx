import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function Dashboard() {
  const [data, setData] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dashboard()
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="page-header"><h1>Dashboard</h1><p style={{ color: "var(--red)" }}>{error}</p></div>;
  if (!data) return <div className="page-header"><h1>Dashboard</h1><p>Loading...</p></div>;

  const cards = [
    { label: "Agents Running", value: data.agents_running ?? 0, color: "blue" },
    { label: "Total Actions", value: data.total_actions ?? 0, color: "" },
    { label: "Active Shipments", value: data.active_shipments ?? 0, color: "green" },
    { label: "Pending Orders", value: data.pending_orders ?? 0, color: "yellow" },
    { label: "Unresolved Alerts", value: data.unresolved_alerts ?? 0, color: (data.unresolved_alerts ?? 0) > 0 ? "red" : "green" },
    { label: "Blockchain Records", value: data.blockchain_records ?? 0, color: "" },
  ];

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>FMN-AI Operations Agent — real-time overview</p>
      </div>
      <div className="cards">
        {cards.map((c) => (
          <div className="card" key={c.label}>
            <h3>{c.label}</h3>
            <div className={`value ${c.color}`}>{c.value}</div>
          </div>
        ))}
      </div>
    </>
  );
}
