import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'

function App() {
  const [status, setStatus] = useState('checking…')

  useEffect(() => {
    // Ping the FastAPI health-check to confirm both ends are running.
    fetch('/api/')
      .then((r) => r.json())
      .then((d) => setStatus(`Backend says: ${JSON.stringify(d)}`))
      .catch(() => setStatus('Backend not reachable — start uvicorn first.'))
  }, [])

  return (
    <div style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <h1>Parallax — scaffold check</h1>
      <p>{status}</p>
      <p style={{ color: '#888' }}>
        UI canvas will be built here after spikes A &amp; B are validated.
      </p>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />)
