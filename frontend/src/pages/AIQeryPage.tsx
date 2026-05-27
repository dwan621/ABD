import { useState } from "react";
import api from "../api/client";
import DataTable from "../components/DataTable";
import ChartView from "../components/ChartView";

interface AIResult {
  sql: string;
  columns: string[];
  rows: any[][];
  row_count: number;
  execution_time_ms: number;
}

const EXAMPLE_QUESTIONS = [
  "Top 5 product categories by total sales",
  "Monthly revenue trend in 2025",
  "Average order value by province",
];

export default function AIQeryPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AIResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sqlVisible, setSqlVisible] = useState(true);
  const [viewMode, setViewMode] = useState<"table" | "chart">("table");
  const [stage, setStage] = useState(""); // "" | "generating" | "executing"

  const handleSubmit = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    setSqlVisible(true);
    try {
      setStage("generating");
      const res = await api.post("/ai/text-to-sql", { question: question.trim() });
      setResult(res.data);
      setStage("");
    } catch (err: any) {
      setError(err.response?.data?.detail || "AI query failed");
      setStage("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-xl font-bold mb-4">AI Query</h2>
      <p className="text-gray-400 mb-6">Ask questions in natural language — AI generates the SQL for you.</p>

      {/* Input area */}
      <div className="flex gap-3 mb-2">
        <textarea
          className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 resize-none"
          rows={2}
          placeholder="e.g. 'top 5 products by sales last month'"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={loading || !question.trim()}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg self-end font-medium"
        >
          {loading ? "Thinking..." : "Ask AI"}
        </button>
      </div>

      {/* Example prompts — only show in empty state */}
      {!result && !loading && !error && (
        <div className="flex gap-2 mb-6 flex-wrap">
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => setQuestion(q)}
              className="px-3 py-1.5 text-sm bg-gray-800 border border-gray-700 rounded-full text-gray-400 hover:text-gray-200 hover:border-gray-600"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center gap-3 py-8 text-gray-400">
          <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
          <span>{stage === "generating" ? "Generating SQL..." : "Executing query..."}</span>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg px-4 py-3 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Results area */}
      {result && (
        <div>
          {/* Generated SQL — collapsible */}
          <div className="mb-4">
            <button
              onClick={() => setSqlVisible(!sqlVisible)}
              className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 mb-2"
            >
              <span className={`transform transition-transform ${sqlVisible ? "rotate-90" : ""}`}>&#9654;</span>
              Generated SQL
            </button>
            {sqlVisible && (
              <pre className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-sm text-gray-300 overflow-x-auto">
                {result.sql}
              </pre>
            )}
          </div>

          {/* Stats bar */}
          <div className="flex justify-between items-center mb-3">
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

          {/* Data display */}
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
