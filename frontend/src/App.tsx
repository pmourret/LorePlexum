import { Navigate, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout'
import DetailPage from './pages/DetailPage'
import HistoryPage from './pages/HistoryPage'
import InjectPage from './pages/InjectPage'
import KeysPage from './pages/KeysPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/inject" replace />} />
        <Route path="/inject" element={<InjectPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/injection/:id" element={<DetailPage />} />
        <Route path="/keys" element={<KeysPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

function NotFound() {
  return (
    <div className="notfound">
      <h1>Page introuvable</h1>
      <p className="muted">Ce chemin ne correspond à aucune page de l'outil.</p>
    </div>
  )
}
