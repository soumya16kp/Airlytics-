import React, { useState, useEffect } from 'react';

export default function FreshnessCounter({ syncedAt }) {
  const [display, setDisplay] = useState('');

  useEffect(() => {
    if (!syncedAt) {
      setDisplay('');
      return;
    }

    const updateDisplay = () => {
      const seconds = Math.floor((Date.now() - syncedAt) / 1000);
      if (seconds < 60) {
        setDisplay(`${seconds}s ago`);
      } else {
        setDisplay(`${Math.floor(seconds / 60)}m ago`);
      }
    };

    updateDisplay(); // Run immediately
    const interval = setInterval(updateDisplay, 1000);
    
    return () => clearInterval(interval);
  }, [syncedAt]);

  if (!display) return null;

  return <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Synced: {display}</span>;
}
