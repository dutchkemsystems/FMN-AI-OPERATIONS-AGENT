const BASE = "/api";

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => request<{ status: string; app: string; environment: string }>("/health"),
  dashboard: () => request<Record<string, number>>("/dashboard"),
  agents: () => request<{ agents: Record<string, Record<string, unknown>> }>("/agents"),
  agentRuns: (limit = 20) => request<{ runs: Array<Record<string, unknown>> }>(`/agents/runs?limit=${limit}`),
  energyReadings: (limit = 50) => request<{ readings: Array<Record<string, unknown>> }>(`/energy/readings?limit=${limit}`),
  trucks: () => request<{ trucks: Array<Record<string, unknown>> }>("/logistics/trucks"),
  orders: (status?: string) => request<{ orders: Array<Record<string, unknown>> }>(`/logistics/orders${status ? `?status=${status}` : ""}`),
  shipments: (status?: string) => request<{ shipments: Array<Record<string, unknown>> }>(`/logistics/shipments${status ? `?status=${status}` : ""}`),
  silos: () => request<{ readings: Array<Record<string, unknown>> }>("/silos"),
  fxRates: (limit = 20) => request<{ rates: Array<Record<string, unknown>> }>(`/market/fx?limit=${limit}`),
  batches: (limit = 20) => request<{ batches: Array<Record<string, unknown>> }>(`/production/batches?limit=${limit}`),
  securityAlerts: (resolved?: boolean) => request<{ alerts: Array<Record<string, unknown>> }>(`/security/alerts${resolved !== undefined ? `?resolved=${resolved}` : ""}`),
  visionEvents: (limit = 30) => request<{ events: Array<Record<string, unknown>> }>(`/vision/events?limit=${limit}`),
  blockchainRecords: (limit = 30) => request<{ records: Array<Record<string, unknown>> }>(`/blockchain/records?limit=${limit}`),
  blockchainVerify: () => request<{ valid: boolean; checked: number }>("/blockchain/verify"),
  reports: (kind?: string) => request<{ reports: Array<Record<string, unknown>> }>(`/reports${kind ? `?kind=${kind}` : ""}`),
  actions: (limit = 50) => request<{ actions: Array<Record<string, unknown>> }>(`/actions?limit=${limit}`),
  wasteReports: (limit = 20) => request<{ waste_reports: Array<Record<string, unknown>> }>(`/waste/reports?limit=${limit}`),
};
