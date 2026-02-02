import './App.css'
import { AgoraProjectGraph } from './AgoraProjectGraph'

import { Component, type ReactNode } from 'react'

class ErrorBoundary extends Component<{ children: ReactNode }, { error?: Error }> {
  state: { error?: Error } = {}

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 16, fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial' }}>
          <h2 style={{ margin: 0, marginBottom: 8 }}>Chart failed to render</h2>
          <pre style={{ whiteSpace: 'pre-wrap', color: '#b91c1c' }}>{String(this.state.error.stack || this.state.error.message)}</pre>
        </div>
      )
    }
    return this.props.children
  }
}

function App() {
  return (
    <ErrorBoundary>
      <AgoraProjectGraph />
    </ErrorBoundary>
  )
}

export default App
