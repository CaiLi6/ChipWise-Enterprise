import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 60000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('chipwise_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('chipwise_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default api
