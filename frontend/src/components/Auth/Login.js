import React, { useState } from "react";

function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const login = async () => {
    if (!email || !password) {
      console.warn("⚠️ Please enter both email and password");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (data.token) {
        const displayName = data.name || email.split("@")[0];

        localStorage.setItem("token", data.token);
        localStorage.setItem("name", displayName);

        console.log(`✅ Welcome, ${displayName}`);
        onLogin(data.token);
      } else {
        console.warn("⚠️ Login failed:", data.error || "Unknown error");
      }
    } catch (error) {
      console.error("❌ Error connecting to server:", error);
    }

    setLoading(false);
  };

  return (
    <div className="auth-form">
      <input
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button onClick={login} disabled={loading}>
        {loading ? "Logging in..." : "Login"}
      </button>
    </div>
  );
}

export default Login;
