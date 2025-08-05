import React, { useEffect, useRef } from "react";
import "./Sidebar.css";
import { FiMenu, FiFileText, FiBarChart2, FiHome } from "react-icons/fi";

function Sidebar({ onNavigate, sidebarOpen, setSidebarOpen }) {
  const sidebarRef = useRef(null);

  const handleToggle = () => {
    setSidebarOpen(!sidebarOpen);
  };

  // Close sidebar on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        sidebarOpen &&
        sidebarRef.current &&
        !sidebarRef.current.contains(e.target) &&
        !e.target.closest(".menu-btn")
      ) {
        setSidebarOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [sidebarOpen, setSidebarOpen]);

  return (
    <div className="sidebar-container">
      <button className="menu-btn" onClick={handleToggle}>
        <FiMenu size={24} />
      </button>

      {sidebarOpen && (
        <div className="sidebar" ref={sidebarRef}>
          <div className="sidebar-option" onClick={() => onNavigate("home")}>
            <FiHome /> <span>Home</span>
          </div>
          <div className="sidebar-option" onClick={() => onNavigate("pdf")}>
            <FiFileText /> <span>PDF Extractor</span>
          </div>
          <div
            className="sidebar-option"
            onClick={() => onNavigate("analytics")}
          >
            <FiBarChart2 /> <span>Data Analytics</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default Sidebar;
