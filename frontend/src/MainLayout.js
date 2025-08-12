import React, { useState } from "react";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import PDFExtractor from "./components/PDFExtractor";
import Analytics from "./components/Analytics";
import ComparePage from "./components/ComparePage";
import "./App.css";
import "./HomePage.css"; // 👈 CSS for home page styling
import MultiDocVoiceChat from "./components/MultiDocVoiceChat";

function MainLayout({ onLogout }) {
  const [activePage, setActivePage] = useState("home");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("name");
    onLogout();
  };

  return (
    <div className="layout">
      <Sidebar
        onNavigate={setActivePage}
        onLogout={handleLogout}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
      />

      <div className={`main-content ${sidebarOpen ? "shifted" : ""}`}>
        <Header onLogout={handleLogout} />
        <div className="page-content">
          {activePage === "home" && (
            <div className="home-container">
              <section className="hero">
                <h1>SmartDoc AI</h1>
                <p className="tagline">Extract What Matters. Validate. Explore Insights.</p>

              </section>

              <div className="side-by-side-sections">
  <section className="section">
    <h2>What It Does</h2>
    <ul>
      <li>Extracts only the required data from long documents.</li>
      <li>Humans review the extracted data and save it for downstream systems to use.</li>
      <li>Lets you chat with the document to ask questions or explore more.</li>
      <li>Tracks accuracy, field-level confidence, and trends in a simple dashboard.</li>
    </ul>
  </section>

  <section className="section">
    <h2>Use Cases</h2>
    <ul>
      <li><strong>Insurance</strong> — Pull out policy details like dates, coverage, and other details.</li>
      <li><strong>Healthcare</strong> — Extract patient info, diagnosis, and visit summaries.</li>
      <li><strong>Finance</strong> — Parse KYC docs like Aadhaar, PAN, and address proofs.</li>
      <li><strong>Legal</strong> — Capture key clauses, party names, and timelines from contracts.</li>
      <li><strong>And more</strong> — Pharma reports, shipping docs, academic records, etc.</li>
    </ul>
  </section>
</div>

            </div>
          )}

          {activePage === "pdf" && <PDFExtractor />}
          {activePage === "analytics" && <Analytics />}
          {activePage === "compare" && <ComparePage />}
          {activePage === "multi-doc-chat" && <MultiDocVoiceChat />}
        </div>
      </div>
    </div>
  );
}

export default MainLayout;
