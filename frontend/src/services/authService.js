import axios from 'axios';

const normalizeApiUrl = (url) => (url.endsWith('/') ? url : `${url}/`);
const API_URL = normalizeApiUrl('https://obituchiha91-airlytics-backend.hf.space/api');

// Public API for login/register
const publicApi = axios.create({
  baseURL: API_URL,
});

// Authenticated API with interceptors
const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

const login = async (username, password) => {
  const response = await publicApi.post('login/', { username, password });
  if (response.data.access) {
    localStorage.setItem('access_token', response.data.access);
    localStorage.setItem('refresh_token', response.data.refresh);
  }
  return response.data;
};

const register = async (username, email, password) => {
  const response = await publicApi.post('register/', { username, email, password });
  return response.data;
};

const logout = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
};

const getUser = async () => {
  const response = await api.get('user/');
  return response.data;
};

const authService = {
  login,
  register,
  logout,
  getUser,
};

export default authService;
