import { useEffect, useState } from "react";
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

  useEffect(() => {
    api.get("/datasets/").then((res) => setDatasets(res.data));
  }, []);

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Datasets</h2>
      <div className="space-y-2">
        {datasets.map((ds) => (
          <div key={ds.id} className="bg-gray-900 p-4 rounded border border-gray-800">
            <p className="font-medium">{ds.name}</p>
            <p className="text-sm text-gray-400">
              Table: {ds.table_name} | Rows: {ds.row_count.toLocaleString()} |{" "}
              {new Date(ds.created_at).toLocaleDateString()}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
