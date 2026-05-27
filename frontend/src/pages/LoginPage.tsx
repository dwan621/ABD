import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await api.post("/auth/login", { username, password });
      localStorage.setItem("token", res.data.access_token);
      navigate("/query");
    } catch {
      setError("Invalid username or password");
    }
  };

  return (
    <div className="flex items-center justify-center h-screen bg-gray-950">
      <form onSubmit={handleSubmit} className="bg-gray-900 p-8 rounded-lg w-96 border border-gray-800">
        <h1 className="text-2xl font-bold text-blue-400 mb-6">ABD Platform</h1>
        {error && <p className="text-red-400 mb-4">{error}</p>}
        <input
          className="w-full px-3 py-2 mb-3 bg-gray-800 border border-gray-700 rounded text-gray-100"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          type="password"
          className="w-full px-3 py-2 mb-4 bg-gray-800 border border-gray-700 rounded text-gray-100"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button type="submit" className="w-full py-2 bg-blue-600 hover:bg-blue-700 rounded font-medium">
          Login
        </button>
      </form>
    </div>
  );
}
