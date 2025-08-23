// src/components/CategoryManager.js
import React, { useEffect, useState } from "react";
import "./CategoryManager.css";

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

export default function CategoryManager() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);

  // Add form
  const [newName, setNewName] = useState("");
  const [newKeywords, setNewKeywords] = useState("");
  const [newReceiver, setNewReceiver] = useState("");

  // Edit form (inline)
  const [editNameOriginal, setEditNameOriginal] = useState(null);
  const [editName, setEditName] = useState("");
  const [editKeywords, setEditKeywords] = useState("");
  const [editReceiver, setEditReceiver] = useState("");

  const refresh = async () => {
    try {
      const res = await fetch("http://localhost:5000/get-categories", {
        headers: authHeaders(),
      });
      const data = await res.json();
      if (res.ok) {
        setCategories(Array.isArray(data.categories) ? data.categories : []);
      } else {
        setCategories([]);
      }
    } catch (e) {
      console.error(e);
      setCategories([]);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const clearAddForm = () => {
    setNewName("");
    setNewKeywords("");
    setNewReceiver("");
  };

  const handleAdd = async () => {
    const nameTrim = newName.trim();
    const receiverTrim = newReceiver.trim();

    if (!nameTrim || !newKeywords.trim() || !receiverTrim) {
      return alert("Please fill category name, keywords and receiver email.");
    }

    // Check duplicate
    const existingNames = categories.map((c) => (c.name || "").toLowerCase());
    if (existingNames.includes(nameTrim.toLowerCase())) {
      return alert("Category name must be unique.");
    }

    // Check email format
    if (!isValidEmail(receiverTrim)) {
      return alert("Please enter a valid receiver email.");
    }

    setLoading(true);
    try {
      const res = await fetch("/update-categories", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          category: nameTrim,
          keywords: newKeywords
            .split(",")
            .map((k) => k.trim())
            .filter(Boolean),
          receiver_email: receiverTrim,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to add category");

      await refresh();
      clearAddForm();
      alert("Category added!");
    } catch (e) {
      console.error(e);
      alert(e.message || "Error adding category");
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (cat) => {
    setEditNameOriginal(cat.name);
    setEditName(cat.name);
    setEditKeywords((cat.keywords || []).join(", "));
    setEditReceiver(cat.receiver_email || "");
  };

  const cancelEdit = () => {
    setEditNameOriginal(null);
    setEditName("");
    setEditKeywords("");
    setEditReceiver("");
  };

  const handleEdit = async () => {
    if (!editNameOriginal) return;
    const nameTrim = editName.trim();
    const receiverTrim = editReceiver.trim();

    if (!nameTrim || !receiverTrim) {
      return alert("Please fill category name and receiver email.");
    }

    // Check duplicate (exclude the category we are editing)
    const existingNames = categories
      .filter((c) => c.name !== editNameOriginal)
      .map((c) => (c.name || "").toLowerCase());
    if (existingNames.includes(nameTrim.toLowerCase())) {
      return alert("Category name must be unique.");
    }

    // Check email format
    if (!isValidEmail(receiverTrim)) {
      return alert("Please enter a valid receiver email.");
    }

    setLoading(true);
    try {
      const res = await fetch("/edit-category", {
        method: "PUT",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          name: editNameOriginal,
          update: {
            name: nameTrim,
            keywords: editKeywords
              .split(",")
              .map((k) => k.trim())
              .filter(Boolean),
            receiver_email: receiverTrim,
          },
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Edit failed");

      await refresh();
      cancelEdit();
      alert("Category updated!");
    } catch (e) {
      console.error(e);
      alert(e.message || "Error editing category");
    } finally {
      setLoading(false);
    }
  };
const handleDelete = async (name) => {
  if (!window.confirm(`Are you sure you want to delete category "${name}"?`)) return;
  try {
    const res = await fetch("/delete-category", {
      method: "DELETE",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ name }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error || "Delete failed");

    await refresh();
    alert("Category deleted!");
  } catch (e) {
    console.error(e);
    alert(e.message || "Error deleting category");
  }
};

  return (
    <div className="category-layout">
  <div className="category-left">
        <h2>Update / Add Categories</h2>

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <input
            type="text"
            placeholder="Category name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <input
            type="text"
            placeholder="Keywords (comma separated)"
            value={newKeywords}
            onChange={(e) => setNewKeywords(e.target.value)}
          />
          <input
            type="email"
            placeholder="Receiver email"
            value={newReceiver}
            onChange={(e) => setNewReceiver(e.target.value)}
          />

          <button className="upload-btn" onClick={handleAdd} disabled={loading}>
            {loading ? "Saving…" : "Add Category"}
          </button>
        </div>

        <p style={{ color: "#777", fontSize: 12, marginTop: 12 }}>
          NOTE: The email you set here will auto-fill in the “Classify & Route” page when that category is selected.
        </p>
      </div>

      {/* Right: List + Edit */}
      <div className="category-right">
        <h2 className="center-heading">Your Categories</h2>

        <table>
          <thead>
  <tr>
    <th style={{ width: "20%" }}>Name</th>
    <th style={{ width: "40%" }}>Keywords</th>
    <th style={{ width: "25%" }}>Receiver Email</th>
    <th style={{ width: "15%" }}>Action</th>
  </tr>
</thead>

          <tbody>
            {categories.length === 0 ? (
              <tr>
                <td colSpan="4" style={{ textAlign: "center", color: "#777" }}>
                  No categories yet
                </td>
              </tr>
            ) : (
              categories.map((cat) => (
                <tr key={cat.name}>
                  <td>{cat.name}</td>
                  <td>{(cat.keywords || []).join(", ")}</td>
                  <td>{cat.receiver_email || ""}</td>
                 <td style={{ display: "flex", justifyContent: "center", gap: "10px" }}>
  {/* Delete icon */}
  <button
    className="remove-btn"
    title="Delete Category"
    onClick={() => handleDelete(cat.name)}
  >
    🗑️
  </button>

  {/* 3-dots menu for edit */}
  <button
    className="dots-btn"
    title="More Options"
    onClick={() => startEdit(cat)}
  >
    ⋮
  </button>
</td>

                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Inline editor */}
        {editNameOriginal && (
          <div className="modal-overlay" style={{ background: "transparent" }}>
            <div className="modal" style={{ maxWidth: 620 }}>
              <h3>Edit Category</h3>
              <input
                type="text"
                placeholder="Category name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
              <input
                type="text"
                placeholder="Keywords (comma separated)"
                value={editKeywords}
                onChange={(e) => setEditKeywords(e.target.value)}
              />
              <input
                type="email"
                placeholder="Receiver Email"
                value={editReceiver}
                onChange={(e) => setEditReceiver(e.target.value)}
              />
              <div className="modal-actions">
                <button onClick={handleEdit} disabled={loading}>
                  {loading ? "Updating…" : "Update"}
                </button>
                <button onClick={cancelEdit}>Cancel</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
