import React, { useState } from 'react';
import './Chatbot.css';

const ChatBot = ({ pdfId }) => {
  const [chatOpen, setChatOpen] = useState(false);
  const [messages, setMessages] = useState([
    { sender: 'bot', text: "Hey! I'm AI assistant 🤖. Ready to explore your PDF in style?" },
    { sender: 'suggestions' } // Show suggestions at the start
  ]);
  const [userInput, setUserInput] = useState('');

  const initialOptions = [
    { icon: '📝', label: 'Summarize in 3 points', value: 'Summarize in 3 points' },
    { icon: '📅', label: 'Find all important dates', value: 'List all key dates from PDF' },
    { icon: '👥', label: 'List parties involved', value: 'List all people or entities mentioned' },
    { icon: '📌', label: 'Highlight key terms', value: 'What are the main clauses and terms?' },
  ];

  const sendToBackend = (question) => {
    if (!pdfId) {
      setMessages(prev => [
        ...prev,
        { sender: 'bot', text: "Please upload & extract a PDF first to chat." },
        { sender: 'suggestions' }
      ]);
      return;
    }

    setMessages(prev => [
      ...prev,
      { sender: 'bot', text: '...', loading: true }
    ]);

    fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pdf_id: pdfId, question }),
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

  return (
    <div className="chatbot-container">
      {!chatOpen ? (
        <button className="chatbot-toggle" onClick={() => setChatOpen(true)}>
          💬
        </button>
      ) : (
        <div className="chatbot-box">
          <div className="chatbot-header">
            <span>AI Assistant</span>
            <span className="close-icon" onClick={() => setChatOpen(false)}>×</span>
          </div>

          <div className="chatbot-body">
            {messages.map((msg, idx) => (
              msg.sender === 'suggestions' ? (
                <div key={idx} className="chatbot-suggestions">
                  {initialOptions.map((opt, idx2) => (
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
            <button type="submit">➤</button>
          </form>
        </div>
      )}
    </div>
  );
};

export default ChatBot;
