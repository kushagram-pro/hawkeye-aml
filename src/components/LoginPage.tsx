import { useState } from "react";
import { login } from "../services/api";

interface LoginPageProps {
  onLogin: () => void;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login(username, password);
      onLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-shell">
      <div className="backdrop backdrop-left" />
      <div className="backdrop backdrop-right" />

      <form className="panel login-card" onSubmit={handleSubmit}>
        <span className="hero-kicker">HawkEye AML</span>
        <h1 className="login-title">Sign in to the investigation dashboard</h1>
        <p className="helper-text">Use your analyst credentials to access live scenarios and investigation runs.</p>

        <label className="login-field">
          <span className="metric-label">Username</span>
          <input
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
          />
        </label>

        <label className="login-field">
          <span className="metric-label">Password</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {error ? <p className="upload-error">{error}</p> : null}

        <button type="submit" className="run-button login-submit" disabled={submitting}>
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
