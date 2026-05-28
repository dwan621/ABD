import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api/client";

interface AnomalyItem {
  id: string;
  dataset_id: string;
  column_name: string;
  anomaly_type: string;
  severity: string;
  detected_value: string | null;
  expected_range: string | null;
  ai_explanation: string | null;
  detected_at: string;
}

interface DetectResponse {
  dataset_id: string;
  total_anomalies: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  anomalies: AnomalyItem[];
}

const severityBadge = (s: string) => {
  const colors: Record<string, string> = {
    high: "bg-red-900/60 text-red-400 border-red-700",
    medium: "bg-orange-900/60 text-orange-400 border-orange-700",
    low: "bg-yellow-900/60 text-yellow-400 border-yellow-700",
  };
  return (
    <span className={`text-xs border px-2 py-0.5 rounded-full ${colors[s] || "bg-gray-800 text-gray-400"}`}>
      {s}
    </span>
  );
};

export default function AnomalyPage() {
  const { id } = useParams<{ id: string }>();
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<{ total: number; high: number; medium: number; low: number } | null>(null);

  const fetchAnomalies = () => {
    setLoading(true);
    setError("");
    api
      .get(`/datasets/${id}/anomalies`)
      .then((res) => {
        setAnomalies(res.data);
        const counts = { total: res.data.length, high: 0, medium: 0, low: 0 };
        res.data.forEach((a: AnomalyItem) => {
          if (a.severity === "high") counts.high++;
          else if (a.severity === "medium") counts.medium++;
          else counts.low++;
        });
        setSummary(counts.total > 0 ? counts : null);
      })
      .catch((err) => setError(err.response?.data?.detail || "Failed to load anomalies"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchAnomalies();
  }, [id]);

  const handleDetect = async () => {
    setDetecting(true);
    setError("");
    try {
      const res = await api.post(`/datasets/${id}/anomalies/detect`);
      const data: DetectResponse = res.data;
      setAnomalies(data.anomalies);
      setSummary({
        total: data.total_anomalies,
        high: data.high_count,
        medium: data.medium_count,
        low: data.low_count,
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || "Detection failed");
    } finally {
      setDetecting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-3 py-8 text-gray-400">
        <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
        Loading anomalies...
      </div>
    );
  }

  const hasAnomalies = anomalies.length > 0;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold">Anomaly Detection</h2>
        <button
          onClick={handleDetect}
          disabled={detecting}
          className="px-5 py-2.5 bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500 disabled:opacity-50 rounded-lg font-medium text-sm flex items-center gap-2"
        >
          {detecting ? (
            <>
              <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
              Detecting...
            </>
          ) : (
            "Detect Anomalies"
          )}
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg px-4 py-3 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Detecting progress */}
      {detecting && (
        <div className="flex flex-col items-center gap-4 py-16">
          <div className="animate-spin h-8 w-8 border-2 border-red-500 border-t-transparent rounded-full" />
          <p className="text-gray-400">Computing statistics and running Isolation Forest...</p>
          <p className="text-sm text-gray-500">This may take 10-20 seconds</p>
        </div>
      )}

      {/* Summary stats bar */}
      {summary && !detecting && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-white">{summary.total}</p>
            <p className="text-xs text-gray-400 mt-1">Total</p>
          </div>
          <div className="bg-gray-900 border border-red-800/50 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-red-400">{summary.high}</p>
            <p className="text-xs text-red-400/70 mt-1">High</p>
          </div>
          <div className="bg-gray-900 border border-orange-800/50 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-orange-400">{summary.medium}</p>
            <p className="text-xs text-orange-400/70 mt-1">Medium</p>
          </div>
          <div className="bg-gray-900 border border-yellow-800/50 rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-yellow-400">{summary.low}</p>
            <p className="text-xs text-yellow-400/70 mt-1">Low</p>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!hasAnomalies && !detecting && (
        <div className="text-center py-16 bg-gray-900 border border-gray-800 rounded-xl">
          <p className="text-4xl mb-3">&#128270;</p>
          <p className="text-gray-400 mb-2">No anomalies detected</p>
          <p className="text-sm text-gray-500">
            Click "Detect Anomalies" to scan this dataset for statistical outliers
          </p>
        </div>
      )}

      {/* Anomaly cards */}
      {hasAnomalies && !detecting && (
        <div className="space-y-2">
          {anomalies.map((a) => (
            <div key={a.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm text-blue-400">{a.column_name}</span>
                  <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
                    {a.anomaly_type}
                  </span>
                  {severityBadge(a.severity)}
                </div>
                <span className="text-xs text-gray-500">
                  {new Date(a.detected_at).toLocaleString()}
                </span>
              </div>
              {a.detected_value && (
                <p className="text-sm text-gray-300 mb-1">
                  Value: <span className="font-mono text-red-300">{a.detected_value}</span>
                </p>
              )}
              {a.expected_range && (
                <p className="text-sm text-gray-400 mb-1">
                  Expected: <span className="font-mono">{a.expected_range}</span>
                </p>
              )}
              {a.ai_explanation && (
                <p className="text-sm text-indigo-300 mt-2">
                  AI: {a.ai_explanation}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
