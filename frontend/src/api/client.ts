import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
})

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // Multi-tenancy — attach active client company if set
  const clientCompanyId = localStorage.getItem('clientCompanyId')
  if (clientCompanyId) {
    config.headers['X-Client-Company-ID'] = clientCompanyId
  }
  return config
})

export default api