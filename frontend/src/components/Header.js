import React, { useEffect, useState } from "react";
import { FiUser, FiLogOut } from "react-icons/fi";
import "./Header.css";

function Header({ onLogout }) {
  const [userName, setUserName] = useState("");

  useEffect(() => {
    const name = localStorage.getItem("name");
    setUserName(name || "User");
  }, []);

  return (
    <header className="header">
      <div className="menu-and-title">
        <div className="title-container">
          <h1>SmartDoc AI</h1>
          <p className="subtitle">Extract What Matters. Validate. Explore Insights.</p>
        </div>
      </div>
      <div className="user-section">
        <FiUser size={20} />
        <span className="username">{userName}</span>
        <button className="logout-btn" onClick={onLogout} title="Logout">
          <FiLogOut size={18} />
        </button>
      </div>
    </header>
  );
}

export default Header;
