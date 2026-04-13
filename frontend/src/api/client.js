/**
 * Centralized API Client
 * All HTTP communication goes through here.
 */
import axios from 'axios';

// API Base URL (Vite proxy handles /api in dev, production serves from same domain)
export const API_BASE = "/api";

/**
 * Authenticated fetch wrapper — attaches JWT token from localStorage
 */
export const authFetch = (url, options = {}) => {
    const token = localStorage.getItem('token');
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return fetch(url, { ...options, headers });
};

// Configure axios interceptor to include auth token in all requests
axios.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers = config.headers || {};
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

export { axios };
export default { API_BASE, authFetch, axios };
