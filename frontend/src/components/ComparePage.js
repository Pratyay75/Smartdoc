import React, { useState } from "react";
import "./ComparePage.css";

function ComparePage() {
  const [file1, setFile1] = useState(null);
  const [file2, setFile2] = useState(null);
  const [outputHtml, setOutputHtml] = useState("");
  const [loading, setLoading] = useState(false);

  const [showSame, setShowSame] = useState(true);
  const [showNew, setShowNew] = useState(true);
  const [showRemoved, setShowRemoved] = useState(true);

  const handleCompare = async () => {
    if (!file1 || !file2) {
      alert("Upload both PDFs");
      return;
    }

    const formData = new FormData();
    formData.append("pdf1", file1);
    formData.append("pdf2", file2);

    setLoading(true);
    try {
      const res = await fetch("/compare", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setOutputHtml(data?.html_result || "No result");
    } catch (err) {
      console.error(err);
      setOutputHtml("Error comparing PDFs");
    }
    setLoading(false);
  };

  return (
    <div className="pdf-extractor">
      <div className="left-panel">
        <h3>Compare PDFs</h3>
        <div className="field">
          <label>Upload PDF 1</label>
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile1(e.target.files[0])}
          />
        </div>

        <div className="field">
          <label>Upload PDF 2</label>
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile2(e.target.files[0])}
          />
        </div>

        <div className="button-group">
          <button onClick={handleCompare} disabled={!file1 || !file2 || loading}>
            {loading ? "Comparing..." : "Compare"}
          </button>
        </div>
      </div>

      <div className="right-panel">
        {/* --- legend --- */}
<div className="legend">
  <label className="legend-item legend-same">
    <input
      type="checkbox"
      checked={showSame}
      onChange={() => setShowSame(!showSame)}
    />
    
    <span className="legend-label">Same text</span>
  </label>

  <label className="legend-item legend-new">
    <input
      type="checkbox"
      checked={showNew}
      onChange={() => setShowNew(!showNew)}
    />
   
    <span className="legend-label">New text</span>
  </label>

  <label className="legend-item legend-removed">
    <input
      type="checkbox"
      checked={showRemoved}
      onChange={() => setShowRemoved(!showRemoved)}
    />
  
    <span className="legend-label">Removed text</span>
  </label>
</div>

        <div
          className={`output-viewer 
            ${showSame ? "show-same" : "hide-same"} 
            ${showNew ? "show-new" : "hide-new"} 
            ${showRemoved ? "show-removed" : "hide-removed"}`}
          dangerouslySetInnerHTML={{ __html: outputHtml }}
        />
      </div>
    </div>
  );
}

export default ComparePage;
