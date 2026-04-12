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

// ── CO ENDPOINTS ────────────────────────────────────────────────────────────

const getMapData = async () => {
  const response = await api.get('map-data/');
  return response.data;
};

const predictCO = async (townId, range = '1Y') => {
  const response = await api.get(`predict-co/?town=${townId}&range=${range}`);
  return response.data;
};

const predictCOAt = async (lat, lon, range = '1Y') => {
  const response = await api.get(`predict-co-at/?lat=${lat}&lon=${lon}&range=${range}`);
  return response.data;
};

// ── NO2 ENDPOINTS ───────────────────────────────────────────────────────────

const getMapDataNO2 = async () => {
  const response = await api.get('map-data-no2/');
  return response.data;
};

const predictNO2 = async (townId, range = '1Y') => {
  const response = await api.get(`predict-no2/?town=${townId}&range=${range}`);
  return response.data;
};

const predictNO2At = async (lat, lon, range = '1Y') => {
  const response = await api.get(`predict-no2-at/?lat=${lat}&lon=${lon}&range=${range}`);
  return response.data;
};

// ── O3 ENDPOINTS ────────────────────────────────────────────────────────────

const getMapDataO3 = async () => {
  const response = await api.get('map-data-o3/');
  return response.data;
};

const predictO3 = async (townId, range = '1Y') => {
  const response = await api.get(`predict-o3/?town=${townId}&range=${range}`);
  return response.data;
};

const predictO3At = async (lat, lon, range = '1Y') => {
  const response = await api.get(`predict-o3-at/?lat=${lat}&lon=${lon}&range=${range}`);
  return response.data;
};

// ── SO2 ENDPOINTS ───────────────────────────────────────────────────────────

const getMapDataSO2 = async () => {
  const response = await api.get('map-data-so2/');
  return response.data;
};

const predictSO2 = async (townId, range = '1Y') => {
  const response = await api.get(`predict-so2/?town=${townId}&range=${range}`);
  return response.data;
};

const predictSO2At = async (lat, lon, range = '1Y') => {
  const response = await api.get(`predict-so2-at/?lat=${lat}&lon=${lon}&range=${range}`);
  return response.data;
};

const locationService = {
  getDistricts,
  getTowns,
  getEmissions,
  getProfile,
  updateProfile,
  // CO
  getMapData,
  predictCO,
  predictCOAt,
  // NO2
  getMapDataNO2,
  predictNO2,
  predictNO2At,
  // O3
  getMapDataO3,
  predictO3,
  predictO3At,
  // SO2
  getMapDataSO2,
  predictSO2,
  predictSO2At,
};

export default locationService;
