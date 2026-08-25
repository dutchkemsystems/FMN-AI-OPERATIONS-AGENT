import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function Security() {
  const [alerts, setAlerts] = useState<Array<Record<string, unknown>>>([]);
  const [events, setEvents] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.securityAlerts(false), api.visionEvents()])
      .then(([a, v]) => { setAlerts(a.alerts); setEvents(v.events); })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <div className="page-header">
        <h1>Security</h1>
        <p>Intrusion alerts, vision events and security monitoring</p>
      </div>
      {error && <p style={{ color: "var(--red)" }}>{error}</p>}
      <div className="cards">
        <div className="card"><h3>Unresolved Alerts</h3><div className={`value ${alerts.length > 0 ? "red" : "green"}`}>{alerts.length}</div></div>
        <div className="card"><h3>Vision Events</h3><div className="value blue">{events.length}</div></div>
      </div>
      <div className="table-wrap">
        <h2>Security Alerts</h2>
        <table>
          <thead><tr><th>ID</th><th>Source</th><th>Severity</th><th>Message</th><th>Timestamp</th></tr></thead>
          <tbody>
            {alerts.length === 0 ? (
              <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--text2)" }}>No unresolved alerts</td></tr>
            ) : alerts.map((a, i) => (
              <tr key={i}>
                <td>#{String(a.id)}</td>
                <td>{String(a.source)}</td>
                <td><span className={`badge ${String(a.severity)}`}>{String(a.severity)}</span></td>
                <td>{String(a.message)}</td>
                <td>{String(a.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="table-wrap">
        <h2>Vision Events</h2>
        <table>
          <thead><tr><th>Camera</th><th>Type</th><th>Confidence</th><th>Timestamp</th></tr></thead>
          <tbody>
            {events.length === 0 ? (
              <tr><td colSpan={4} style={{ textAlign: "center", color: "var(--text2)" }}>No vision events</td></tr>
            ) : events.map((e, i) => (
              <tr key={i}>
                <td>{String(e.camera_id)}</td>
                <td><span className={`badge ${String(e.event_type) === "intrusion" ? "critical" : "medium"}`}>{String(e.event_type)}</span></td>
                <td>{(Number(e.confidence) * 100).toFixed(1)}%</td>
                <td>{String(e.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
