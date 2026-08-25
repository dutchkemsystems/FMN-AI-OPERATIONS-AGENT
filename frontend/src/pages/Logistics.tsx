import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function Logistics() {
  const [orders, setOrders] = useState<Array<Record<string, unknown>>>([]);
  const [shipments, setShipments] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.orders(), api.shipments()])
      .then(([o, s]) => { setOrders(o.orders); setShipments(s.shipments); })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <div className="page-header">
        <h1>Logistics</h1>
        <p>Orders, shipments and fleet management</p>
      </div>
      {error && <p style={{ color: "var(--red)" }}>{error}</p>}
      <div className="cards">
        <div className="card"><h3>Pending Orders</h3><div className="value yellow">{orders.filter((o) => o.status === "pending").length}</div></div>
        <div className="card"><h3>Dispatched</h3><div className="value green">{shipments.filter((s) => s.status === "dispatched").length}</div></div>
        <div className="card"><h3>Total Orders</h3><div className="value blue">{orders.length}</div></div>
      </div>
      <div className="table-wrap">
        <h2>Recent Orders</h2>
        <table>
          <thead><tr><th>Reference</th><th>Customer</th><th>Region</th><th>Tons</th><th>Status</th></tr></thead>
          <tbody>
            {orders.length === 0 ? (
              <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--text2)" }}>No orders yet</td></tr>
            ) : orders.map((o, i) => (
              <tr key={i}>
                <td>{String(o.reference)}</td>
                <td>{String(o.customer)}</td>
                <td>{String(o.region)}</td>
                <td>{Number(o.tons).toLocaleString()}</td>
                <td><span className={`badge ${String(o.status)}`}>{String(o.status)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="table-wrap">
        <h2>Active Shipments</h2>
        <table>
          <thead><tr><th>ID</th><th>Origin</th><th>Destination</th><th>Distance</th><th>ETA (h)</th><th>Cost (₦)</th><th>Status</th></tr></thead>
          <tbody>
            {shipments.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: "center", color: "var(--text2)" }}>No shipments yet</td></tr>
            ) : shipments.map((s, i) => (
              <tr key={i}>
                <td>#{String(s.id)}</td>
                <td>{String(s.origin)}</td>
                <td>{String(s.destination)}</td>
                <td>{Number(s.distance_km).toLocaleString()} km</td>
                <td>{Number(s.eta_hours).toFixed(1)}</td>
                <td>₦{Number(s.cost_ngn).toLocaleString()}</td>
                <td><span className={`badge ${String(s.status)}`}>{String(s.status)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
