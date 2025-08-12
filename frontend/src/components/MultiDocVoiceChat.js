import React, { useState } from "react";
import "./MultiDocVoiceChat.css";
import ChatBot from "./Chatbot"; // reusing your chatbot
import { FiTrash2 } from "react-icons/fi";
import { useEffect } from "react";


export default function MultiDocVoiceChat() {
  const [files, setFiles] = useState([]);
  const [uploadedDocs, setUploadedDocs] = useState([]);



useEffect(() => {
  const handleBeforeUnload = async () => {
    if (uploadedDocs.length > 0) {
      const blobNames = uploadedDocs.map(doc => doc.blob_name).filter(Boolean);
      if (blobNames.length > 0) {
        try {
          await fetch("/delete-multiple-blobs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ blob_names: blobNames })
          });
        } catch (err) {
          console.error("Failed to delete blobs on refresh", err);
        }
      }
    }
  };

  window.addEventListener("beforeunload", handleBeforeUnload);
  return () => window.removeEventListener("beforeunload", handleBeforeUnload);
}, [uploadedDocs]);


  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files));
  };

  const handleUpload = async () => {
    if (!files.length) return;

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    // Show immediate placeholders while uploading
    const tempDocs = files.map((file) => ({
      name: file.name,
      date: new Date().toLocaleString(),
      status: "Uploading",
      size: (file.size / 1024).toFixed(1) + " KB",
      processing: true,
    }));
    setUploadedDocs((prev) => [...tempDocs, ...prev]);
    setFiles([]);

    try {
      const res = await fetch("/upload-multi-doc", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (data.documents) {
        // Replace "Processing..." entries with actual backend results
        setUploadedDocs((prev) => {
          const updated = [...prev];
          data.documents.forEach((docData) => {
            const index = updated.findIndex(
              (d) => d.name === docData.name && d.status === "Uploading"
            );
            if (index !== -1) {
              updated[index] = {
  name: docData.name,
  date: docData.date,
  status: docData.status,
  size: docData.size,

  blob_name: docData.blob_name,
  processing: false,
};

            }
          });
          return updated;
        });
      } else {
        console.error("Upload error:", data.error);
      }
    } catch (err) {
      console.error("Upload failed", err);
    }
  };

  const detectType = (filename) => {
    const lower = filename.toLowerCase();
    if (lower.includes("invoice")) return "Invoice";
    if (lower.includes("legal")) return "Legal";
    if (lower.includes("health")) return "Health Insurance";
    return "Other";
  };

 const removeFile = async (index) => {
  const docToRemove = uploadedDocs[index];
  setUploadedDocs((prev) => prev.filter((_, i) => i !== index));

  if (docToRemove?.blob_name) {
    try {
      await fetch("/delete-blob", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blob_name: docToRemove.blob_name })
      });
    } catch (err) {
      console.error("Failed to delete blob", err);
    }
  }
};


  return (
    <div className="multi-doc-layout">
      {/* Left Panel */}
      <div className="left-panel">
        <h2>Upload</h2>
        <input
          type="file"
          multiple
          onChange={handleFileChange}
          accept=".pdf,.docx,.txt"
        />
        <button className="upload-btn" onClick={handleUpload}>
          Upload
        </button>
      </div>

      {/* Right Panel */}
      <div className="right-panel">
        <h2 className="center-heading">Uploaded Files</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Date Uploaded</th>
              <th>Status</th>
              <th>Size</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {uploadedDocs.length === 0 ? (
              <tr>
                <td colSpan="5" style={{ textAlign: "center", color: "#777" }}>
                  No files uploaded yet
                </td>
              </tr>
            ) : (
              uploadedDocs.map((doc, idx) => (
                <tr key={idx}>
                  <td>{doc.name}</td>
                  <td>{doc.date}</td>
                  <td>
                    {doc.processing ? (
                      <span className="spinner"></span>
                    ) : (
                      doc.status
                    )}
                  </td>
                  <td>{doc.size}</td>
                  <td>
                    <button
                      className="remove-btn"
                      onClick={() => removeFile(idx)}
                    >
                      <FiTrash2 />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Floating Chatbot */}
      <div className="chatbot-floating">
        <ChatBot contextType="multi-doc" />
      </div>
    </div>
  );
}