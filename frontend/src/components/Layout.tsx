import { useAuth } from '../context/AuthContext'
import { useNavigate, NavLink } from 'react-router-dom'

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top nav */}
      <nav className="bg-white border-b border-gray-200 px-6 py-3 flex
                      items-center justify-between">
        <div className="flex items-center gap-8">
          <span className="font-semibold text-gray-900">SANGATNA</span>
          <div className="flex items-center gap-4 text-sm">
            <NavLink
              to="/upload"
              className={({ isActive }) =>
                isActive
                  ? 'text-green-600 font-medium'
                  : 'text-gray-600 hover:text-gray-900'
              }
            >
              Upload
            </NavLink>
            <NavLink
              to="/documents"
              className={({ isActive }) =>
                isActive
                  ? 'text-green-600 font-medium'
                  : 'text-gray-600 hover:text-gray-900'
              }
            >
              Documents
            </NavLink>
          </div>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-500">{user?.full_name}</span>
          <button
            onClick={handleLogout}
            className="text-gray-500 hover:text-gray-900"
          >
            Sign out
          </button>
        </div>
      </nav>

      {/* Page content */}
      <main className="py-8">
        {children}
      </main>
    </div>
  )
}