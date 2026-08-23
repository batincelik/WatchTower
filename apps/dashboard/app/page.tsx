type Monitor = { id: string; name: string; url: string; monitor_type: string; enabled: boolean; last_checked_at: string | null; next_check_at: string | null };
const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
async function monitors(): Promise<Monitor[]> {
  const response = await fetch(`${api}/monitors`, { cache: "no-store" });
  if (!response.ok) throw new Error("Watchtower API is unavailable");
  return response.json() as Promise<Monitor[]>;
}
export default async function Home() {
  const rows = await monitors();
  return <><section className="title"><div><h1>Monitors</h1><p>Live monitor configuration and scheduling state.</p></div><a className="button" href="/monitors/new">New monitor</a></section><div className="panel"><table><thead><tr><th>Monitor</th><th>Type</th><th>Status</th><th>Last check</th><th>Next check</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td><strong>{row.name}</strong><small>{row.url}</small></td><td>{row.monitor_type}</td><td><span className={row.enabled ? "ok" : "muted"}>{row.enabled ? "Monitoring" : "Paused"}</span></td><td>{row.last_checked_at ? new Date(row.last_checked_at).toLocaleString() : "Never"}</td><td>{row.next_check_at ? new Date(row.next_check_at).toLocaleString() : "—"}</td></tr>)}</tbody></table>{rows.length === 0 && <p className="empty">No monitors yet. Create one to establish its first baseline.</p>}</div></>;
}
