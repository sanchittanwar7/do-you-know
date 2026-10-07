import { Route, Routes } from 'react-router-dom'
import Home from './pages/Home.jsx'
import Preview from './pages/Preview.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/preview/:draftId" element={<Preview />} />
    </Routes>
  )
}
