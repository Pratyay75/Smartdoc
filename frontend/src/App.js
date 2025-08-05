import React, { useState, useEffect } from "react";
import AuthPage from "./components/Auth/AuthPage";
import MainLayout from "./MainLayout";

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));

  useEffect(() => {
    if (token) {
      const timeout = setTimeout(() => {
        localStorage.removeItem("token");
        setToken(null);
      }, 200 * 60 * 1000); // 25 minutes
      return () => clearTimeout(timeout);
    }
  }, [token]);

  return (
    <div className="App">
      {!token ? (
        <AuthPage onLogin={setToken} />
      ) : (
        <MainLayout onLogout={() => setToken(null)} />
      )}
    </div>
  );
}

export default App;
