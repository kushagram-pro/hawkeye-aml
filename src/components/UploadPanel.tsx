import { useRef, useState } from "react";
import { uploadScenario } from "../services/api";

interface UploadPanelProps {
  onUploaded: (scenarioId: string) => void;
  disabled?: boolean;
}

export function UploadPanel({ onUploaded, disabled }: UploadPanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const { scenarioId } = await uploadScenario(file, name);
      setName("");
      onUploaded(scenarioId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="upload-panel">
      <div>
        <span className="metric-label">Bring your own data</span>
        <p className="helper-text">Upload a .csv or .json file with from_account, to_account, amount, timestamp columns.</p>
      </div>
      <div className="upload-controls">
        <input
          type="text"
          className="upload-name-input"
          placeholder="Name this dataset (optional)"
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={disabled || uploading}
          maxLength={80}
        />
        <button
          type="button"
          className="ghost-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || uploading}
        >
          {uploading ? "Uploading..." : "Upload transactions"}
        </button>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.json"
        onChange={handleFileChange}
        style={{ display: "none" }}
      />
      {error ? <p className="upload-error">{error}</p> : null}
    </div>
  );
}
