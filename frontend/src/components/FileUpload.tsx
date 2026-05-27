import { useCallback, useState } from "react";

interface Props {
  onUpload: (file: File) => void;
  accept?: string;
}

export default function FileUpload({ onUpload, accept = ".csv,.xlsx" }: Props) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onUpload(file);
    },
    [onUpload]
  );

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
        dragging ? "border-blue-400 bg-blue-900/20" : "border-gray-600 hover:border-gray-400"
      }`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => document.getElementById("file-input")?.click()}
    >
      <input
        id="file-input"
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file);
        }}
      />
      <p className="text-gray-400">Drop CSV/Excel file here or click to browse</p>
    </div>
  );
}
