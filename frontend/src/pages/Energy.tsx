import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function Energy() {
  const [readings, setReadings] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.energyReadings(30)
      .then((d) => setReadings(d.readings))
      .catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <div className="page-header">
        <h1>Energy Monitor</h1>
        <p>Real-time power source consumption and cost tracking</p>
      </div>
      {error && <p style={{ color: "var(--red)" }}>{error}</p>}
      <div className="table-wrap">
        <h2>Recent Readings</h2>
        <table>
          <thead>
            <tr>
              <th>Facility</th>
              <th>Source</th>
              <th>kWh</th>
              <th>Cost (₦)</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {readings.length === 0 ? (
              <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--text2)" }}>No readings yet</td></tr>
            ) : readings.map((r, i) => (
              <tr key={i}>
                <td>{String(r.facility)}</td>
                <td><span className={`badge ${r.source === "solar" ? "ok" : r.source === "diesel" ? "high" : ""}`}>{String(r.source)}</span></td>
                <td>{Number(r.kwh).toLocaleString()}</td>
                <td>₦{Number(r.cost_ngn).toLocaleString()}</td>
                <td>{String(r.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
