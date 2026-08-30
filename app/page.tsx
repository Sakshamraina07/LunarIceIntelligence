'use client';

import { useEffect } from 'react';

export default function Home() {
  useEffect(() => {
    // Immediately redirect to the unified GIS Mission Control application
    window.location.replace('http://localhost:5173/');
  }, []);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: '#090d16',
        color: '#00f0ff',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        textAlign: 'center',
        padding: '2rem',
      }}
    >
      <div
        style={{
          border: '1px solid rgba(6, 182, 212, 0.4)',
          borderRadius: '12px',
          padding: '2.5rem',
          maxWidth: '520px',
          backgroundColor: 'rgba(15, 23, 42, 0.8)',
          boxShadow: '0 10px 25px rgba(0, 0, 0, 0.5)',
        }}
      >
        <h1 style={{ fontSize: '1.4rem', fontWeight: 'bold', marginBottom: '0.75rem', color: '#38bdf8' }}>
          LUNAR ICE INTELLIGENCE SYSTEM
        </h1>
        <p style={{ color: '#94a3b8', fontSize: '0.95rem', marginBottom: '1.5rem', lineHeight: 1.5 }}>
          Redirecting to the unified <strong>GIS Mission Control</strong> interface...
        </p>
        <a
          href="http://localhost:5173/"
          style={{
            display: 'inline-block',
            padding: '0.75rem 1.5rem',
            backgroundColor: '#0284c7',
            color: '#ffffff',
            borderRadius: '6px',
            textDecoration: 'none',
            fontWeight: 600,
            fontSize: '0.9rem',
          }}
        >
          Open Mission Control (Port 5173) &rarr;
        </a>
      </div>
    </div>
  );
}
