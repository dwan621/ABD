import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api/client";
import DataTable from "../components/DataTable";
import ChartView from "../components/ChartView";

interface DatasetInfo {
  id: string;
  name: string;
  table_name: string;
  row_count: number;
  schema_json: { name: string; type: string }[];
}

interface InsightResult {
  columns: string[];
  rows: any[][];
  row_count: number;
  execution_time_ms: number;
  error?: string;
}

interface Insight {
  title: string;
  description: string;
  type: string;
  sql: string | null;
  result: InsightResult | null;
}

interface InsightsData {
  dataset_id: string;
  table_name: string;
  row_count: number;
  insights: Insight[];
}

const TYPE_COLORS: Record<string, string> = {
  summary: "bg-blue-900/40 text-blue-300 border-blue-800",
  trend: "bg-green-900/40 text-green-300 border-green-800",
  ranking: "bg-purple-900/40 text-purple-300 border-purple-800",
  anomaly: "bg-orange-900/40 text-orange-300 border-orange-800",
};

export default function InsightsPage() {
  const { id } = useParams<{ id: string }>();
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [data, setData] = useState<InsightsData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [datasetLoading, setDatasetLoading] = useState(true);
  const [expandedInsight, setExpandedInsight] = useState<number | null>(null);
  const [viewModes, setViewModes] = useState<Record<number, "table" | "chart">>({});

  useEffect(() => {
    api
      .get(`/datasets/${id}`)
      .then((res) => setDataset(res.data))
      .catch(() => setError("Failed to load dataset"))
      .finally(() => setDatasetLoading(false));
  }, [id]);

  const handleGenerate = async () => {
    setLoading(true);
    setError("");
    setData(null);
    try {
      const res = await api.post(`/ai/insights/${id}`);
      setData(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to generate insights");
    } finally {
      setLoading(false);
    }
  };

  if (datasetLoading) {
    return (
      <div className="flex items-center gap-3 py-8 text-gray-400">
        <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
        Loading dataset...
      </div>
    );
  }

  if (!dataset) {
    return (
      <div className="bg-red-900/30 border border-red-800 rounded-lg px-4 py-3">
        <p className="text-red-400">{error || "Dataset not found"}</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold">{dataset.name}</h2>
          <p className="text-sm text-gray-400 mt-1">
            Table: {dataset.table_name} | {dataset.row_count.toLocaleString()} rows |{" "}
            {dataset.schema_json?.length || 0} columns
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:opacity-50 rounded-lg font-medium text-sm flex items-center gap-2"
        >
          {loading ? (
            <>
              <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
              Analyzing...
            </>
          ) : data ? (
            "Regenerate Insights"
          ) : (
            "Generate Insights"
          )}
        </button>
      </div>

      {/* Empty state */}
      {!data && !loading && !error && (
        <div className="text-center py-16 bg-gray-900 border border-gray-800 rounded-xl">
          <p className="text-5xl mb-4">&#128269;</p>
          <p className="text-gray-400 mb-2">Click "Generate Insights" to analyze this dataset with AI</p>
          <p className="text-sm text-gray-500">
            The AI will examine schema and sample data to produce trends, rankings, and anomaly detection
          </p>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex flex-col items-center gap-4 py-16">
          <div className="animate-spin h-8 w-8 border-3 border-blue-500 border-t-transparent rounded-full" />
          <p className="text-gray-400">AI is analyzing {dataset.table_name}...</p>
          <p className="text-sm text-gray-500">This may take 10-20 seconds</p>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg px-4 py-3 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
          <p className="text-red-500 text-xs mt-1">You can try again — the input is preserved</p>
        </div>
      )}

      {/* Insights cards */}
      {data && (
        <div className="space-y-4">
          {data.insights.map((insight, idx) => (
            <div key={idx} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <div className="p-4">
                <div className="flex items-start gap-3">
                  <span className="text-2xl mt-0.5">
                    {insight.type === "summary" && "&#128202;"}
                    {insight.type === "trend" && "&#128200;"}
                    {insight.type === "ranking" && "&#127942;"}
                    {insight.type === "anomaly" && "&#9888;&#65039;"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <h3 className="font-semibold text-gray-100">{insight.title}</h3>
                      <span className={`px-2 py-0.5 rounded text-xs border ${TYPE_COLORS[insight.type]}`}>
                        {insight.type}
                      </span>
                    </div>
                    <p className="text-sm text-gray-400 leading-relaxed">{insight.description}</p>
                  </div>
                </div>

                {insight.sql && (
                  <div className="mt-3 ml-9">
                    <button
                      onClick={() => {
                        setExpandedInsight(expandedInsight === idx ? null : idx);
                        if (!(idx in viewModes)) {
                          setViewModes((prev) => ({ ...prev, [idx]: "table" }));
                        }
                      }}
                      className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300"
                    >
                      <span
                        className={`transform transition-transform ${expandedInsight === idx ? "rotate-90" : ""}`}
                      >
                        &#9654;
                      </span>
                      Show Query &amp; Data
                    </button>

                    {expandedInsight === idx && insight.result && (
                      <div className="mt-2 space-y-3">
                        <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-gray-300 overflow-x-auto">
                          {insight.sql}
                        </pre>

                        {insight.result.error ? (
                          <p className="text-red-400 text-sm">Query failed: {insight.result.error}</p>
                        ) : (
                          <>
                            <div className="flex items-center justify-between">
                              <p className="text-xs text-gray-500">
                                {insight.result.row_count} rows in {insight.result.execution_time_ms}ms
                              </p>
                              <div className="flex gap-1">
                                <button
                                  onClick={() => setViewModes((prev) => ({ ...prev, [idx]: "table" }))}
                                  className={`px-2 py-0.5 rounded text-xs ${viewModes[idx] === "table" ? "bg-blue-600" : "bg-gray-700"}`}
                                >
                                  Table
                                </button>
                                <button
                                  onClick={() => setViewModes((prev) => ({ ...prev, [idx]: "chart" }))}
                                  className={`px-2 py-0.5 rounded text-xs ${viewModes[idx] === "chart" ? "bg-blue-600" : "bg-gray-700"}`}
                                >
                                  Chart
                                </button>
                              </div>
                            </div>

                            {viewModes[idx] === "table" ? (
                              <DataTable columns={insight.result.columns} rows={insight.result.rows} />
                            ) : (
                              <ChartView columns={insight.result.columns} rows={insight.result.rows} />
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
