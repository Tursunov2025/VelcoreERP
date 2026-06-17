import { useState } from "react";
import LoginPage from "./pages/LoginPage";
import TrackingPage from "./pages/TrackingPage";

export default function App() {
  const [user, setUser] = useState(null);

  if (!user) {
    return <LoginPage onLoggedIn={setUser} />;
  }

  return <TrackingPage user={user} onLogout={() => setUser(null)} />;
}
