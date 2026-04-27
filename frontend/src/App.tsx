import { useEffect, useMemo, useState } from 'react'
import './App.css'

type WorkflowResponse = {
  session_id: string
  caption: string
  analysis: {
    style: string
    emotion: string
    composition: string
  }
  critique: string
  generation: {
    positive_prompt: string
    negative_prompt: string
    edit_suggestion: string
    generated_image_url: string | null
  }
}

type SessionTurn = {
  timestamp: string
  description: string
  persona: string
  caption: string
  style: string
  emotion: string
  composition: string
  positive_prompt: string
  negative_prompt: string
  generated_image_url: string | null
  controls: {
    stylization: number
    drama: number
    texture: number
    warmth: number
  }
}

type CompareResponse = {
  session_id: string
  items: Array<{
    index: number
    filename: string
    caption: string
    style: string
    emotion: string
    composition: string
    score: number
  }>
  best_index: number
  summary: string
  generation: {
    positive_prompt: string
    negative_prompt: string
    edit_suggestion: string
    generated_image_url: string | null
  }
}

type ChatMessage = {
  role: 'user' | 'assistant'
  text: string
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

const PERSONAS = [
  'friendly mentor',
  'strict academic critic',
  'gallery curator',
  'commercial art director',
]

const PRESETS = [
  { label: 'Cinematic', values: { stylization: 0.8, drama: 0.85, texture: 0.65, warmth: 0.6 } },
  { label: 'Soft Editorial', values: { stylization: 0.55, drama: 0.35, texture: 0.45, warmth: 0.5 } },
  { label: 'Dreamy', values: { stylization: 0.9, drama: 0.55, texture: 0.7, warmth: 0.65 } },
  { label: 'Minimal', values: { stylization: 0.3, drama: 0.3, texture: 0.25, warmth: 0.45 } },
] as const

function App() {
  const [mode, setMode] = useState<'single' | 'compare'>('single')

  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [userEmail, setUserEmail] = useState('')

  const [description, setDescription] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [compareFiles, setCompareFiles] = useState<File[]>([])
  const [persona, setPersona] = useState(PERSONAS[0])

  const [stylization, setStylization] = useState(0.6)
  const [drama, setDrama] = useState(0.6)
  const [texture, setTexture] = useState(0.55)
  const [warmth, setWarmth] = useState(0.5)

  const [loading, setLoading] = useState(false)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<WorkflowResponse | null>(null)
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null)
  const [sessionId, setSessionId] = useState('')
  const [turns, setTurns] = useState<SessionTurn[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [summaryInput, setSummaryInput] = useState('')
  const [summaryStyle, setSummaryStyle] = useState<'concise' | 'detailed' | 'chat'>('concise')
  const [summaryOutput, setSummaryOutput] = useState('')

  const previewUrl = useMemo(() => {
    if (!imageFile) return ''
    return URL.createObjectURL(imageFile)
  }, [imageFile])

  const generatedImageUrl = useMemo(() => {
    if (!result?.generation.generated_image_url) return ''
    const p = result.generation.generated_image_url
    return p.startsWith('http') ? p : `${API_BASE}${p}`
  }, [result])

  const compareGeneratedImageUrl = useMemo(() => {
    if (!compareResult?.generation.generated_image_url) return ''
    const p = compareResult.generation.generated_image_url
    return p.startsWith('http') ? p : `${API_BASE}${p}`
  }, [compareResult])

  async function loadSessionHistory(id: string, authToken: string) {
    const res = await fetch(`${API_BASE}/api/v1/sessions/${id}`, {
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    })
    if (!res.ok) return
    const data = await res.json()
    setTurns(data.turns ?? [])
  }

  useEffect(() => {
    let active = true

    async function bootstrapAuth() {
      if (!token) return
      const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (!active) return

      if (!res.ok) {
        localStorage.removeItem('token')
        setToken('')
        setUserEmail('')
        return
      }

      const data = await res.json()
      setUserEmail(data.user.email)
    }

    bootstrapAuth()
    return () => {
      active = false
    }
  }, [token])

  async function onAuthSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    try {
      const endpoint = authMode === 'login' ? 'login' : 'register'
      const res = await fetch(`${API_BASE}/api/v1/auth/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      })

      if (!res.ok) {
        const details = await res.text()
        throw new Error(details || 'Authentication failed')
      }

      const data = await res.json()
      localStorage.setItem('token', data.token)
      setToken(data.token)
      setUserEmail(data.user.email)
      setPassword('')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setError(message)
    }
  }

  function logout() {
    localStorage.removeItem('token')
    setToken('')
    setUserEmail('')
    clearAll()
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      if (!token) {
        throw new Error('Login required')
      }

      if (mode === 'compare') {
        if (compareFiles.length < 2) {
          throw new Error('Select at least 2 images for compare mode')
        }

        const compareForm = new FormData()
        compareFiles.forEach((f) => compareForm.append('images', f))
        compareForm.append('description', description)
        compareForm.append('persona', persona)
        compareForm.append('stylization', String(stylization))
        compareForm.append('drama', String(drama))
        compareForm.append('texture', String(texture))
        compareForm.append('warmth', String(warmth))
        if (sessionId) compareForm.append('session_id', sessionId)

        const compareRes = await fetch(`${API_BASE}/api/v1/workflows/compare-analysis`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: compareForm,
        })

        if (!compareRes.ok) {
          const details = await compareRes.text()
          throw new Error(details || 'Compare request failed')
        }

        const data: CompareResponse = await compareRes.json()
        setCompareResult(data)
        setResult(null)
        setSessionId(data.session_id)
        setMessages((prev) => [
          ...prev,
          { role: 'user', text: description || `Compare ${compareFiles.length} artworks` },
          {
            role: 'assistant',
            text: `Best candidate: image ${data.best_index + 1}\n\n${data.summary}`,
          },
        ])
        await loadSessionHistory(data.session_id, token)
        return
      }

      const formData = new FormData()
      if (imageFile) formData.append('image', imageFile)
      formData.append('description', description)
      formData.append('persona', persona)
      formData.append('stylization', String(stylization))
      formData.append('drama', String(drama))
      formData.append('texture', String(texture))
      formData.append('warmth', String(warmth))
      if (sessionId) formData.append('session_id', sessionId)

      const res = await fetch(`${API_BASE}/api/v1/workflows/full-analysis`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      })

      if (!res.ok) {
        const details = await res.text()
        throw new Error(details || 'Request failed')
      }

      const data: WorkflowResponse = await res.json()
      setResult(data)
      setCompareResult(null)
      setSessionId(data.session_id)
      setMessages((prev) => [
        ...prev,
        { role: 'user', text: description || (imageFile ? 'Analyze uploaded artwork' : 'Analyze') },
        {
          role: 'assistant',
          text: `Style: ${data.analysis.style}\nEmotion: ${data.analysis.emotion}\n\n${data.critique}`,
        },
      ])
      await loadSessionHistory(data.session_id, token)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  function clearAll() {
    setDescription('')
    setImageFile(null)
    setCompareFiles([])
    setResult(null)
    setCompareResult(null)
    setError('')
    setMessages([])
    setSessionId('')
    setTurns([])
  }

  async function exportReport() {
    if (!sessionId || !token) return

    const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}/export`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
    if (!res.ok) {
      const details = await res.text()
      setError(details || 'Export failed')
      return
    }

    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `session_${sessionId}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  function applyPreset(values: { stylization: number; drama: number; texture: number; warmth: number }) {
    setStylization(values.stylization)
    setDrama(values.drama)
    setTexture(values.texture)
    setWarmth(values.warmth)
  }

  async function summarizeNow() {
    setError('')
    setSummaryLoading(true)
    setSummaryOutput('')

    try {
      if (!token) {
        throw new Error('Login required')
      }

      const res = await fetch(`${API_BASE}/api/v1/chat/summarize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          text: summaryInput,
          style: summaryStyle,
        }),
      })

      if (!res.ok) {
        const details = await res.text()
        throw new Error(details || 'Summarization failed')
      }

      const data = await res.json()
      setSummaryOutput(data.summary || '')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setError(message)
    } finally {
      setSummaryLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="auth-shell">
        <section className="auth-card">
          <p className="eyebrow">Welcome</p>
          <h1>Multimodal Art Critic</h1>
          <p className="subtitle">Sign in to save sessions, compare artworks, and export reports.</p>

          <div className="auth-tabs">
            <button className={authMode === 'login' ? 'active' : ''} onClick={() => setAuthMode('login')} type="button">
              Login
            </button>
            <button className={authMode === 'register' ? 'active' : ''} onClick={() => setAuthMode('register')} type="button">
              Register
            </button>
          </div>

          <form onSubmit={onAuthSubmit}>
            <label className="field-label">Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <label className="field-label">Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
            <button className="primary auth-submit" type="submit">
              {authMode === 'login' ? 'Login' : 'Create Account'}
            </button>
          </form>

          {error && <p className="error">{error}</p>}
        </section>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <p className="eyebrow">Creative AI Studio</p>
        <h1>Multimodal Art Critic</h1>
        <p className="subtitle">
          Upload or describe art, receive critique in your chosen persona, tune visual direction, and generate new artwork.
        </p>
        <div className="hero-meta">
          <span>Signed in as {userEmail}</span>
          <button className="ghost" onClick={logout} type="button">Logout</button>
        </div>
      </header>

      <main className="layout">
        <section className="panel input-panel">
          <h2>Input</h2>
          <div className="mode-tabs">
            <button className={mode === 'single' ? 'active' : ''} type="button" onClick={() => setMode('single')}>Single</button>
            <button className={mode === 'compare' ? 'active' : ''} type="button" onClick={() => setMode('compare')}>Compare</button>
          </div>

          <form onSubmit={onSubmit}>
            {mode === 'single' ? (
              <>
                <label className="field-label">Artwork Upload</label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => setImageFile(e.target.files?.[0] || null)}
                />
              </>
            ) : (
              <>
                <label className="field-label">Artwork Uploads (2-4 images)</label>
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(e) => setCompareFiles(Array.from(e.target.files || []))}
                />
              </>
            )}

            {mode === 'single' && previewUrl && (
              <img className="preview" src={previewUrl} alt="Upload preview" />
            )}

            {mode === 'compare' && compareFiles.length > 0 && (
              <p className="file-count">Selected files: {compareFiles.length}</p>
            )}

            <label className="field-label">Describe your intent</label>
            <textarea
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Example: surreal chess pieces debating fate under gallery lights"
            />

            <label className="field-label">Critic Persona</label>
            <select value={persona} onChange={(e) => setPersona(e.target.value)}>
              {PERSONAS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>

            <div className="slider-grid">
              <label>
                Stylization: {stylization.toFixed(2)}
                <input type="range" min={0} max={1} step={0.05} value={stylization} onChange={(e) => setStylization(Number(e.target.value))} />
              </label>
              <label>
                Drama: {drama.toFixed(2)}
                <input type="range" min={0} max={1} step={0.05} value={drama} onChange={(e) => setDrama(Number(e.target.value))} />
              </label>
              <label>
                Texture: {texture.toFixed(2)}
                <input type="range" min={0} max={1} step={0.05} value={texture} onChange={(e) => setTexture(Number(e.target.value))} />
              </label>
              <label>
                Warmth: {warmth.toFixed(2)}
                <input type="range" min={0} max={1} step={0.05} value={warmth} onChange={(e) => setWarmth(Number(e.target.value))} />
              </label>
            </div>

            <div className="preset-row">
              {PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  className="preset"
                  type="button"
                  onClick={() => applyPreset(preset.values)}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            <div className="button-row">
              <button className="primary" type="submit" disabled={loading}>
                {loading ? 'Analyzing...' : 'Analyze & Generate'}
              </button>
              <button className="ghost" type="button" onClick={clearAll}>
                Clear
              </button>
              <button className="ghost" type="button" onClick={exportReport} disabled={!sessionId}>
                Export Report
              </button>
            </div>
          </form>

          {error && <p className="error">{error}</p>}
        </section>

        <section className="panel chat-panel">
          <h2>Critic Chat</h2>
          <div className="chat-box">
            {messages.length === 0 && <p className="empty">Your conversation appears here.</p>}
            {messages.map((m, idx) => (
              <article className={`msg ${m.role}`} key={`${m.role}-${idx}`}>
                <h3>{m.role === 'user' ? 'You' : 'Critic'}</h3>
                <p>{m.text}</p>
              </article>
            ))}
          </div>
          <div className="session-meta">
            <span>Session ID</span>
            <strong>{sessionId || 'not started'}</strong>
          </div>
        </section>

        <section className="panel output-panel">
          <h2>Analysis</h2>

          {compareResult && (
            <article className="long-block">
              <h3>Comparison Summary</h3>
              <p>{compareResult.summary}</p>
              <div className="compare-grid">
                {compareResult.items.map((item) => (
                  <article key={item.index} className={item.index === compareResult.best_index ? 'best' : ''}>
                    <h4>Image {item.index + 1}: {item.filename}</h4>
                    <p><strong>Score:</strong> {item.score}</p>
                    <p><strong>Style:</strong> {item.style}</p>
                    <p><strong>Emotion:</strong> {item.emotion}</p>
                    <p><strong>Caption:</strong> {item.caption}</p>
                  </article>
                ))}
              </div>

              <p><strong>Positive:</strong> {compareResult.generation.positive_prompt || '-'}</p>
              <p><strong>Negative:</strong> {compareResult.generation.negative_prompt || '-'}</p>
              <p><strong>Edit Suggestion:</strong> {compareResult.generation.edit_suggestion || '-'}</p>

              {compareGeneratedImageUrl && (
                <article className="generated-card">
                  <h3>Generated Artwork (Best Candidate)</h3>
                  <img src={compareGeneratedImageUrl} alt="Generated artwork from compare mode" />
                </article>
              )}
            </article>
          )}

          <div className="stat-grid">
            <article>
              <h3>Caption</h3>
              <p>{result?.caption || '-'}</p>
            </article>
            <article>
              <h3>Style</h3>
              <p>{result?.analysis.style || '-'}</p>
            </article>
            <article>
              <h3>Emotion</h3>
              <p>{result?.analysis.emotion || '-'}</p>
            </article>
            <article>
              <h3>Composition</h3>
              <p>{result?.analysis.composition || '-'}</p>
            </article>
          </div>

          <article className="long-block">
            <h3>Critique</h3>
            <p>{result?.critique || '-'}</p>
          </article>

          <article className="long-block">
            <h3>Prompt Studio</h3>
            <p><strong>Positive:</strong> {result?.generation.positive_prompt || '-'}</p>
            <p><strong>Negative:</strong> {result?.generation.negative_prompt || '-'}</p>
            <p><strong>Edit Suggestion:</strong> {result?.generation.edit_suggestion || '-'}</p>
          </article>

          {generatedImageUrl && (
            <article className="generated-card">
              <h3>Generated Artwork</h3>
              <img src={generatedImageUrl} alt="Generated artwork" />
            </article>
          )}
        </section>

        <section className="panel timeline-panel">
          <h2>Session Timeline</h2>
          <div className="timeline">
            {turns.length === 0 && <p className="empty">No previous turns yet.</p>}
            {turns.map((t, idx) => (
              <article key={`${t.timestamp}-${idx}`} className="turn">
                <header>
                  <span>{new Date(t.timestamp).toLocaleString()}</span>
                  <span>{t.persona}</span>
                </header>
                <p><strong>Caption:</strong> {t.caption}</p>
                <p><strong>Style/Emotion:</strong> {t.style} / {t.emotion}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="panel summary-panel">
          <h2>Text Summarizer</h2>
          <p className="helper">Paste long text and get a chatbot-style summary.</p>

          <label className="field-label">Summary Style</label>
          <select value={summaryStyle} onChange={(e) => setSummaryStyle(e.target.value as 'concise' | 'detailed' | 'chat')}>
            <option value="concise">Concise Bullet Summary</option>
            <option value="detailed">Detailed Summary</option>
            <option value="chat">Chatbot Style</option>
          </select>

          <label className="field-label">Text Input</label>
          <textarea
            rows={6}
            value={summaryInput}
            onChange={(e) => setSummaryInput(e.target.value)}
            placeholder="Paste article notes, research text, or long conversation here..."
          />

          <div className="button-row">
            <button className="primary" type="button" onClick={summarizeNow} disabled={summaryLoading}>
              {summaryLoading ? 'Summarizing...' : 'Summarize Text'}
            </button>
            <button className="ghost" type="button" onClick={() => { setSummaryInput(''); setSummaryOutput('') }}>
              Clear Summary
            </button>
          </div>

          <article className="long-block">
            <h3>Summary Output</h3>
            <p>{summaryOutput || '-'}</p>
          </article>
        </section>
      </main>
    </div>
  )
}

export default App
