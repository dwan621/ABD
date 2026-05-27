import { useEffect, useState } from "react";
import api from "../api/client";
import FileUpload from "../components/FileUpload";

interface Datasource {
  id: string;
  name: string;
  type: string;
  created_at: string;
}

export default function DatasourcePage() {
  const [datasources, setDatasources] = useState<Datasource[]>([]);
  const [name, setName] = useState("");

  const fetchAll = async () => {
    const res = await api.get("/datasources/");
    setDatasources(res.data);
  };

  useEffect(() => { fetchAll(); }, []);

  const handleCreate = async () => {
    if (!name.trim()) return;
    await api.post("/datasources/", { name, type: "csv", config_json: {} });
    setName("");
    fetchAll();
  };

  const handleUpload = async (file: File) => {
    const dsName = file.name.replace(/\.[^.]+$/, "");
    const res = await api.post("/datasources/", { name: dsName, type: "csv", config_json: { filename: file.name } });
    const formData = new FormData();
    formData.append("file", file);
    await api.post(`/datasets/upload?datasource_id=${res.data.id}`, formData);
    fetchAll();
  };

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Data Sources</h2>

      <div className="flex gap-2 mb-6">
        <input
          className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded text-gray-100"
          placeholder="Datasource name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button onClick={handleCreate} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded">
          Create
        </button>
      </div>

      <FileUpload onUpload={handleUpload} />

      <div className="mt-6 space-y-2">
        {datasources.map((ds) => (
          <div key={ds.id} className="bg-gray-900 p-4 rounded border border-gray-800 flex justify-between">
            <div>
              <p className="font-medium">{ds.name}</p>
              <p className="text-sm text-gray-400">{ds.type} — {new Date(ds.created_at).toLocaleDateString()}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
