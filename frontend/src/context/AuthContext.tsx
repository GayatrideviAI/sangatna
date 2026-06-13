import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react'
import { login as apiLogin } from '../api/auth'

interface AuthContextType {
  token: string | null
  user: { full_name: string; role: string } | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(
    localStorage.getItem('token')
  )
  const [user, setUser] = useState<{ full_name: string; role: string } | null>(
    null
  )

  useEffect(() => {
    const stored = localStorage.getItem('user')
    if (stored) setUser(JSON.parse(stored))
  }, [])

  async function login(email: string, password: string) {
    const data = await apiLogin(email, password)
    localStorage.setItem('token', data.access_token)
    localStorage.setItem(
      'user',
      JSON.stringify({ full_name: data.full_name, role: data.role })
    )
    setToken(data.access_token)
    setUser({ full_name: data.full_name, role: data.role })
  }

  function logout() {
    localStorage.clear()
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{ token, user, login, logout, isAuthenticated: !!token }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}