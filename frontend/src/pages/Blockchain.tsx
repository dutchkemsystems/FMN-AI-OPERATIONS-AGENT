import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function Blockchain() {
  const [records, setRecords] = useState<Array<Record<string, unknown>>>([]);
  const [verify, setVerify] = useState<{ valid?: boolean; checked?: number } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.blockchainRecords(), api.blockchainVerify()])
      .then(([r, v]) => { setRecords(r.records); setVerify(v); })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <div className="page-header">
        <h1>Audit Ledger</h1>
        <p>Immutable blockchain records and chain verification</p>
      </div>
      {error && <p style={{ color: "var(--red)" }}>{error}</p>}
      <div className="cards">
        <div className="card"><h3>Total Blocks</h3><div className="value blue">{records.length}</div></div>
        <div className="card">
          <h3>Chain Integrity</h3>
          <div className={`value ${verify?.valid ? "green" : verify ? "red" : ""}`}>
            {verify?.valid ? "VALID" : verify ? "BROKEN" : "Checking..."}
          </div>
        </div>
        <div className="card"><h3>Blocks Verified</h3><div className="value">{verify?.checked ?? 0}</div></div>
      </div>
      <div className="table-wrap">
        <h2>Recent Blocks</h2>
        <table>
          <thead><tr><th>Block #</th><th>Type</th><th>TX Hash</th><th>Timestamp</th></tr></thead>
          <tbody>
            {records.length === 0 ? (
              <tr><td colSpan={4} style={{ textAlign: "center", color: "var(--text2)" }}>No blockchain records yet</td></tr>
            ) : records.map((r, i) => (
              <tr key={i}>
                <td>{String(r.block_number)}</td>
                <td><span className="badge">{String(r.event_type)}</span></td>
                <td style={{ fontFamily: "monospace", fontSize: ".75rem" }}>{String(r.tx_hash).substring(0, 24)}...</td>
                <td>{String(r.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
