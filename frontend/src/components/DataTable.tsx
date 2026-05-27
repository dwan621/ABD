interface Props {
  columns: string[];
  rows: any[][];
}

export default function DataTable({ columns, rows }: Props) {
  return (
    <div className="overflow-auto max-h-96 border border-gray-700 rounded">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-800">
            {columns.map((col) => (
              <th key={col} className="px-3 py-2 text-left font-medium text-gray-300">{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-gray-800 hover:bg-gray-800/50">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-1.5 text-gray-400">
                  {cell === null ? <span className="text-gray-600">NULL</span> : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
