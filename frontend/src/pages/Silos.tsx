import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function Silos() {
  const [readings, setReadings] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.silos()
      .then((d) => setReadings(d.readings))
      .catch((e) => setError(e.message));
  }, []);

  const latestBySilo = new Map<string, Record<string, unknown>>();
  for (const r of readings) {
    const id = String(r.silo_id);
    if (!latestBySilo.has(id)) latestBySilo.set(id, r);
  }
  const silos = Array.from(latestBySilo.entries());

  return (
    <>
      <div className="page-header">
        <h1>Silo Monitor</h1>
        <p>Temperature, humidity and fill levels across 17 silos</p>
      </div>
      {error && <p style={{ color: "var(--red)" }}>{error}</p>}
      <div className="cards">
        <div className="card"><h3>Tracked Silos</h3><div className="value blue">{silos.length}</div></div>
        <div className="card"><h3>Warnings</h3><div className="value yellow">{silos.filter(([, r]) => Number(r.temp_c) > 32 || Number(r.humidity_pct) > 70).length}</div></div>
        <div className="card"><h3>Low Fill</h3><div className="value red">{silos.filter(([, r]) => Number(r.fill_pct) < 10).length}</div></div>
      </div>
      <div className="table-wrap">
        <h2>Silo Status</h2>
        <table>
          <thead><tr><th>Silo</th><th>Temp (°C)</th><th>Humidity (%)</th><th>Fill (%)</th><th>Quality</th></tr></thead>
          <tbody>
            {silos.length === 0 ? (
              <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--text2)" }}>No silo readings yet</td></tr>
            ) : silos.map(([id, r]) => (
              <tr key={id}>
                <td><strong>{id}</strong></td>
                <td style={{ color: Number(r.temp_c) > 32 ? "var(--red)" : undefined }}>{Number(r.temp_c).toFixed(1)}</td>
                <td style={{ color: Number(r.humidity_pct) > 70 ? "var(--red)" : undefined }}>{Number(r.humidity_pct).toFixed(1)}</td>
                <td>{Number(r.fill_pct).toFixed(1)}</td>
                <td><span className={`badge ${String(r.quality_flag) === "ok" ? "ok" : "high"}`}>{String(r.quality_flag)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
