
import React, { useEffect, useState } from "react";
const API = "http://127.0.0.1:8000";

export default function AdvancedAnalytics({ token }) {
  const [overview, setOverview] = useState(null);
  const [leaks, setLeaks] = useState([]);
  const [consumption, setConsumption] = useState([]);
  const [quality, setQuality] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setError("Operator login required");
      setLoading(false);
      return;
    }

    const controller = new AbortController();

    async function fetchData(path) {
      const response = await fetch(`${API}${path}`, {
        headers: {
          Authorization: `Bearer ${token}`
        },
        signal: controller.signal
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(`${path}: ${message}`);
      }

      return response.json();
    }

    async function load() {
      try {
        setLoading(true);
        setError("");

        const [o, l, c, q] = await Promise.all([
          fetchData("/operator/advanced/overview"),
          fetchData("/operator/advanced/leakage"),
          fetchData("/operator/advanced/consumption"),
          fetchData("/operator/advanced/water-quality")
        ]);

        if (controller.signal.aborted) return;

        setOverview(o);
        setLeaks(l);
        setConsumption(c);
        setQuality(q);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err.message);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    load();

    return () => controller.abort();
  }, [token]);

  if (loading) return <p>Loading smart analytics...</p>;

  if (error) {
    return (
      <section>
        <h2>Advanced Analytics</h2>
        <p role="alert">{error}</p>
      </section>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <h1>Smart Water Analytics</h1>

      <div style={{
        display: "grid",
        gridTemplateColumns:
          "repeat(auto-fit, minmax(180px, 1fr))",
        gap: 16
      }}>
        <Metric
          title="Active Meters"
          value={overview?.meters?.active_meters ?? 0}
        />
        <Metric
          title="Meter Readings"
          value={overview?.readings?.total_readings ?? 0}
        />
        <Metric
          title="Possible Leak Events"
          value={
            overview?.leakage?.possible_leak_events ?? 0
          }
        />
        <Metric
          title="Sensor Events"
          value={overview?.sensor_events ?? 0}
        />
      </div>

      <h2>Possible Leakage Alerts</h2>
      <DataTable
        data={leaks}
        columns={[
          "meter_serial",
          "connection_id",
          "reading_date",
          "consumption_liters",
          "baseline_liters",
          "anomaly_status"
        ]}
      />

      <h2>Consumption Summary</h2>
      <DataTable
        data={consumption}
        columns={[
          "connection_id",
          "meter_serial",
          "reading_days",
          "total_liters",
          "average_daily_liters"
        ]}
      />

      <h2>Zone-wise Water Quality</h2>
      <DataTable
        data={quality}
        columns={[
          "zone_id",
          "total_readings",
          "average_ph",
          "average_turbidity",
          "average_chlorine",
          "abnormal_count"
        ]}
      />
    </div>
  );
}

function Metric({ title, value }) {
  return (
    <div style={{
      border: "1px solid #ddd",
      borderRadius: 10,
      padding: 18
    }}>
      <div style={{ fontSize: 14 }}>{title}</div>
      <strong style={{ fontSize: 28 }}>{value}</strong>
    </div>
  );
}

function DataTable({ data, columns }) {
  if (!data.length) return <p>No records found.</p>;

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{
        width: "100%",
        borderCollapse: "collapse"
      }}>
        <thead>
          <tr>
            {columns.map(column => (
              <th
                key={column}
                style={{
                  padding: 10,
                  borderBottom: "1px solid #ddd",
                  textAlign: "left"
                }}
              >
                {column.replaceAll("_", " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr key={index}>
              {columns.map(column => (
                <td
                  key={column}
                  style={{
                    padding: 10,
                    borderBottom: "1px solid #eee"
                  }}
                >
                  {String(row[column] ?? "-")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
