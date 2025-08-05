import React, { useState } from "react";

function Signup({ onToggle }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const signup = async () => {
    if (!name || !email || !password) {
      console.warn("⚠️ Please fill all fields");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });

      const data = await res.json();

      if (data.message) {
        console.log("✅ Signup successful. Please login.");
        onToggle(); // Switch to login form
      } else {
        console.warn("⚠️ Signup failed:", data.error || "Unknown error");
      }
    } catch (error) {
      console.error("❌ Error connecting to server:", error);
    }

    setLoading(false);
  };

  return (
    <div className="auth-form">
      <input
        placeholder="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
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
      <button onClick={signup} disabled={loading}>
        {loading ? "Signing up..." : "Signup"}
      </button>
    </div>
  );
}

export default Signup;
