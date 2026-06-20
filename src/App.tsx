import { useState } from "react";
import { Dashboard } from "./Dashboard";
import { LoginPage } from "./components/LoginPage";
import { getToken } from "./services/api";

export default function App() {
  const [authed, setAuthed] = useState(() => Boolean(getToken()));

  if (!authed) {
    return <LoginPage onLogin={() => setAuthed(true)} />;
  }

  return <Dashboard onLogout={() => setAuthed(false)} />;
}
