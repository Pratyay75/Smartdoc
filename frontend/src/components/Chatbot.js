import React, { useState, useRef, useEffect } from 'react';
import './Chatbot.css';

const ChatBot = ({ pdfId = null, contextType = "single-pdf" }) => {
  const [chatOpen, setChatOpen] = useState(false);
const [messages, setMessages] = useState([
  { sender: 'bot', text: contextType === "single-pdf"
      ? "Hey! I'm AI assistant 🤖. Ready to explore your PDF in style?"
      : "Hey! I can search across all uploaded documents. What do you want to know?"
  },
  ...(contextType === "single-pdf" ? [{ sender: 'suggestions' }] : [])
]);

  const [userInput, setUserInput] = useState('');
  const recognitionRef = useRef(null);
const chatBodyRef = useRef(null);

  // PDF Extractor page options
  const pdfOptions = [
    { icon: '📝', label: 'Summarize in 3 points', value: 'Summarize in 3 points' },
    { icon: '📅', label: 'Find all important dates', value: 'List all key dates from PDF' },
    { icon: '👥', label: 'List parties involved', value: 'List all people or entities mentioned' },
    { icon: '📌', label: 'Highlight key terms', value: 'What are the main clauses and terms?' },
  ];

  // Multi-doc page options
// Multi-doc page options removed
const multiDocOptions = [];


  const currentOptions = contextType === "single-pdf" ? pdfOptions : multiDocOptions;
useEffect(() => {
  if (chatBodyRef.current) {
    chatBodyRef.current.scrollTop = chatBodyRef.current.scrollHeight;
  }
}, [messages]);

  const sendToBackend = (question) => {
    // For PDF Extractor, pdfId is required
    if (contextType === "single-pdf" && !pdfId) {
      setMessages(prev => [
        ...prev,
        { sender: 'bot', text: "Please upload & extract a PDF first to chat." },
        { sender: 'suggestions' }
      ]);
      return;
    }

    setMessages(prev => [...prev, { sender: 'bot', text: '...', loading: true }]);

    const BACKEND_URL = window.location.hostname.includes("localhost")
  ? "http://localhost:5000"
  : "https://smartdoc-ebf9a0eddvd0ecet.eastus-01.azurewebsites.net";


const route = contextType === "multi-doc" 
  ? `${BACKEND_URL}/chat-multi-doc` 
  : `${BACKEND_URL}/chat`;

const payload =
  contextType === "multi-doc"
    ? { question } // no pdfId needed
    : { question, pdf_id: pdfId }; // pdfId needed for single-pdf

fetch(route, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload),
})
      .then(res => res.json())
      .then(data => {
        setMessages(prev => [
          ...prev.slice(0, -1),
          { sender: 'bot', text: data.answer || "Hmm, I couldn’t find anything relevant." },
          { sender: 'suggestions' }
        ]);
      })
      .catch(() => {
        setMessages(prev => [
          ...prev.slice(0, -1),
          { sender: 'bot', text: "Oops! Something went wrong. Try again later." },
          { sender: 'suggestions' }
        ]);
      });
  };

  const handleOptionClick = (value) => {
    setMessages(prev => [...prev, { sender: 'user', text: value }]);
    sendToBackend(value);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!userInput.trim()) return;
    setMessages(prev => [...prev, { sender: 'user', text: userInput }]);
    sendToBackend(userInput);
    setUserInput('');
  };

  // 🎤 Voice Recognition
  const startListening = () => {
    if (!('webkitSpeechRecognition' in window)) {
      alert("Your browser doesn't support speech recognition.");
      return;
    }
    recognitionRef.current = new window.webkitSpeechRecognition();
    recognitionRef.current.lang = 'en-US';
    recognitionRef.current.interimResults = false;
    recognitionRef.current.maxAlternatives = 1;

    recognitionRef.current.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setUserInput('');
      setMessages(prev => [...prev, { sender: 'user', text: transcript }]);
      sendToBackend(transcript);
    };

    recognitionRef.current.start();
  };

  return (
    <div className="chatbot-container">
      {!chatOpen ? (
        <button className="chatbot-toggle" onClick={() => setChatOpen(true)}>💬</button>
      ) : (
        <div className="chatbot-box">
          <div className="chatbot-header">
            <span>AI Assistant</span>
            <span className="close-icon" onClick={() => setChatOpen(false)}>×</span>
          </div>

          <div className="chatbot-body" ref={chatBodyRef}>

            {messages.map((msg, idx) => (
              msg.sender === 'suggestions' ? (
                <div key={idx} className="chatbot-suggestions">
                  {currentOptions.map((opt, idx2) => (
                    <button key={idx2} onClick={() => handleOptionClick(opt.value)}>
                      {opt.icon} {opt.label}
                    </button>
                  ))}
                </div>
              ) : (
                <div
                  key={idx}
                  className={`chat-message ${msg.sender} ${msg.loading ? 'typing' : ''}`}
                >
                  {msg.loading ? (
                    <>
                      <span className="dot"></span>
                      <span className="dot"></span>
                      <span className="dot"></span>
                    </>
                  ) : (
                    <span dangerouslySetInnerHTML={{ __html: msg.text.replace(/\n/g, "<br/>") }}></span>
                  )}
                  <div className="timestamp">
                    {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              )
            ))}
          </div>

          <form className="chatbot-input" onSubmit={handleSubmit}>
            <input
              name="userInput"
              placeholder="Type your question..."
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
            />
            <button type="button" className="mic-btn" onClick={startListening}>🎤</button>
            <button type="submit">➤</button>
          </form>
        </div>
      )}
    </div>
  );
};

export default ChatBot;
