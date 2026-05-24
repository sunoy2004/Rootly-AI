import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error(`ErrorBoundary [${this.props.name}]:`, error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            backgroundColor: '#1a1d27',
            border: '1px solid #ef4444',
            borderRadius: 12,
            padding: 20,
            color: '#e8eaf0',
          }}
        >
          <h4 style={{ margin: '0 0 8px', color: '#ef4444' }}>
            {this.props.title || 'Something went wrong'}
          </h4>
          <p style={{ color: '#8b8fa8', fontSize: 13, margin: '0 0 12px' }}>
            {this.props.message || 'This section failed to load. Other parts of the dashboard still work.'}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              backgroundColor: '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              padding: '8px 14px',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
