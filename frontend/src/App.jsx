import { useCallback, useEffect, useState } from 'react'
import {
  CalendarCheck, MessageSquarePlus, NotebookText, Settings, Sun, Moon, GraduationCap, MessageSquare, Trash2,
} from 'lucide-react'
import { api } from './api'
import { ToastProvider, useToast } from './components/ui'
import PlanView from './views/PlanView'
import SettingsView from './views/SettingsView'
import NotesView from './views/NotesView'
import ChatView from './views/ChatView'

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'dark')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('scaffold-theme', theme) } catch (e) { /* private mode */ }
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))]
}

function readRoute() {
  const h = window.location.hash.replace(/^#\/?/, '')
  const [view, ...rest] = h.split('/')
  return { view: view || 'plan', arg: decodeURIComponent(rest.join('/')) }
}

function Shell() {
  const toast = useToast()
  const [theme, toggleTheme] = useTheme()
  const [route, setRoute] = useState(readRoute)
  const [chats, setChats] = useState([])
  const [pending, setPending] = useState(null) // first message for a new chat
  const [models, setModels] = useState(null)

  useEffect(() => {
    const on = () => setRoute(readRoute())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  const go = (view, arg = '') => { window.location.hash = `/${view}${arg ? '/' + encodeURIComponent(arg) : ''}` }

  const loadChats = useCallback(async () => {
    try { setChats(await api('/api/chats')) } catch (e) { setChats([]) }
  }, [])
  useEffect(() => { loadChats() }, [loadChats, route.view])
  useEffect(() => { api('/api/settings').then(setModels).catch(() => {}) }, [route.view])

  // Background events (notes written, memory updated)
  useEffect(() => {
    let es
    try {
      es = new EventSource('/api/events')
      es.onmessage = (m) => {
        const ev = JSON.parse(m.data)
        if (ev.type === 'memory') toast({ kind: 'success', title: 'Memory updated', text: ev.summary, timeout: 7000, action: { label: 'View', onClick: () => go('settings', 'memory') } })
        if (ev.type === 'notes') toast({ kind: 'success', title: 'Notes updated', text: ev.paths.join(', '), timeout: 7000, action: { label: 'Open', onClick: () => go('notes', ev.paths[0]) } })
        if (ev.type === 'chats') loadChats()
        if (ev.type === 'bg_error') toast({ kind: 'error', title: ev.title || 'Background task failed', text: ev.message, timeout: 8000 })
      }
    } catch (e) { /* no events */ }
    return () => es?.close()
  }, [toast, loadChats])

  const newChat = async (firstMessage, meta) => {
    const c = await api('/api/chats', { method: 'POST', body: meta || {} })
    setPending(firstMessage || null)
    await loadChats()
    go('chat', c.id)
  }

  const studyTask = (rawLine) => {
    const clean = rawLine.replace(/^\s*[-*] \[[ xX]\]\s*/, '')
    const link = clean.match(/\]\((file:\/\/[^)]+)\)/)?.[1]
    const text = clean.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/\*\*/g, '')
    newChat(`I want to study this task from my plan: ${text}\n\nTeach me from zero and guide me through it. Don't give me the answers.`,
      { task: text, pinned_files: link ? [link] : [], title: text.slice(0, 70) })
  }

  const deleteChat = async (id) => {
    await api(`/api/chats/${id}`, { method: 'DELETE' })
    await loadChats()
    if (route.view === 'chat' && route.arg === id) go('plan')
  }

  const tutor = models?.roles?.tutor
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo"><GraduationCap size={18} /></span>
          <span>Scaffold</span>
        </div>
        <button className="btn primary block" onClick={() => newChat()}><MessageSquarePlus size={16} /> New chat</button>
        <nav className="nav">
          <button className={route.view === 'plan' ? 'on' : ''} onClick={() => go('plan')}><CalendarCheck size={17} /> Study plan</button>
          <button className={route.view === 'notes' ? 'on' : ''} onClick={() => go('notes')}><NotebookText size={17} /> Notes</button>
        </nav>
        <div className="nav-label">Chats</div>
        <div className="chat-list">
          {chats.length === 0 && <p className="muted small pad">No chats yet. Start one from a plan task or paste an exam question.</p>}
          {chats.map((c) => (
            <div key={c.id} className={`chat-item ${route.view === 'chat' && route.arg === c.id ? 'on' : ''}`}>
              <button className="chat-link" onClick={() => go('chat', c.id)} title={c.title}><MessageSquare size={14} /> <span>{c.title || 'New chat'}</span></button>
              <button className="icon-btn ghost del" onClick={() => deleteChat(c.id)} aria-label="Delete chat"><Trash2 size={13} /></button>
            </div>
          ))}
        </div>
        <div className="sidebar-foot">
          <button className={`nav-btn ${route.view === 'settings' ? 'on' : ''}`} onClick={() => go('settings')}>
            <Settings size={17} />
            <span className="grow">Settings</span>
            {tutor && <span className="model-pill" title="Tutor model">{tutor.model || tutor.provider}</span>}
          </button>
          <button className="icon-btn" onClick={toggleTheme} aria-label="Toggle theme" title={theme === 'dark' ? 'Light mode' : 'Dark mode'}>
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </div>
      </aside>
      <main className="main">
        {route.view === 'plan' && <PlanView onStudy={studyTask} />}
        {route.view === 'notes' && <NotesView initial={route.arg} />}
        {route.view === 'settings' && <SettingsView section={route.arg} onSaved={setModels} />}
        {route.view === 'chat' && route.arg && (
          <ChatView key={route.arg} chatId={route.arg} firstMessage={pending} onConsumedFirst={() => setPending(null)} onChanged={loadChats} />
        )}
      </main>
    </div>
  )
}

export default function App() {
  return <ToastProvider><Shell /></ToastProvider>
}
