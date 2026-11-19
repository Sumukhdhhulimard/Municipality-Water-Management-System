
import React, { useCallback, useEffect, useState } from "react";
const API = "http://127.0.0.1:8000";

export default function IncidentManagement({ token }) {
  const [incidents, setIncidents] = useState([]);
  const [technicians, setTechnicians] = useState([]);
  const [history, setHistory] = useState([]);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const request = useCallback(async (path, options = {}) => {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        ...options.headers
      }
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`${response.status}: ${body}`);
    }

    return response.json();
  }, [token]);

  const load = useCallback(async () => {
    const [incidentData, technicianData] = await Promise.all([
      request("/operator/incidents"),
      request("/operator/incidents/technicians")
    ]);
    setIncidents(incidentData);
    setTechnicians(technicianData);
  }, [request]);

  useEffect(() => {
    if (!token) return;
    load().catch(err => setError(err.message));
  }, [token, load]);

  async function perform(action, successMessage) {
    setBusy(true);
    setError("");
    setMessage("");

    try {
      await action();
      await load();
      setMessage(successMessage);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function scan() {
    perform(
      () => request("/operator/incidents/scan", {
        method: "POST"
      }),
      "Sensor scan completed."
    );
  }

  function sync() {
    perform(
      () => request("/operator/incidents/sync-history", {
        method: "POST"
      }),
      "Incident history synchronized."
    );
  }

  function assign(incident) {
    const eligible = technicians.filter(
      t => t.zone_id === incident.zone_id &&
           t.is_available
    );

    if (!eligible.length) {
      setError("No available technician in this zone.");
      return;
    }

    const answer = window.prompt(
      `Technician ID (${eligible.map(
        t => `${t.technician_id}: ${t.full_name}`
      ).join(", ")})`,
      String(eligible[0].technician_id)
    );

    if (answer === null) return;

    const id = Number(answer);

    if (!eligible.some(t => t.technician_id === id)) {
      setError("Select a valid available technician ID.");
      return;
    }

    perform(
      () => request(
        `/operator/incidents/${incident.incident_id}/assign`,
        {
          method: "POST",
          body: JSON.stringify({ technician_id: id })
        }
      ),
      "Technician assigned successfully."
    );
  }

  function complete(incident) {
    const notes = window.prompt("Repair notes:");

    if (notes === null) return;

    if (notes.trim().length < 5) {
      setError("Enter at least 5 characters.");
      return;
    }

    const costText = window.prompt("Repair cost:", "0");
    if (costText === null) return;

    const cost = Number(costText);

    if (!Number.isFinite(cost) || cost < 0) {
      setError("Enter a valid non-negative repair cost.");
      return;
    }

    perform(
      () => request(
        `/operator/incidents/${incident.incident_id}/complete`,
        {
          method: "POST",
          body: JSON.stringify({
            repair_notes: notes,
            repair_cost: cost
          })
        }
      ),
      "Incident resolved successfully."
    );
  }

  async function showHistory(incidentId) {
    setError("");
    try {
      const result = await request(
        `/operator/incidents/${incidentId}/history`
      );
      setSelected(incidentId);
      setHistory(result);
    } catch (err) {
      setError(err.message);
    }
  }

  if (!token) return <p>Operator login required.</p>;

  return (
    <section style={{ padding: 24 }}>
      <h1>Incident Management</h1>

      <div style={{ display: "flex", gap: 12 }}>
        <button disabled={busy} onClick={scan}>
          Scan Sensors
        </button>
        <button disabled={busy} onClick={sync}>
          Sync MongoDB History
        </button>
        <button disabled={busy} onClick={() =>
          load().catch(err => setError(err.message))
        }>
          Refresh
        </button>
      </div>

      {error && <p role="alert" style={{ color: "red" }}>
        {error}
      </p>}
      {message && <p role="status">{message}</p>}

      <h2>Incidents ({incidents.length})</h2>

      <div style={{ overflowX: "auto" }}>
        <table cellPadding="10" border="1"
          style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr>
              <th>ID</th>
              <th>Zone</th>
              <th>Problem</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Technician</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map(i => (
              <tr key={i.incident_id}>
                <td>{i.incident_id}</td>
                <td>{i.zone_name}</td>
                <td>{i.description}</td>
                <td>{i.severity}</td>
                <td>{i.status}</td>
                <td>{i.technician_name || "Unassigned"}</td>
                <td>
                  {i.status === "OPEN" && (
                    <button disabled={busy}
                      onClick={() => assign(i)}>
                      Assign
                    </button>
                  )}
                  {["ASSIGNED", "IN_PROGRESS"].includes(
                    i.status
                  ) && (
                    <button disabled={busy}
                      onClick={() => complete(i)}>
                      Complete
                    </button>
                  )}
                  <button onClick={() =>
                    showHistory(i.incident_id)
                  }>
                    History
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected !== null && (
        <section>
          <h2>History — Incident #{selected}</h2>
          {history.length === 0 && (
            <p>No synchronized events found.</p>
          )}
          {history.map(event => (
            <article key={event.event_id}
              style={{
                padding: 12,
                borderBottom: "1px solid #ddd"
              }}>
              <strong>{event.event_type}</strong>
              <p>{new Date(
                event.created_at
              ).toLocaleString()}</p>
              <pre style={{
                whiteSpace: "pre-wrap",
                overflowWrap: "anywhere"
              }}>
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            </article>
          ))}
        </section>
      )}
    </section>
  );
}
