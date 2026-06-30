import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Loader2 } from 'lucide-react';

const SUGGESTIONS = [
  "Can I exercise outside today?",
  "Is this safe for children?",
  "Should I wear a mask?",
  "Is it safe for elderly to travel?",
  "What is causing this pollution?"
];

export default function FollowUpChat({ pollutantType, currentValue, statusLabel }) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorFlash, setErrorFlash] = useState(false);
  
  const historyRef = useRef(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    if (historyRef.current) {
      historyRef.current.scrollTop = historyRef.current.scrollHeight;
    }
  }, [history, isLoading]);

  const handleSend = async (qText = question) => {
    const textToSubmit = qText.trim().substring(0, 200); // Feature 8 Edge Case: Max 200 chars
    
    if (!textToSubmit) {
      setErrorFlash(true);
      setTimeout(() => setErrorFlash(false), 500);
      return;
    }

    setIsLoading(true);
    setQuestion(""); // Clear input
    
    try {
      // Extended API Call logic per spec
      const response = await axios.post('/api/insight', {
        pollutant: pollutantType,
        value: currentValue,
        status: statusLabel,
        question: textToSubmit
      });

      // Handle backend returning standard object or plain string answer
      const answerRaw = response.data;
      let answerText = "The AI didn't provide an answer. Try rephrasing.";
      
      if (typeof answerRaw === 'string') answerText = answerRaw;
      else if (answerRaw?.answer) answerText = answerRaw.answer;
      else if (answerRaw?.short_term_effects) answerText = answerRaw.short_term_effects; // Fallback

      setHistory(prev => [...prev, { q: textToSubmit, a: answerText }]);
    } catch (err) {
      setHistory(prev => [...prev, { q: textToSubmit, a: "⚠ Could not get an answer. Please try again.", error: true }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading) handleSend();
    }
  };

  return (
    <div className="follow-up-section">
      <div style={{ fontSize: '14px', fontWeight: 700, marginBottom: '12px' }}>
        💬 Ask a Follow-up Question
      </div>
      
      {/* Question Chips */}
      <div className="follow-up-chips">
        {SUGGESTIONS.map((chip, idx) => (
          <button 
            key={idx} 
            className="follow-up-chip" 
            disabled={isLoading}
            onClick={() => {
              setQuestion(chip);
              document.getElementById('follow-up-input').focus();
            }}
          >
            {chip}
          </button>
        ))}
      </div>

      {/* Input Area */}
      <div className="follow-up-input-wrap">
        <input
          id="follow-up-input"
          className={`follow-up-input ${errorFlash ? 'error' : ''}`}
          placeholder="Ask anything about your air quality..."
          value={question}
          onChange={(e) => setQuestion(e.target.value.substring(0, 200))}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
        />
        <button 
          className="btn-send-chat" 
          onClick={() => handleSend()} 
          disabled={isLoading || !question.trim()}
        >
          {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </div>

      {/* Edge case: Character count warning */}
      {question.length > 150 && (
        <div style={{ fontSize: '11px', color: 'var(--warning)', marginTop: '4px', textAlign: 'right' }}>
          {question.length}/200
        </div>
      )}

      {/* Answer History */}
      {(history.length > 0 || isLoading) && (
        <div className="ai-chat-history" ref={historyRef}>
          {history.map((chat, i) => (
            <div key={i} className="ai-answer-box" style={{ borderColor: chat.error ? 'var(--error)' : '' }}>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '8px' }}>
                Q: {chat.q}
              </div>
              <div style={{ fontSize: '15px', color: chat.error ? 'var(--error)' : '#334155', lineHeight: 1.7 }}>
                A: {chat.a}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="ai-answer-box">
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '8px' }}>
                Generating answer...
              </div>
              <div className="skeleton" style={{ height: '14px', width: '80%', marginBottom: '8px' }} />
              <div className="skeleton" style={{ height: '14px', width: '95%', marginBottom: '8px' }} />
              <div className="skeleton" style={{ height: '14px', width: '60%' }} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
