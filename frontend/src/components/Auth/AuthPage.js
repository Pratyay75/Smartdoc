import React, { useState } from "react";
import Login from "./Login";
import Signup from "./Signup";
import "./Auth.css";

function AuthPage({ onLogin }) {
  const [isLogin, setIsLogin] = useState(true);

  const toggleForm = () => setIsLogin(!isLogin);

  return (
    <div className="auth-page">
      <div className="auth-container glass">
        <h2>{isLogin ? "Login" : "Signup"}</h2>
        {isLogin ? (
          <Login onLogin={onLogin} />
        ) : (
          <Signup onToggle={toggleForm} />
        )}
        <p className="toggle-text">
          {isLogin ? "Don't have an account?" : "Already have an account?"}
          <span onClick={toggleForm}>
            {isLogin ? " Signup" : " Login"}
          </span>
        </p>
      </div>
    </div>
  );
}

export default AuthPage;
