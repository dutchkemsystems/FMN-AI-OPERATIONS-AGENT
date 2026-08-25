import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Energy from "./pages/Energy";
import Logistics from "./pages/Logistics";
import Silos from "./pages/Silos";
import Security from "./pages/Security";
import Blockchain from "./pages/Blockchain";
import "./App.css";

export default function App() {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/energy" element={<Energy />} />
          <Route path="/logistics" element={<Logistics />} />
          <Route path="/silos" element={<Silos />} />
          <Route path="/security" element={<Security />} />
          <Route path="/blockchain" element={<Blockchain />} />
        </Routes>
      </main>
    </div>
  );
}
