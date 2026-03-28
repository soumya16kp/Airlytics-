import axios from 'axios';

const API_URL = 'http://localhost:8000/api/';

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

const getDistricts = async () => {
  const response = await api.get('districts/');
  return response.data;
};

const getTowns = async (districtId) => {
  const response = await api.get(`towns/?district=${districtId}`);
  return response.data;
};

const getEmissions = async (filters) => {
  const { town, district, sector } = filters;
  let url = 'emissions/';
  const params = new URLSearchParams();
  if (town) params.append('town', town);
  if (district) params.append('district', district);
  if (sector) params.append('sector', sector);
  
  if (params.toString()) {
    url += `?${params.toString()}`;
  }
  
  const response = await api.get(url);
  return response.data;
};

const getProfile = async () => {
  const response = await api.get('profile/');
  return response.data;
};

const updateProfile = async (profileData) => {
  const response = await api.patch('profile/', profileData);
  return response.data;
};

const getMapData = async () => {
  const response = await api.get('map-data/');
  return response.data;
};

/**
 * Calls the live RF model for a given town.
 * Returns { town_name, district, latitude, longitude, base_co_2026, timeline }
 */
const predictCO = async (townId) => {
  const response = await api.get(`predict-co/?town=${townId}`);
  return response.data;
};

/**
 * Runs RF model at any arbitrary lat/lon (for draggable map marker).
 * Returns { base_co_2026, march_co_2026, lat, lon }
 */
const predictCOAt = async (lat, lon) => {
  const response = await api.get(`predict-co-at/?lat=${lat}&lon=${lon}`);
  return response.data;
};

const locationService = {
  getDistricts,
  getTowns,
  getEmissions,
  getProfile,
  updateProfile,
  getMapData,
  predictCO,
  predictCOAt,
};

export default locationService;
