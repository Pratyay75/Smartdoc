// src/components/Sidebar.js
import React, { useEffect, useRef, useState } from "react";
import "./Sidebar.css";
import { FiMenu, FiFileText, FiBarChart2, FiHome, FiChevronDown, FiChevronRight } from "react-icons/fi";

function Sidebar({ onNavigate, sidebarOpen, setSidebarOpen }) {
  const sidebarRef = useRef(null);
  const [classifyOpen, setClassifyOpen] = useState(true);

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
          <div className="sidebar-option" onClick={() => onNavigate("analytics")}>
            <FiBarChart2 /> <span>Data Analytics</span>
          </div>
          <div className="sidebar-option" onClick={() => onNavigate("compare")}>
            <FiBarChart2 /> <span>Compare PDF's</span>
          </div>
          <div className="sidebar-option" onClick={() => onNavigate("multi-doc-chat")}>
            <FiFileText /> <span>Multi-Doc Processing</span>
          </div>

          {/* Classify group */}
          <div
            className="sidebar-option"
            onClick={() => setClassifyOpen((v) => !v)}
            style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <FiBarChart2 /> <span>Classify Docs</span>
            </span>
            {classifyOpen ? <FiChevronDown /> : <FiChevronRight />}
          </div>

          {classifyOpen && (
            <>
              <div
                className="sidebar-option"
                style={{ paddingLeft: 28, fontSize: 14 }}
                onClick={() => onNavigate("classify-route")}
              >
                <FiFileText /> <span>Classify & Route</span>
              </div>
              <div
                className="sidebar-option"
                style={{ paddingLeft: 28, fontSize: 14 }}
                onClick={() => onNavigate("classify-manage")}
              >
                <FiFileText /> <span>Update / Add Categories</span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default Sidebar;
