import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api from "../api/client";

interface ColumnInfo {
  id: string;
  col_name: string;
  data_type: string;
  ai_description: string | null;
  tags: string[];
}

interface DictionaryData {
  dataset_id: string;
  table_name: string;
  row_count: number;
  columns: ColumnInfo[];
}

export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<DictionaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [editingCol, setEditingCol] = useState<string | null>(null);
  const [editDesc, setEditDesc] = useState("");
  const [editTags, setEditTags] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .get(`/datasets/${id}/dictionary`)
      .then((res) => { if (!cancelled) setData(res.data); })
      .catch((err) => { if (!cancelled) setError(err.response?.data?.detail || "Failed to load dictionary"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);

  const handleRegenerate = async () => {
    setEditingCol(null);
    setGenerating(true);
    setError("");
    try {
      const res = await api.post(`/datasets/${id}/dictionary/regenerate`);
      setData(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to regenerate");
    } finally {
      setGenerating(false);
    }
  };

  const startEdit = (col: ColumnInfo) => {
    setEditingCol(col.id);
    setEditDesc(col.ai_description || "");
    setEditTags(col.tags.join(", "));
  };

  const cancelEdit = () => {
    setEditingCol(null);
    setEditDesc("");
    setEditTags("");
  };

  const saveEdit = async (colId: string) => {
    setSaving(true);
    try {
      const tags = editTags
        .split(",")
        .map((t) => t.trim())
        .filter((t) => t.length > 0);
      const res = await api.patch(`/columns/${colId}`, {
        ai_description: editDesc,
        tags,
      });
      if (data) {
        setData({
          ...data,
          columns: data.columns.map((c) =>
            c.id === colId
              ? { ...c, ai_description: res.data.ai_description, tags: res.data.tags }
              : c
          ),
        });
      }
      setEditingCol(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-3 py-8 text-gray-400">
        <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
        Loading data dictionary...
      </div>
    );
  }

  if (!data && error) {
    return (
      <div className="bg-red-900/30 border border-red-800 rounded-lg px-4 py-3">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const hasDescriptions = data.columns.some((c) => c.ai_description);

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold">{data.table_name}</h2>
          <div className="flex gap-6 mt-1 text-sm text-gray-400">
            <span>Table: {data.table_name}</span>
            <span>{data.row_count.toLocaleString()} rows</span>
            <span>{data.columns.length} columns</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(`/datasets/${id}/lineage`)}
            className="px-5 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-lg font-medium text-sm"
          >
            Lineage
          </button>
          <button
            onClick={() => navigate(`/datasets/${id}/anomalies`)}
            className="px-5 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-lg font-medium text-sm"
          >
            Anomalies
          </button>
          <button
            onClick={handleRegenerate}
            disabled={generating}
            className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:opacity-50 rounded-lg font-medium text-sm flex items-center gap-2"
          >
            {generating ? (
              <>
                <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                Generating...
              </>
            ) : (
              "Regenerate Descriptions"
            )}
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg px-4 py-3 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Empty state */}
      {!hasDescriptions && !generating && (
        <div className="text-center py-16 bg-gray-900 border border-gray-800 rounded-xl mb-6">
          <p className="text-4xl mb-3">&#128214;</p>
          <p className="text-gray-400 mb-2">No data dictionary yet</p>
          <p className="text-sm text-gray-500">
            Click "Regenerate Descriptions" to generate AI-powered column descriptions
          </p>
        </div>
      )}

      {/* Generating skeleton */}
      {generating && (
        <div className="flex flex-col items-center gap-4 py-16">
          <div className="animate-spin h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full" />
          <p className="text-gray-400">AI is analyzing columns and generating descriptions...</p>
          <p className="text-sm text-gray-500">This may take 10-20 seconds</p>
        </div>
      )}

      {/* Column cards */}
      {hasDescriptions && !generating && (
        <div className="space-y-2">
          {data.columns.map((col) => (
            <div
              key={col.id}
              className="bg-gray-900 border border-gray-800 rounded-xl p-4"
            >
              {editingCol === col.id ? (
                /* Inline edit */
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="font-mono text-sm text-blue-400">{col.col_name}</span>
                    <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
                      {col.data_type}
                    </span>
                  </div>
                  <label className="text-xs text-gray-500 block mb-1">Description</label>
                  <input
                    value={editDesc}
                    onChange={(e) => setEditDesc(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm mb-3 text-gray-200"
                  />
                  <label className="text-xs text-gray-500 block mb-1">
                    Tags (comma separated)
                  </label>
                  <input
                    value={editTags}
                    onChange={(e) => setEditTags(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm mb-3 text-gray-200"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => saveEdit(col.id)}
                      disabled={saving}
                      className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded text-sm"
                    >
                      {saving ? "Saving..." : "Save"}
                    </button>
                    <button
                      onClick={cancelEdit}
                      className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                /* Display */
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm text-blue-400">{col.col_name}</span>
                      <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
                        {col.data_type}
                      </span>
                    </div>
                    <button
                      onClick={() => startEdit(col)}
                      className="text-xs text-gray-500 hover:text-gray-300"
                    >
                      Edit
                    </button>
                  </div>
                  {col.ai_description && (
                    <p className="text-sm text-indigo-300 mb-2">
                      AI: {col.ai_description}
                    </p>
                  )}
                  {col.tags.length > 0 && (
                    <div className="flex gap-2 flex-wrap">
                      {col.tags.map((tag) => (
                        <span
                          key={tag}
                          className="text-xs bg-indigo-900/50 text-indigo-300 px-2 py-0.5 rounded-full"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
