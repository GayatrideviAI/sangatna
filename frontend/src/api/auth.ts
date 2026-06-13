import api from './client'

export interface LoginResponse {
  access_token: string
  token_type: string
  user_id: string
  company_id: string
  role: string
  full_name: string
}

export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/login', {
    email,
    password,
  })
  return data
}

export async function getMe() {
  const { data } = await api.get('/auth/me')
  return data
}