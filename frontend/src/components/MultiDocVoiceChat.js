import React, { useState, useEffect, useRef } from "react";
import "./MultiDocVoiceChat.css";
import { FiTrash2 } from "react-icons/fi";

export default function MultiDocVoiceChat() {
  const [files, setFiles] = useState([]);
  const [uploadedDocs, setUploadedDocs] = useState([]);

  // --- Chatbot state ---
  const [showChat, setShowChat] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hi! Ask me anything about the PDFs you’ve uploaded on the right.",
    },
  ]);

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [chatSize, setChatSize] = useState({ width: 400, height: 500 });
  const resizingRef = useRef(false);
  const chatBodyRef = useRef(null);

  // derive currently uploaded blob names
  const currentBlobNames = uploadedDocs
    .map((d) => d.blob_name)
    .filter(Boolean);

  const sendMessage = async () => {
    const q = chatInput.trim();
    if (!q || chatLoading) return;

    // Add user message immediately
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setChatInput("");
    setChatLoading(true);

    try {
      const res = await fetch("/chat-multidoc", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, blob_names: currentBlobNames }),
      });
      const data = await res.json();

      if (data?.answer) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text: data.answer,
            sources: data.sources || [],
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text:
              data?.error ||
              "Sorry, I couldn't find that in the current documents.",
          },
        ]);
      }
    } catch (err) {
      console.error("Chat error", err);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Server error while chatting." },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const onKeyDownChat = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ✅ Auto-scroll to latest chat
  useEffect(() => {
    if (chatBodyRef.current) {
      chatBodyRef.current.scrollTop = chatBodyRef.current.scrollHeight;
    }
  }, [messages, chatLoading]);

  useEffect(() => {
    const handleBeforeUnload = async () => {
      if (uploadedDocs.length > 0) {
        const blobNames = uploadedDocs
          .map((doc) => doc.blob_name)
          .filter(Boolean);
        if (blobNames.length > 0) {
          try {
            await fetch("/delete-multiple-blobs", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ blob_names: blobNames }),
            });
          } catch (err) {
            console.error("Failed to delete blobs on refresh", err);
          }
        }
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () =>
      window.removeEventListener("beforeunload", handleBeforeUnload);
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
        // Update placeholder rows with real backend results
        setUploadedDocs((prev) => {
          const updated = [...prev];
          data.documents.forEach((docData) => {
            const index = updated.findIndex(
              (d) => d.name.toLowerCase() === docData.name.toLowerCase()
            );
            if (index !== -1) {
              updated[index] = {
                ...updated[index],
                name: docData.name,
                date: docData.date,
                status: docData.status || "Uploaded",
                size: docData.size,
                blob_name: docData.blob_name,
                processing: false, // ✅ stop spinner immediately
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

    // ⏳ Conditional fallback: only mark as uploaded if still processing after 25s
    setTimeout(() => {
      setUploadedDocs((prev) =>
        prev.map((doc) =>
          doc.processing ? { ...doc, processing: false, status: "Uploaded" } : doc
        )
      );
    }, 350000);
  };

  const removeFile = async (index) => {
    const docToRemove = uploadedDocs[index];
    setUploadedDocs((prev) => prev.filter((_, i) => i !== index));

    if (docToRemove?.blob_name) {
      try {
        await fetch("/delete-blob", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ blob_name: docToRemove.blob_name }),
        });
      } catch (err) {
        console.error("Failed to delete blob", err);
      }
    }
  };

  // ✅ Resize logic (drag from top-left)
  const handleMouseDown = (e) => {
    resizingRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      startWidth: chatSize.width,
      startHeight: chatSize.height,
    };
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    e.preventDefault();
  };

  const handleMouseMove = (e) => {
    if (!resizingRef.current) return;
    const dx = resizingRef.current.startX - e.clientX;
    const dy = resizingRef.current.startY - e.clientY;
    setChatSize({
      width: Math.max(300, resizingRef.current.startWidth + dx),
      height: Math.max(400, resizingRef.current.startHeight + dy),
    });
  };

  const handleMouseUp = () => {
    resizingRef.current = false;
    window.removeEventListener("mousemove", handleMouseMove);
    window.removeEventListener("mouseup", handleMouseUp);
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
      <div className="chatbot-container">
        {!showChat && (
          <button className="chat-toggle" onClick={() => setShowChat(true)}>
            💬 Chat
          </button>
        )}

        {showChat && (
          <div
            className={`chat-window ${isFullscreen ? "fullscreen" : ""}`}
            style={
              isFullscreen
                ? {}
                : { width: chatSize.width, height: chatSize.height }
            }
          >
            <div
              className="resize-handle"
              onMouseDown={handleMouseDown}
              title="Drag to resize"
            ></div>

            <div className="chat-header">
              <div>
                <strong>Multi-Doc Chatbot</strong>
                <div className="chat-subtitle">
                  Searching: {currentBlobNames.length} file
                  {currentBlobNames.length !== 1 ? "s" : ""} in view
                </div>
              </div>
              <div>
                <button
                  className="chat-fullscreen"
                  onClick={() => setIsFullscreen((f) => !f)}
                >
                  {isFullscreen ? "⤡" : "⛶"}
                </button>
                <button
                  className="chat-close"
                  onClick={() => setShowChat(false)}
                >
                  ✕
                </button>
              </div>
            </div>

            <div className="chat-body" ref={chatBodyRef}>
              {messages.map((m, i) => (
                <div key={i} className={`chat-msg ${m.role}`}>
                  <div className="bubble">
                    <div
                      dangerouslySetInnerHTML={{
                        __html: m.text.replace(/\n/g, "<br/>"),
                      }}
                    />
                    {m.sources?.length ? (
                      <div className="sources">
                        {m.sources.map((s, idx) => (
                          <span
                            key={`${idx}-${s.blob_name}`}
                            className="source-tag"
                          >
                            {s.filename}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}

              {chatLoading && (
                <div className="chat-msg assistant">
                  <div className="bubble">Thinking…</div>
                </div>
              )}
            </div>

            <div className="chat-input-row">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={onKeyDownChat}
                placeholder="Ask about the documents in the table…"
                rows={2}
              />
              <button
                className="send-btn"
                onClick={sendMessage}
                disabled={chatLoading || !chatInput.trim()}
              >
                Send
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
