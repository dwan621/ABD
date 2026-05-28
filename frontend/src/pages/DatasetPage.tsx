import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";

interface Dataset {
  id: string;
  name: string;
  table_name: string;
  row_count: number;
  created_at: string;
}

export default function DatasetPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/datasets/").then((res) => setDatasets(res.data));
  }, []);

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Datasets</h2>
      <div className="space-y-2">
        {datasets.map((ds) => (
          <div
            key={ds.id}
            onClick={() => navigate(`/datasets/${ds.id}`)}
            className="bg-gray-900 p-4 rounded border border-gray-800 flex items-center justify-between cursor-pointer hover:bg-gray-800/50 transition-colors"
          >
            <div>
              <p className="font-medium">{ds.name}</p>
              <p className="text-sm text-gray-400">
                Table: {ds.table_name} | Rows: {ds.row_count.toLocaleString()} |{" "}
                {new Date(ds.created_at).toLocaleDateString()}
              </p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/datasets/${ds.id}/insights`);
              }}
              className="px-4 py-1.5 text-sm bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 rounded-lg"
            >
              Insights
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
