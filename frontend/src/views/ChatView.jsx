import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowUp, Paperclip, X, ShieldCheck, ShieldAlert, ChevronDown, Loader2, Check, Image as ImageIcon,
  FileText, BookOpen, ClipboardPaste, CalendarCheck, Sparkles, Search, Library,
} from 'lucide-react'
import { api, follow, setBusy as markBusy, upload } from '../api'
import Markdown from '../components/Markdown'
import { Modal, Pitch, useToast } from '../components/ui'
import ModelPicker from '../components/ModelPicker'

const STAGES = [
  { id: 'context', label: 'Reading your materials' },
  { id: 'drafting', label: 'Tutor is writing' },
  { id: 'reviewing', label: 'Reviewer is checking' },
]
const ISSUE_LABEL = {
  correctness: 'Correctness', completeness: 'Missing step', gave_answer: 'Gave the answer away',
  feedback: 'Feedback on attempt', memory: 'Your preferences', clarity: 'Clarity',
}

function ReviewBadge({ review }) {
  const [open, setOpen] = useState(false)
  if (!review) return null
  if (!review.enabled) return <div className="review-badge off">Not reviewed</div>
  const fixes = review.rounds.filter((r) => r.verdict === 'revise').reduce((n, r) => n + (r.issues?.length || 0), 0)
  const ok = review.final !== 'best_effort'
  return (
    <div className="review">
      <button className={`review-badge ${ok ? 'ok' : 'warn'}`} onClick={() => setOpen(!open)} aria-expanded={open}>
        {ok ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
        <span>{ok ? 'Reviewed' : 'Reviewed with open issues'}</span>
        {fixes > 0 && <span className="sep">·</span>}
        {fixes > 0 && <span>{review.student_note || `${fixes} fix${fixes > 1 ? 'es' : ''} before you saw it`}</span>}
        {fixes === 0 && <span className="muted">· approved first time</span>}
        {fixes > 0 && <ChevronDown size={14} className={open ? 'rot' : ''} />}
      </button>
      {open && fixes > 0 && (
        <div className="review-detail">
          {review.rounds.map((r, i) => r.issues?.length > 0 && (
            <div key={i}>
              <div className="muted tiny">Round {i + 1}: the reviewer sent it back</div>
              <ul>
                {r.issues.map((is, j) => (
                  <li key={j}><span className={`issue-tag t-${is.type}`}>{ISSUE_LABEL[is.type] || is.type}</span> {is.fix}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const ACT_ICON = { context: '📚', draft: '✍️', tool: '🔎', review: '🛡️', issues: '↩︎', revise: '🔧', approved: '✓' }

function ActivityList({ items, live }) {
  return (
    <ol className={`activity ${live ? 'live' : ''}`}>
      {items.map((a, i) => (
        <li key={i} className={`act act-${a.kind}`}>
          <span className="act-icon" aria-hidden="true">{ACT_ICON[a.kind] || '•'}</span>
          <div className="act-body">
            <span>{a.text}</span>
            {a.issues?.length > 0 && (
              <ul className="act-issues">
                {a.issues.map((is, j) => <li key={j}><span className="issue-tag">{is.label}</span> {is.fix}</li>)}
              </ul>
            )}
          </div>
          <span className="act-time mono">{a.t != null ? `${a.t}s` : ''}</span>
        </li>
      ))}
    </ol>
  )
}

function Pending({ stage, elapsed, detail, rounds, activity = [], reconnecting }) {
  const order = ['context', 'drafting', 'tool', 'reviewing', 'revising']
  const idx = order.indexOf(stage)
  const steps = [...STAGES]
  if (stage === 'revising' || rounds > 0) steps.push({ id: 'revising', label: 'Tutor is fixing what the reviewer found' })
  const activeId = stage === 'tool' ? 'drafting' : stage
  return (
    <div className="msg assistant pending">
      <div className="avatar tutor"><Sparkles size={15} /></div>
      <div className="bubble">
        <div className="pending-steps">
          {steps.map((s) => {
            const sIdx = order.indexOf(s.id)
            const state = s.id === activeId ? 'active' : sIdx < idx || (s.id === 'reviewing' && stage === 'revising') ? 'done' : 'todo'
            return (
              <div key={s.id} className={`pstep ${state}`}>
                <span className="pdot">{state === 'done' ? <Check size={11} /> : state === 'active' ? <Loader2 size={11} className="spin" /> : null}</span>
                {s.label}
                {state === 'active' && elapsed != null && <span className="muted tiny mono">{elapsed}s</span>}
              </div>
            )
          })}
        </div>
        {detail && <div className="muted small pdetail">{detail}</div>}
        {reconnecting && <div className="reconnect small"><Loader2 size={12} className="spin" /> Connection dropped. Reconnecting; the tutor keeps working on the server…</div>}
        {activity.length > 0 && <ActivityList items={activity.slice(-10)} live />}
      </div>
    </div>
  )
}

function HowMade({ m }) {
  const [open, setOpen] = useState(false)
  if (!m.activity?.length) return null
  return (
    <div className="howmade">
      <button className="link small" onClick={() => setOpen(!open)}>{open ? 'Hide' : 'How this answer was made'}{m.seconds ? ` · ${m.seconds}s` : ''}</button>
      {open && <ActivityList items={m.activity} />}
    </div>
  )
}

function Attachment({ a, onRemove }) {
  return (
    <div className="att">
      {a.kind === 'image'
        ? <img src={a.url} alt={a.name} />
        : <span className="att-icon">{a.kind === 'pdf' ? <FileText size={16} /> : <FileText size={16} />}</span>}
      <span className="att-name" title={a.name}>{a.name}</span>
      {a.uploading && <Loader2 size={13} className="spin" />}
      {onRemove && <button className="icon-btn ghost tiny-btn" onClick={onRemove} aria-label="Remove"><X size={12} /></button>}
    </div>
  )
}

function MaterialPicker({ onPick, onClose }) {
  const [data, setData] = useState(null)
  const [q, setQ] = useState('')
  const [sel, setSel] = useState(null)
  const [page, setPage] = useState(1)
  useEffect(() => { api('/api/materials/list').then(setData) }, [])
  const files = (data?.files || []).filter((f) => !q || f.rel.toLowerCase().includes(q.toLowerCase()))
  return (
    <Modal title="Attach a page from your materials" onClose={onClose} wide
      footer={<>
        <button className="btn ghost" onClick={onClose}>Cancel</button>
        <button className="btn primary" disabled={!sel} onClick={() => onPick(sel.rel, page)}>Attach page {page}</button>
      </>}>
      {!data?.root && data && <p className="muted">Choose a materials folder in the Study plan or Settings first.</p>}
      <div className="search"><Search size={14} /><input autoFocus placeholder="Filter files" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      <div className="mat-pick">
        <div className="picker-list">
          {files.map((f) => (
            <button key={f.rel} className={`picker-item ${sel?.rel === f.rel ? 'on' : ''}`} onClick={() => { setSel(f); setPage(1) }}>
              <FileText size={15} /> <span className="grow">{f.rel}</span> <span className="muted tiny">{f.pages} p.</span>
            </button>
          ))}
        </div>
        {sel && (
          <div className="mat-preview">
            <div className="row between">
              <b className="small">{sel.rel.split('/').pop()}</b>
              <div className="row">
                <button className="btn small" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹</button>
                <span className="small mono">{page} / {sel.pages}</span>
                <button className="btn small" disabled={page >= sel.pages} onClick={() => setPage(page + 1)}>›</button>
              </div>
            </div>
            <iframe title="preview" src={`/api/materials/raw?path=${encodeURIComponent(sel.rel)}#page=${page}&toolbar=0&view=FitH`} key={sel.rel + page} />
          </div>
        )}
      </div>
    </Modal>
  )
}

export default function ChatView({ chatId, firstMessage, onConsumedFirst, onChanged }) {
  const toast = useToast()
  const [chat, setChat] = useState(null)
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [atts, setAtts] = useState([])
  const [busy, setBusy] = useState(null) // { stage, elapsed, detail, rounds }
  const [drag, setDrag] = useState(false)
  const [matPicker, setMatPicker] = useState(false)
  const [settings, setSettings] = useState(null)
  const listRef = useRef(null)
  const taRef = useRef(null)
  const fileRef = useRef(null)
  const sentFirst = useRef(false)

  const [missing, setMissing] = useState(false)
  const [failed, setFailed] = useState(null)
  const load = useCallback(async () => {
    try {
      const c = await api(`/api/chats/${chatId}`)
      setChat(c.meta)
      setMessages(c.messages)
      setMissing(false)
      return c
    } catch (e) {
      setMissing(true)
      onChanged?.()
      return { messages: [] }
    }
  }, [chatId]) // eslint-disable-line

  const [catalog, setCatalog] = useState(null)
  useEffect(() => { api('/api/settings').then(setSettings); api('/api/models').then((r) => setCatalog(r.catalog)).catch(() => {}) }, [])
  useEffect(() => {
    load().then((c) => {
      if (c.running) { track(); return }
      const last = c.messages?.[c.messages.length - 1]
      if (last && last.role === 'user') setFailed(c.meta?.last_error || 'This answer was interrupted before it finished.')
      if (firstMessage && !sentFirst.current && c.messages.length === 0) {
        sentFirst.current = true
        onConsumedFirst?.()
        send(firstMessage, [])
      }
    })
  }, [chatId]) // eslint-disable-line

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  useEffect(() => {
    const ta = taRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 240) + 'px'
  }, [text])

  const addFiles = async (files) => {
    for (const f of files) {
      const temp = { id: 'tmp' + Math.random(), name: f.name || 'Screenshot', kind: f.type.startsWith('image/') ? 'image' : 'pdf', url: f.type.startsWith('image/') ? URL.createObjectURL(f) : '', uploading: true }
      setAtts((a) => [...a, temp])
      try {
        const named = f.name ? f : new File([f], `screenshot-${Date.now()}.png`, { type: f.type })
        const r = await upload(named)
        setAtts((a) => a.map((x) => (x.id === temp.id ? r : x)))
      } catch (e) {
        setAtts((a) => a.filter((x) => x.id !== temp.id))
        toast({ kind: 'error', text: `Could not attach ${f.name || 'image'}` })
      }
    }
  }

  const onPaste = (e) => {
    const files = [...(e.clipboardData?.files || [])]
    if (files.length) { e.preventDefault(); addFiles(files) }
  }

  const track = async () => {
    setBusy((b) => b || { stage: 'context', elapsed: 0, detail: '', rounds: 0, activity: [] })
    markBusy(true)
    setFailed(null)
    const res = await follow(`/api/chats/${chatId}/events`, (ev) => {
      if (ev.type === 'reconnecting') return setBusy((b) => (b ? { ...b, reconnecting: true } : b))
      setBusy((b) => {
        if (!b) return b
        const nb = { ...b, reconnecting: false }
        if (ev.type === 'status') Object.assign(nb, { stage: ev.stage, elapsed: ev.elapsed ?? b.elapsed, detail: ev.detail })
        if (ev.type === 'review' && ev.verdict === 'revise') nb.rounds = b.rounds + 1
        if (ev.type === 'activity') nb.activity = [...(b.activity || []), ev]
        return nb
      })
      if (ev.type === 'user_saved') onChanged?.()
    })
    const c = await load()
    setBusy(null)
    markBusy(false)
    if (res.error && c.messages?.length && c.messages[c.messages.length - 1].role === 'user') setFailed(res.error)
    else if (res.error) toast({ kind: 'error', title: 'The tutor could not answer', text: res.error, timeout: 10000 })
    taRef.current?.focus()
  }

  const send = async (t = text, a = atts) => {
    const body = (t || '').trim()
    if ((!body && a.length === 0) || busy || a.some((x) => x.uploading)) return
    setText(''); setAtts([])
    setMessages((m) => [...m, { role: 'user', content: body, attachments: a, ts: Date.now() / 1000 }])
    setBusy({ stage: 'context', elapsed: 0, detail: '', rounds: 0, activity: [] })
    try {
      await api(`/api/chats/${chatId}/messages`, { method: 'POST', body: { text: body, attachments: a.map(({ id, name, kind, url }) => ({ id, name, kind, url })) } })
    } catch (e) {
      // could not even start: give the text and attachments back so nothing is lost
      setBusy(null)
      setMessages((m) => m.slice(0, -1))
      setText(body); setAtts(a)
      toast({ kind: 'error', title: 'Not sent', text: /load failed|failed to fetch/i.test(e.message) ? 'Could not reach Scaffold. Check that it is running, then press Enter again.' : e.message, timeout: 10000 })
      return
    }
    track()
  }

  const retry = async () => {
    setFailed(null)
    try {
      await api(`/api/chats/${chatId}/retry`, { method: 'POST' })
      track()
    } catch (e) { setFailed(e.message) }
  }

  const toggleSetting = async (key) => {
    const s = await api('/api/settings', { method: 'PUT', body: { ...settings, [key]: !settings[key] } })
    setSettings(s)
  }

  const attachPage = async (file, page) => {
    setMatPicker(false)
    try {
      const r = await api('/api/materials/page', { method: 'POST', body: { file, page } })
      setAtts((a) => [...a, r])
    } catch (e) { toast({ kind: 'error', text: e.message }) }
  }

  if (missing) {
    return (
      <div className="center-col">
        <div className="card job-card">
          <h2>This chat doesn't exist anymore</h2>
          <p className="muted">It was deleted or moved. Pick another chat on the left, or start a new one.</p>
          <button className="btn primary" onClick={() => { window.location.hash = '/plan' }}>Back to my plan</button>
        </div>
      </div>
    )
  }

  const empty = messages.length === 0 && !busy
  const tutor = settings?.roles?.tutor

  return (
    <div className={`chat ${drag ? 'dragging' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
      onDragLeave={(e) => { if (e.currentTarget === e.target) setDrag(false) }}
      onDrop={(e) => { e.preventDefault(); setDrag(false); addFiles([...e.dataTransfer.files]) }}>
      <header className="chat-head">
        <div className="chat-title">
          <h2>{chat?.title || 'New chat'}</h2>
          {chat?.task && <span className="task-chip"><CalendarCheck size={13} /> From your plan</span>}
          {chat?.badge && <span className={`chat-badge ${/on$/.test(chat.badge) ? 'on' : ''}`}>Test run · {chat.badge}</span>}
        </div>
        {settings && (
          <div className="chat-toggles">
            <button className={`toggle ${settings.review ? 'on' : ''}`} onClick={() => toggleSetting('review')} title="A second agent checks every reply before you see it">
              <ShieldCheck size={14} /> Review {settings.review ? 'on' : 'off'}
            </button>
            <button className={`toggle ${settings.auto_notes ? 'on' : ''}`} onClick={() => toggleSetting('auto_notes')} title="Write notes automatically">
              <BookOpen size={14} /> Auto-notes {settings.auto_notes ? 'on' : 'off'}
            </button>
            {tutor && catalog && (
              <ModelPicker compact catalog={catalog} value={tutor} align="right"
                onChange={async (cfg) => { const s = await api('/api/settings', { method: 'PUT', body: { ...settings, roles: { ...settings.roles, tutor: cfg } } }); setSettings(s) }} />
            )}
          </div>
        )}
      </header>

      <div className="messages" ref={listRef}>
        {empty && (
          <div className="chat-empty">
            <h1>What are we studying?</h1>
            <Pitch />
            <div className="starter-grid">
              <button className="starter" onClick={() => taRef.current?.focus()}>
                <ClipboardPaste size={18} /><b>Paste a screenshot</b><span className="muted small">of an exam question. Press ⌘V in the box below.</span>
              </button>
              <button className="starter" onClick={() => setMatPicker(true)}>
                <Library size={18} /><b>Pick from your materials</b><span className="muted small">Attach any page of a past exam or slide deck.</span>
              </button>
              <button className="starter" onClick={() => { window.location.hash = '/plan' }}>
                <CalendarCheck size={18} /><b>Today's plan task</b><span className="muted small">Hit "Study this" on any task in your plan.</span>
              </button>
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.role === 'assistant' && <div className="avatar tutor"><Sparkles size={15} /></div>}
            <div className="bubble">
              {m.attachments?.length > 0 && (
                <div className="msg-atts">
                  {m.attachments.map((a) => a.kind === 'image'
                    ? <a key={a.id} href={a.url} target="_blank" rel="noreferrer"><img src={a.url} alt={a.name} /></a>
                    : <Attachment key={a.id} a={a} />)}
                </div>
              )}
              {m.content && <Markdown source={m.content} />}
              {m.role === 'assistant' && <ReviewBadge review={m.review} />}
              {m.role === 'assistant' && <HowMade m={m} />}
            </div>
          </div>
        ))}
        {busy && <Pending {...busy} />}
        {!busy && failed && (
          <div className="msg assistant">
            <div className="avatar warn-av"><Sparkles size={15} /></div>
            <div className="bubble failed">
              <b>The tutor didn't finish this answer.</b>
              <span className="muted small">{failed}</span>
              <div className="row"><button className="btn primary small" onClick={retry}>Try again</button>
                <a className="btn ghost small" href="#/settings/models">Check models</a></div>
            </div>
          </div>
        )}
      </div>

      <div className="composer-wrap">
        <div className="composer">
          {atts.length > 0 && <div className="atts">{atts.map((a) => <Attachment key={a.id} a={a} onRemove={() => setAtts((x) => x.filter((y) => y.id !== a.id))} />)}</div>}
          <textarea
            ref={taRef}
            rows={1}
            value={text}
            placeholder={busy ? 'The tutor is working…' : 'Ask, answer, or paste a screenshot. Math like x^2 is fine.'}
            onChange={(e) => setText(e.target.value)}
            onPaste={onPaste}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send() } }}
          />
          <div className="composer-bar">
            <div className="row">
              <button className="icon-btn ghost" title="Attach images or PDFs" onClick={() => fileRef.current?.click()}><Paperclip size={17} /></button>
              <button className="icon-btn ghost" title="Attach a page from your materials" onClick={() => setMatPicker(true)}><Library size={17} /></button>
              <span className="muted tiny hint"><ImageIcon size={12} /> Paste or drop screenshots · Shift+Enter for a new line</span>
            </div>
            <button className="send" onClick={() => send()} disabled={!!busy || (!text.trim() && atts.length === 0) || atts.some((a) => a.uploading)} aria-label="Send">
              {busy ? <Loader2 size={17} className="spin" /> : <ArrowUp size={17} />}
            </button>
          </div>
          <input ref={fileRef} type="file" multiple accept="image/*,.pdf,.md,.txt" hidden onChange={(e) => { addFiles([...e.target.files]); e.target.value = '' }} />
        </div>
      </div>
      {drag && <div className="drop-overlay"><ImageIcon size={28} /> Drop to attach</div>}
      {matPicker && <MaterialPicker onClose={() => setMatPicker(false)} onPick={attachPage} />}
    </div>
  )
}
