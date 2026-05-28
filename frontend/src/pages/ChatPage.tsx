import { useEffect, useRef, useState } from "react";
import api from "../api/client";
import DataTable from "../components/DataTable";
import ChartView from "../components/ChartView";

interface Message {
  role: string;
  content: string;
  sql?: string;
  result?: {
    columns: string[];
    rows: any[][];
    row_count: number;
    execution_time_ms: number;
  };
}

interface ChatResponse {
  session_id: string;
  answer: string;
  sql: string | null;
  result: {
    columns: string[];
    rows: any[][];
    row_count: number;
    execution_time_ms: number;
  } | null;
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<string[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedMsg, setExpandedMsg] = useState<number | null>(null);
  const [viewModes, setViewModes] = useState<Record<number, "table" | "chart">>({});
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleNewSession = async () => {
    try {
      const res = await api.post("/ai/chat/sessions");
      const sid = res.data.session_id;
      setSessions((prev) => [sid, ...prev]);
      setActiveSession(sid);
      setMessages([]);
      setError("");
    } catch {
      setError("Failed to create session");
    }
  };

  const handleSelectSession = async (sid: string) => {
    setActiveSession(sid);
    setError("");
    try {
      const res = await api.get(`/ai/chat/sessions/${sid}`);
      setMessages(res.data.messages || []);
    } catch {
      setMessages([]);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading || !activeSession) return;
    const msg = input.trim();
    setInput("");
    setError("");

    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setLoading(true);

    try {
      const res = await api.post<ChatResponse>("/ai/chat", {
        session_id: activeSession,
        message: msg,
      });
      const data = res.data;
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sql: data.sql || undefined,
          result: data.result || undefined,
        },
      ]);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Chat failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-5rem)] gap-4">
      {/* Session sidebar */}
      <aside className="w-56 flex flex-col bg-gray-900 border border-gray-800 rounded-lg overflow-hidden shrink-0">
        <div className="p-3 border-b border-gray-800">
          <button
            onClick={handleNewSession}
            className="w-full px-3 py-2 text-sm bg-blue-600 hover:bg-blue-700 rounded-lg"
          >
            + New Chat
          </button>
        </div>
        <div className="flex-1 overflow-auto p-2 space-y-1">
          {sessions.length === 0 && (
            <p className="text-xs text-gray-500 text-center py-4">No sessions yet</p>
          )}
          {sessions.map((sid) => (
            <button
              key={sid}
              onClick={() => handleSelectSession(sid)}
              className={`w-full text-left px-3 py-2 rounded text-sm truncate ${
                activeSession === sid
                  ? "bg-gray-700 text-gray-100"
                  : "text-gray-400 hover:bg-gray-800"
              }`}
            >
              {sid.slice(0, 8)}...
            </button>
          ))}
        </div>
      </aside>

      {/* Chat area */}
      <div className="flex-1 flex flex-col bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {!activeSession && (
            <div className="flex items-center justify-center h-full text-gray-500 text-sm">
              Create a new chat session to get started
            </div>
          )}

          {activeSession && messages.length === 0 && (
            <div className="flex items-center justify-center h-full text-gray-500 text-sm">
              Ask a question to start the conversation
            </div>
          )}

          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-200"
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>

                {msg.sql && (
                  <div className="mt-2">
                    <button
                      onClick={() => {
                        setExpandedMsg(expandedMsg === idx ? null : idx);
                        if (!(idx in viewModes)) {
                          setViewModes((prev) => ({ ...prev, [idx]: "table" }));
                        }
                      }}
                      className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                    >
                      <span
                        className={`transform transition-transform ${
                          expandedMsg === idx ? "rotate-90" : ""
                        }`}
                      >
                        &#9654;
                      </span>
                      Show Query & Data
                    </button>

                    {expandedMsg === idx && msg.result && (
                      <div className="mt-2 space-y-2">
                        <pre className="bg-gray-950 rounded p-2 text-xs text-gray-400 overflow-x-auto">
                          {msg.sql}
                        </pre>
                        <div className="flex items-center justify-between">
                          <p className="text-xs text-gray-500">
                            {msg.result.row_count} rows in {msg.result.execution_time_ms}ms
                          </p>
                          <div className="flex gap-1">
                            <button
                              onClick={() =>
                                setViewModes((prev) => ({ ...prev, [idx]: "table" }))
                              }
                              className={`px-2 py-0.5 rounded text-xs ${
                                viewModes[idx] === "table" ? "bg-gray-600" : "bg-gray-700"
                              }`}
                            >
                              Table
                            </button>
                            <button
                              onClick={() =>
                                setViewModes((prev) => ({ ...prev, [idx]: "chart" }))
                              }
                              className={`px-2 py-0.5 rounded text-xs ${
                                viewModes[idx] === "chart" ? "bg-gray-600" : "bg-gray-700"
                              }`}
                            >
                              Chart
                            </button>
                          </div>
                        </div>
                        {viewModes[idx] === "table" ? (
                          <DataTable columns={msg.result.columns} rows={msg.result.rows} />
                        ) : (
                          <ChartView columns={msg.result.columns} rows={msg.result.rows} />
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 rounded-xl px-4 py-3">
                <div className="flex items-center gap-2 text-gray-400 text-sm">
                  <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full" />
                  Thinking...
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Error */}
        {error && (
          <div className="mx-4 mb-2 bg-red-900/30 border border-red-800 rounded px-3 py-2">
            <p className="text-red-400 text-xs">{error}</p>
          </div>
        )}

        {/* Input */}
        {activeSession && (
          <div className="p-4 border-t border-gray-800">
            <div className="flex gap-2">
              <input
                className="flex-1 px-4 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 text-sm"
                placeholder="Ask a question..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                disabled={loading}
              />
              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-sm font-medium"
              >
                Send
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
