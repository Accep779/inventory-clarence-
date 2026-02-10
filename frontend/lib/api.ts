import axios from 'axios';

// Create Axios instance
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: Add JWT Authorization header
api.interceptors.request.use((config) => {
  // Get token from localStorage
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('cephly_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Response Interceptor: Handle Errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear invalid token and redirect to auth
      if (typeof window !== 'undefined') {
        localStorage.removeItem('cephly_token');
        localStorage.removeItem('cephly_merchant_id');
        
        // Get shop domain for re-auth (if stored)
        const shopDomain = localStorage.getItem('cephly_shop_domain') || 'demo.myshopify.com';
        window.location.href = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081'}/api/auth/install?shop=${shopDomain}`;
      }
    }
    return Promise.reject(error);
  }
);

export default api;
