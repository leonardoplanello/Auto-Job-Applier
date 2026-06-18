import axios from 'axios';

// Smart resolution: If running on Vite dev port 5173, point to backend on 7000.
// Otherwise, use the current page's host.
export const API_BASE_URL = typeof window !== 'undefined'
  ? (window.location.port === '5173'
      ? `${window.location.protocol}//${window.location.hostname}:7000`
      : `${window.location.protocol}//${window.location.host}`)
  : 'http://localhost:7000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;
