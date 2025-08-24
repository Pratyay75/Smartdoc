// src/components/ClassifyAndRoute.js
import React, { useState, useEffect } from "react";
import "./ClassifyAndRoute.css";
import { FiTrash2 } from "react-icons/fi";

// Regex for email validation
const EMAIL_REGEX = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
const isValidEmail = (s) => EMAIL_REGEX.test((s || "").trim());

// Helper: auth header from localStorage token
function authHeaders(extra = {}) {
  const token = localStorage.getItem("token");
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

export default function ClassifyAndRoute() {
  const [files, setFiles] = useState([]);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);

  const [editingIntentIdx, setEditingIntentIdx] = useState(null);
  const [categoriesFull, setCategoriesFull] = useState([]);
  const [categories, setCategories] = useState(["Other"]);

  // track send status: { [rowIndex]: "sending" | "sent" | "failed" }
  const [sendStatus, setSendStatus] = useState({});

  // ---------- Load categories ----------
  const refreshCategories = async () => {
    try {
      const res = await fetch("/get-categories", {
        headers: authHeaders(),
      });
      const data = await res.json();
      if (res.ok && Array.isArray(data.categories)) {
        setCategoriesFull(data.categories);
        setCategories(["Other", ...data.categories.map((c) => c.name)]);
      } else {
        setCategoriesFull([]);
        setCategories(["Other"]);
      }
    } catch (e) {
      console.error("Failed to load categories", e);
      setCategoriesFull([]);
      setCategories(["Other"]);
    }
  };

  useEffect(() => {
    refreshCategories();
  }, []);

  // ---------- File handling ----------
  const handleFileChange = (e) => setFiles(Array.from(e.target.files || []));
  const removeRow = (idx) => setRows((prev) => prev.filter((_, i) => i !== idx));

  const findEmailForCategory = (catName) => {
    const m = categoriesFull.find((c) => (c.name || "") === (catName || ""));
    return m?.receiver_email || "";
  };

  const handleCategoryChange = (idx, newCategory) => {
    setRows((prev) =>
      prev.map((row, i) =>
        i === idx
          ? {
              ...row,
              category: newCategory,
              toEmail:
                newCategory === "Other"
                  ? row.toEmail
                  : findEmailForCategory(newCategory),
            }
          : row
      )
    );
  };

  const handleIntentChange = (idx, newIntent) => {
    setRows((prev) =>
      prev.map((row, i) => (i === idx ? { ...row, intent: newIntent } : row))
    );
  };

  // ---------- Upload & classify ----------
  const handleUploadAndClassify = async () => {
    if (!files.length || loading) return;
    setLoading(true);

    const placeholders = files.map((f) => ({
      name: f.name,
      status: "Processing…",
      category: "Other",
      intent: "",
      toEmail: "",
    }));
    setRows((prev) => [...placeholders, ...prev]);

    try {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));

      const res = await fetch("/classify-docs", {
        method: "POST",
        headers: authHeaders(),
        body: form,
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data?.error || "Server error");
      }

      setRows((prev) => {
        const updated = [...prev];
        for (let i = 0; i < files.length; i++) {
          const result = data.results[i] || {};
          const effectiveCat = result.category || "Other";
          const defaultEmail =
            effectiveCat === "Other" ? "" : findEmailForCategory(effectiveCat);

          updated[i] = {
            name: result.name || placeholders[i].name,
            status: result.status || "Done",
            category: effectiveCat,
            intent: result.intent || "",
            toEmail: defaultEmail,
          };
        }
        return updated;
      });
    } catch (e) {
      console.error(e);
      setRows((prev) =>
        prev.map((r, idx) =>
          idx < files.length ? { ...r, status: "Failed" } : r
        )
      );
    } finally {
      setFiles([]);
      setLoading(false);
    }
  };

  // ---------- Send email ----------
  const handleSendEmail = async (idx) => {
    const row = rows[idx];
    if (!row) return;
    const to = (row.toEmail || "").trim();

    if (!isValidEmail(to)) {
      setSendStatus((prev) => ({ ...prev, [idx]: "failed" }));
      return;
    }

    setSendStatus((prev) => ({ ...prev, [idx]: "sending" }));
    try {
      const res = await fetch("/send-classification", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          name: row.name,
          category: row.category || "Other",
          intent: row.intent || "",
          to_email: to,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Send failed");

      setSendStatus((prev) => ({ ...prev, [idx]: "sent" }));
    } catch (e) {
      console.error(e);
      setSendStatus((prev) => ({ ...prev, [idx]: "failed" }));
    }
  };

  return (
    <div className="route-layout">
  <div className="route-left">


        <h2>Classify & Route</h2>
        <input
          type="file"
          multiple
          onChange={handleFileChange}
          accept=".pdf,.docx,.txt"
        />
        <button
          className="upload-btn"
          onClick={handleUploadAndClassify}
          disabled={!files.length || loading}
        >
          {loading ? "Processing…" : "Upload & Classify"}
        </button>

        <p style={{ color: "#777", fontSize: 12, marginTop: 12 }}>
          Tip: change the category from the table to auto-fill recipient based on your saved settings.
        </p>
      </div>

      {/* Right Panel */}
      <div className="route-right">
        <h2 className="center-heading">Results</h2>
        <table>
          <thead>
  <tr>
    <th style={{ width: "15%" }}>Name</th>
    <th style={{ width: "8%" }}>Status</th>
    <th style={{ width: "15%" }}>Category</th>
    <th style={{ width: "30%" }}>Intent</th>
    <th style={{ width: "15%" }}>To Email</th>
    <th style={{ width: "12%" }}>Action</th>
  </tr>
</thead>

          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: "center", color: "#777" }}>
                  No files processed yet
                </td>
              </tr>
            ) : (
              rows.map((row, idx) => (
                <tr key={idx}>
                  <td>{row.name}</td>
                  <td>
                    {row.status === "Processing…" ? (
                      <span className="spinner" />
                    ) : (
                      row.status
                    )}
                  </td>
                  <td>
                    <select
                      value={row.category || "Other"}
                      onChange={(e) => handleCategoryChange(idx, e.target.value)}
                      className="category-select"
                    >
                      {categories.map((cat, i) => (
                        <option key={i} value={cat}>
                          {cat}
                        </option>
                      ))}
                    </select>
                  </td>

                  {/* Intent */}
                  <td
                    className="intent-cell"
                    onClick={() => setEditingIntentIdx(idx)}
                  >
                    {editingIntentIdx === idx ? (
                      <textarea
                        autoFocus
                        className="inline-intent-input"
                        value={row.intent}
                        onChange={(e) => handleIntentChange(idx, e.target.value)}
                        onBlur={() => setEditingIntentIdx(null)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !e.shiftKey)
                            setEditingIntentIdx(null);
                        }}
                        rows={3}
                      />
                    ) : row.intent ? (
                      row.intent
                    ) : (
                      <span style={{ color: "#aaa" }}>Click to edit</span>
                    )}
                  </td>

                  {/* To Email */}
                  <td style={{ minWidth: 220, color: "#555" }}>
                    {row.toEmail || "—"}
                  </td>

                  <td>
  <div className="action-actions">
    <button
      className={`send-btn ${
        sendStatus[idx] === "sent"
          ? "sent-btn"
          : sendStatus[idx] === "failed"
          ? "failed-btn"
          : ""
      }`}
      onClick={() => handleSendEmail(idx)}
      disabled={
        !isValidEmail(row.toEmail || "") ||
        row.status !== "Done" ||
        sendStatus[idx] === "sending"
      }
    >
      {sendStatus[idx] === "sending" ? (
        <span className="spinner" />
      ) : sendStatus[idx] === "sent" ? (
        "Sent"
      ) : sendStatus[idx] === "failed" ? (
        "Failed"
      ) : (
        "Send"
      )}
    </button>
    <button
      className="remove-btn"
      onClick={() => removeRow(idx)}
      title="Remove row"
    >
      <FiTrash2 />
    </button>
  </div>
</td>

                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
