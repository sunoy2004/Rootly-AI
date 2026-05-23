import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { login as apiLogin, setAuthHeader } from '../api/client';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await apiLogin(username, password);
      login(data.access_token);
      setAuthHeader({ Authorization: `Bearer ${data.access_token}` });
      navigate('/dashboard');
    } catch (err) {
      setError(
        err.response?.data?.detail || 'Login failed. Please check your credentials.'
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0f1117',
      }}
    >
      <div
        style={{
          backgroundColor: '#1a1d27',
          border: '1px solid #2a2d3a',
          borderRadius: 12,
          padding: 40,
          width: 360,
        }}
      >
        <h1
          style={{
            color: '#e8eaf0',
            fontSize: 24,
            textAlign: 'center',
            marginBottom: 32,
          }}
        >
          API Monitoring Dashboard
        </h1>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 20 }}>
            <label
              style={{
                display: 'block',
                color: '#8b8fa8',
                fontSize: 13,
                marginBottom: 8,
              }}
            >
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={{
                width: '100%',
                padding: '12px 14px',
                backgroundColor: '#0f1117',
                border: '1px solid #2a2d3a',
                borderRadius: 6,
                color: '#e8eaf0',
                fontSize: 14,
                boxSizing: 'border-box',
              }}
              autoFocus
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label
              style={{
                display: 'block',
                color: '#8b8fa8',
                fontSize: 13,
                marginBottom: 8,
              }}
            >
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{
                width: '100%',
                padding: '12px 14px',
                backgroundColor: '#0f1117',
                border: '1px solid #2a2d3a',
                borderRadius: 6,
                color: '#e8eaf0',
                fontSize: 14,
                boxSizing: 'border-box',
              }}
            />
          </div>

          {error && (
            <div
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid #ef4444',
                borderRadius: 6,
                padding: '10px 14px',
                color: '#ef4444',
                fontSize: 13,
                marginBottom: 16,
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '12px',
              backgroundColor: '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
              cursor: loading ? 'wait' : 'pointer',
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <p
          style={{
            color: '#8b8fa8',
            fontSize: 12,
            textAlign: 'center',
            marginTop: 20,
          }}
        >
          Use admin / admin123
        </p>
      </div>
    </div>
  );
}
