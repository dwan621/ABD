import { useState } from "react";
import api from "../api/client";
import DataTable from "../components/DataTable";
import ChartView from "../components/ChartView";

interface QueryResult {
  columns: string[];
  rows: any[][];
  row_count: number;
  execution_time_ms: number;
}

export default function QueryPage() {
  const [sql, setSql] = useState("SELECT * FROM iceberg.abd.default LIMIT 10");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<"table" | "chart">("table");

  const runQuery = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.post("/query/", { sql });
      setResult(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Query failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Query</h2>

      <div className="flex gap-2 mb-4">
        <textarea
          className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded text-gray-100 font-mono text-sm"
          rows={3}
          value={sql}
          onChange={(e) => setSql(e.target.value)}
        />
        <button
          onClick={runQuery}
          disabled={loading}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded self-end"
        >
          {loading ? "Running..." : "Run"}
        </button>
      </div>

      {error && <p className="text-red-400 mb-4">{error}</p>}

      {result && (
        <div>
          <div className="flex justify-between items-center mb-2">
            <p className="text-sm text-gray-400">
              {result.row_count} rows in {result.execution_time_ms}ms
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setViewMode("table")}
                className={`px-3 py-1 rounded text-sm ${viewMode === "table" ? "bg-blue-600" : "bg-gray-700"}`}
              >
                Table
              </button>
              <button
                onClick={() => setViewMode("chart")}
                className={`px-3 py-1 rounded text-sm ${viewMode === "chart" ? "bg-blue-600" : "bg-gray-700"}`}
              >
                Chart
              </button>
            </div>
          </div>
          {viewMode === "table" ? (
            <DataTable columns={result.columns} rows={result.rows} />
          ) : (
            <ChartView columns={result.columns} rows={result.rows} />
          )}
        </div>
      )}
    </div>
  );
}
