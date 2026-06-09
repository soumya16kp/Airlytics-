import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary] Caught render error:', error, info);
    this.setState({ info });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#f8fafc',
          padding: '40px',
        }}>
          <div style={{
            background: 'white',
            borderRadius: '24px',
            padding: '48px',
            maxWidth: '720px',
            width: '100%',
            boxShadow: '0 20px 40px rgba(0,0,0,0.08)',
            border: '1px solid #fecaca',
          }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>⚠️</div>
            <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', marginBottom: '12px' }}>
              Dashboard Render Error
            </h1>
            <p style={{ color: '#64748b', marginBottom: '24px', lineHeight: 1.6 }}>
              The dashboard crashed during rendering. This is a frontend error. Check the details below and the browser console for more information.
            </p>
            <div style={{
              background: '#fef2f2',
              borderRadius: '12px',
              padding: '20px',
              fontFamily: 'monospace',
              fontSize: '13px',
              color: '#dc2626',
              marginBottom: '24px',
              whiteSpace: 'pre-wrap',
              overflowX: 'auto',
              maxHeight: '200px',
              overflowY: 'auto',
            }}>
              {this.state.error?.toString()}
            </div>
            {this.state.info?.componentStack && (
              <details style={{ marginBottom: '24px' }}>
                <summary style={{ cursor: 'pointer', fontWeight: 700, color: '#475569', marginBottom: '12px' }}>
                  Component Stack Trace
                </summary>
                <pre style={{
                  background: '#f8fafc',
                  borderRadius: '8px',
                  padding: '16px',
                  fontSize: '11px',
                  color: '#475569',
                  overflowX: 'auto',
                  maxHeight: '200px',
                  overflowY: 'auto',
                }}>
                  {this.state.info.componentStack}
                </pre>
              </details>
            )}
            <button
              onClick={() => { this.setState({ hasError: false, error: null, info: null }); window.location.reload(); }}
              style={{
                padding: '12px 32px',
                background: '#6366f1',
                color: 'white',
                border: 'none',
                borderRadius: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                fontSize: '14px',
              }}
            >
              🔄 Reload Dashboard
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
