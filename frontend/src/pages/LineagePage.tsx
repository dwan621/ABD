import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import api from "../api/client";

interface LineageEdge {
  id: string;
  source_dataset_id: string;
  source_column: string;
  target_dataset_id: string;
  target_column: string;
  transform_expr: string | null;
}

interface LineageData {
  dataset_id: string;
  table_name: string;
  upstream: LineageEdge[];
  downstream: LineageEdge[];
}

export default function LineagePage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<LineageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"graph" | "upstream" | "downstream">("graph");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get(`/lineage/${id}`)
      .then((res) => { if (!cancelled) setData(res.data); })
      .catch((err) => { if (!cancelled) setError(err.response?.data?.detail || "Failed to load lineage"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center gap-3 py-8 text-gray-400">
        <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
        Loading lineage data...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/30 border border-red-800 rounded-lg px-4 py-3">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const hasEdges = data.upstream.length > 0 || data.downstream.length > 0;

  // Build ECharts graph data
  const nodeSet = new Map<string, string>();
  nodeSet.set(data.dataset_id, data.table_name);

  data.upstream.forEach((e) => nodeSet.set(e.source_dataset_id, e.source_dataset_id));
  data.downstream.forEach((e) => nodeSet.set(e.target_dataset_id, e.target_dataset_id));

  const graphNodes = Array.from(nodeSet.entries()).map(([nodeId, label]) => ({
    id: nodeId,
    name: label.length > 20 ? label.substring(0, 20) + "..." : label,
    symbolSize: nodeId === data.dataset_id ? 50 : 35,
    itemStyle: {
      color: nodeId === data.dataset_id ? "#4f46e5" : "#1e293b",
      borderColor: nodeId === data.dataset_id ? "#818cf8" : "#475569",
      borderWidth: 2,
    },
    label: { show: true, color: "#e2e8f0", fontSize: 11 },
  }));

  const graphLinks = [
    ...data.upstream.map((e) => ({
      source: e.source_dataset_id,
      target: data.dataset_id,
      label: { show: true, formatter: `${e.source_column} → ${e.target_column}`, fontSize: 10, color: "#94a3b8" },
    })),
    ...data.downstream.map((e) => ({
      source: data.dataset_id,
      target: e.target_dataset_id,
      label: { show: true, formatter: `${e.source_column} → ${e.target_column}`, fontSize: 10, color: "#94a3b8" },
    })),
  ];

  const graphOption = {
    tooltip: { formatter: "{b}" },
    series: [{
      type: "graph",
      layout: "force",
      force: { repulsion: 300, edgeLength: [150, 300] },
      roam: true,
      draggable: true,
      data: graphNodes,
      links: graphLinks,
      lineStyle: { color: "#475569", curveness: 0.2 },
    }],
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-bold">{data.table_name} — Data Lineage</h2>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {(["graph", "upstream", "downstream"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}
          >
            {t === "graph" ? "Lineage Graph" : t === "upstream" ? "Upstream" : "Downstream"}
          </button>
        ))}
      </div>

      {!hasEdges ? (
        <div className="text-center py-16 bg-gray-900 border border-gray-800 rounded-xl">
          <p className="text-gray-400">No lineage data available for this dataset</p>
          <p className="text-sm text-gray-500 mt-1">
            Lineage edges are created when datasets are derived from SQL transformations
          </p>
        </div>
      ) : tab === "graph" ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4" style={{ height: 500 }}>
          <ReactECharts option={graphOption} style={{ height: "100%" }} />
        </div>
      ) : tab === "upstream" ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left p-3 text-gray-400">Source Column</th>
                <th className="text-left p-3 text-gray-400">Target Column</th>
                <th className="text-left p-3 text-gray-400">Transform</th>
              </tr>
            </thead>
            <tbody>
              {data.upstream.map((e) => (
                <tr key={e.id} className="border-b border-gray-800/50">
                  <td className="p-3 font-mono text-blue-400">{e.source_column}</td>
                  <td className="p-3 font-mono text-blue-400">{e.target_column}</td>
                  <td className="p-3 text-gray-400">{e.transform_expr || "direct copy"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left p-3 text-gray-400">Source Column</th>
                <th className="text-left p-3 text-gray-400">Target Column</th>
                <th className="text-left p-3 text-gray-400">Transform</th>
              </tr>
            </thead>
            <tbody>
              {data.downstream.map((e) => (
                <tr key={e.id} className="border-b border-gray-800/50">
                  <td className="p-3 font-mono text-blue-400">{e.source_column}</td>
                  <td className="p-3 font-mono text-blue-400">{e.target_column}</td>
                  <td className="p-3 text-gray-400">{e.transform_expr || "direct copy"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
