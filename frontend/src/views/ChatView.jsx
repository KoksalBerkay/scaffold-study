import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowUp, Paperclip, X, ShieldCheck, ShieldAlert, ChevronDown, Loader2, Check, Image as ImageIcon,
  FileText, BookOpen, ClipboardPaste, CalendarCheck, Sparkles, Search, Library,
} from 'lucide-react'
import { api, stream, upload } from '../api'
import Markdown from '../components/Markdown'
import { Modal, Pitch, useToast } from '../components/ui'

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

function Pending({ stage, elapsed, detail, rounds }) {
  const order = ['context', 'drafting', 'tool', 'reviewing', 'revising']
  const idx = order.indexOf(stage)
  const revising = stage === 'revising' || rounds > 0
  const steps = [...STAGES]
  if (revising) steps.push({ id: 'revising', label: 'Tutor is fixing what the reviewer found' })
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
      </div>
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

  const load = useCallback(async () => {
    const c = await api(`/api/chats/${chatId}`)
    setChat(c.meta)
    setMessages(c.messages)
    return c
  }, [chatId])

  useEffect(() => { api('/api/settings').then(setSettings) }, [])
  useEffect(() => {
    load().then((c) => {
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

  const send = async (t = text, a = atts) => {
    const body = (t || '').trim()
    if ((!body && a.length === 0) || busy || a.some((x) => x.uploading)) return
    setText(''); setAtts([])
    const userMsg = { role: 'user', content: body, attachments: a, ts: Date.now() / 1000 }
    setMessages((m) => [...m, userMsg])
    setBusy({ stage: 'context', elapsed: 0, detail: '', rounds: 0 })
    try {
      await stream(`/api/chats/${chatId}/messages`, { text: body, attachments: a.map(({ id, name, kind, url }) => ({ id, name, kind, url })) }, (ev) => {
        if (ev.type === 'status') setBusy((b) => ({ ...b, stage: ev.stage, elapsed: ev.elapsed ?? b?.elapsed, detail: ev.detail }))
        if (ev.type === 'review') setBusy((b) => ({ ...b, rounds: b.rounds + (ev.verdict === 'revise' ? 1 : 0) }))
        if (ev.type === 'message') setMessages((m) => [...m, ev.message])
        if (ev.type === 'user_saved') onChanged?.()
      })
    } catch (e) {
      toast({ kind: 'error', title: 'The tutor could not answer', text: e.message, timeout: 10000 })
    }
    setBusy(null)
    taRef.current?.focus()
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
            {tutor && <a className="model-pill big" href="#/settings/models" title="Change models">{tutor.model || tutor.provider} · {tutor.effort}</a>}
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
            </div>
          </div>
        ))}
        {busy && <Pending {...busy} />}
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
