import { NavLink } from "react-router-dom";
import "./Sidebar.css";

const links = [
  { to: "/", label: "Dashboard", icon: "📊" },
  { to: "/energy", label: "Energy", icon: "⚡" },
  { to: "/logistics", label: "Logistics", icon: "🚚" },
  { to: "/silos", label: "Silos", icon: "🏭" },
  { to: "/security", label: "Security", icon: "🔒" },
  { to: "/blockchain", label: "Audit Ledger", icon: "⛓" },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-icon">🏭</span>
        <div>
          <div className="brand-title">FMN</div>
          <div className="brand-sub">AI Operations</div>
        </div>
      </div>
      <nav className="sidebar-nav">
        {links.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.to === "/"} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            <span className="nav-icon">{l.icon}</span>
            <span>{l.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">
        <a href="/docs" target="_blank" rel="noopener noreferrer" className="nav-link">
          <span className="nav-icon">📄</span>
          <span>API Docs</span>
        </a>
      </div>
    </aside>
  );
}
