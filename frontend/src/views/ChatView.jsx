import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowUp, Paperclip, X, ShieldCheck, ShieldAlert, ChevronDown, Loader2, Check, Image as ImageIcon,
  FileText, BookOpen, ClipboardPaste, CalendarCheck, Sparkles, Search, Library, FolderOpen, Square,
  CornerDownRight, Clock3, Layers, Terminal, NotebookPen, MessageSquareReply,
} from 'lucide-react'
import { api, follow, setBusy as markBusy, upload } from '../api'
import Markdown from '../components/Markdown'
import { FolderPicker, Modal, Pitch, useToast } from '../components/ui'
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

/** Short reviewer/activity text with LaTeX, code and bold rendered inline. */
function InlineMd({ text }) {
  return <Markdown source={String(text || '')} className="inline-md" />
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
        {fixes > 0 && (review.student_note ? <InlineMd text={review.student_note} /> : <span>{`${fixes} fix${fixes > 1 ? 'es' : ''} before you saw it`}</span>)}
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
                  <li key={j}><span className={`issue-tag t-${is.type}`}>{ISSUE_LABEL[is.type] || is.type}</span> <InlineMd text={is.fix} /></li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const ACT_ICON = { context: '📚', draft: '✍️', tool: '🔎', review: '🛡️', issues: '↩︎', revise: '🔧', approved: '✓', build: '🗓️', update: '🗓️', done: '✓', compact: '🗜️' }

function ActivityList({ items, live }) {
  return (
    <ol className={`activity ${live ? 'live' : ''}`}>
      {items.map((a, i) => (
        <li key={i} className={`act act-${a.kind}`}>
          <span className="act-icon" aria-hidden="true">{ACT_ICON[a.kind] || '•'}</span>
          <div className="act-body">
            <InlineMd text={a.text} />
            {a.issues?.length > 0 && (
              <ul className="act-issues">
                {a.issues.map((is, j) => <li key={j}><span className="issue-tag">{is.label}</span> <InlineMd text={is.fix} /></li>)}
              </ul>
            )}
          </div>
          <span className="act-time mono">{a.t != null ? `${a.t}s` : ''}</span>
        </li>
      ))}
    </ol>
  )
}

const PLANNER_STAGES = [
  { id: 'context', label: 'Looking at your materials and plan' },
  { id: 'drafting', label: 'Planner is thinking' },
]

function Pending({ stage, elapsed, detail, rounds, activity = [], reconnecting, kind, steering, codex }) {
  const order = ['context', 'drafting', 'tool', 'reviewing', 'revising', 'building', 'compacting']
  const idx = order.indexOf(stage)
  const steps = stage === 'compacting' ? [{ id: 'compacting', label: codex ? 'Codex is compacting this chat' : 'Summarizing the conversation' }]
    : codex
    ? [{ id: 'drafting', label: kind === 'planner' ? 'Codex is working on your plan' : 'Codex is working in your chat' },
      ...(kind === 'planner' ? [] : [{ id: 'reviewing', label: 'Reviewer is checking' }])]
    : kind === 'planner' ? [...PLANNER_STAGES] : [...STAGES]
  if (kind === 'planner' && stage === 'building') steps.push({ id: 'building', label: 'Writing your plan files (this takes a few minutes)' })
  if (kind !== 'planner' && (stage === 'revising' || rounds > 0)) steps.push({ id: 'revising', label: 'Tutor is fixing what the reviewer found' })
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
        {steering && <div className="steer-note small"><CornerDownRight size={13} /> Steering: stopping here and continuing with “{steering}”</div>}
        {detail && <div className="muted small pdetail">{detail}</div>}
        {reconnecting && <div className="reconnect small"><Loader2 size={12} className="spin" /> Connection dropped. Reconnecting; the tutor keeps working on the server…</div>}
        {activity.length > 0 && <ActivityList items={activity.slice(-10)} live />}
      </div>
    </div>
  )
}

function MaterialsBar({ settings, needFolder, busy, onChosen }) {
  const toast = useToast()
  const [pick, setPick] = useState(false)
  const choose = async (path, label) => {
    setPick(false)
    try {
      const r = await api('/api/materials/scan', { method: 'POST', body: { path } })
      const s2 = await api('/api/settings')
      const n = r.courses.length
      onChosen(s2, label || `I chose my materials folder: ${r.path.split('/').pop()} (${n} course folder${n === 1 ? '' : 's'}).`)
    } catch (e) { toast({ kind: 'error', text: e.message }) }
  }
  if (!needFolder) {
    return (
      <div className="materials-bar">
        <FolderOpen size={14} /> <span className="mono small" title={settings.materials_path}>{settings.materials_path.split('/').slice(-2).join('/')}</span>
        <button className="link small" onClick={() => setPick(true)} disabled={busy}>Change folder</button>
        {pick && <FolderPicker initial={settings.materials_path} title="Choose your materials folder" onClose={() => setPick(false)} onPick={(p) => choose(p)} />}
      </div>
    )
  }
  return (
    <div className="folder-card">
      <div>
        <b>Where are your course materials?</b>
        <div className="muted small">A folder with one subfolder per course: past exams, solutions, slides.</div>
      </div>
      <div className="row">
        <button className="btn primary" onClick={() => setPick(true)} disabled={busy}><FolderOpen size={15} /> Choose folder</button>
      </div>
      {pick && <FolderPicker title="Choose your materials folder" onClose={() => setPick(false)} onPick={(p) => choose(p)} />}
    </div>
  )
}

const kfmt = (n) => (n >= 1000 ? `${Math.round(n / 1000)}k` : String(n))

/** How full the conversation's context is, and when it will be (or was) compacted. */
function ContextMeter({ ctx }) {
  if (!ctx?.window) return null
  const pct = Math.min(100, Math.round((100 * ctx.used) / ctx.window))
  const chars = ctx.unit === 'chars'
  const title = chars
    ? `This chat is ${pct}% of the way to compaction. At 100%, older messages are replaced by a summary so answers stay fast and focused.`
    : `Context: ${kfmt(ctx.used)} of ${kfmt(ctx.window)} tokens used. Codex compacts older turns automatically when it gets full.`
  return (
    <div className={`ctx-meter ${pct > 85 ? 'hot' : ''}`} title={title}>
      <Layers size={13} />
      <span className="ctx-bar"><span style={{ width: `${Math.max(4, pct)}%` }} /></span>
      <span className="tiny mono">{chars ? `${pct}%` : `${kfmt(ctx.used)}/${kfmt(ctx.window)}`}</span>
    </div>
  )
}

function CompactDivider({ text }) {
  return <div className="compact-divider"><span><Layers size={12} /> {text || 'Context compacted: older messages were summarized'}</span></div>
}

function QueueList({ queue, onRemove, onSendNow, busy }) {
  if (!queue?.length) return null
  return (
    <div className="queue">
      {queue.map((q, i) => (
        <div key={q.id} className="queue-item">
          <span className="queue-badge"><Clock3 size={12} /> {busy ? (i === 0 ? 'Next' : `#${i + 1}`) : 'Queued'}</span>
          <span className="queue-body" title={q.text}>{q.text || `${q.attachments?.length || 0} attachment(s)`}</span>
          <button className="queue-act" onClick={() => onSendNow(q.id)} title={busy ? 'Stop the current answer and continue with this message' : 'Send it now'}>
            <CornerDownRight size={12} /> {busy ? 'Steer now' : 'Send now'}
          </button>
          <button className="queue-x" onClick={() => onRemove(q.id)} aria-label="Remove from queue" title="Remove"><X size={13} /></button>
        </div>
      ))}
    </div>
  )
}

const NOTE_STATUS = { working: 'Notes agent is writing your notes…', reviewing: 'Notes reviewer is checking the change…', fixing: 'Fixing what the notes reviewer found…' }

/** What the course's Notes agent did after this answer, with a box to correct it. */
function NotesCard({ card, chatId, onUpdate }) {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const busy = NOTE_STATUS[card.status]
  const fixes = card.review?.verdict === 'revise' ? card.review.issues?.length || 0 : 0
  const send = async () => {
    if (!text.trim()) return
    setSending(true)
    try {
      const c = await api(`/api/chats/${chatId}/notes/${card.id}/feedback`, { method: 'POST', body: { text } })
      onUpdate(c); setText(''); setOpen(false)
    } catch (e) { toast({ kind: 'error', text: e.message }) }
    setSending(false)
  }
  return (
    <div className={`notes-card ${card.status}`}>
      <div className="notes-card-head">
        {busy ? <Loader2 size={14} className="spin" /> : <NotebookPen size={14} />}
        <span className="notes-card-title">{busy || (card.status === 'done' ? 'Notes updated' : card.status === 'nothing' ? 'No new notes needed' : 'Notes failed')}</span>
        {fixes > 0 && !busy && <span className="tiny muted">· reviewer fixed {fixes}</span>}
        {!busy && <button className="link small push-right" onClick={() => setOpen(!open)}><MessageSquareReply size={13} /> {card.status === 'nothing' ? 'Take notes anyway' : 'Correct'}</button>}
      </div>
      {!busy && card.summary && card.status !== 'nothing' && <div className="notes-summary">{card.summary}</div>}
      {card.files?.length > 0 && (
        <div className="notes-files">
          {card.files.map((f) => (
            <a key={f.path} className="note-chip" href={`#/notes/${encodeURIComponent(f.path)}`} title={f.path}>
              <FileText size={12} /> {f.path.split('/').pop().replace(/\.md$/, '')}
              <span className="tiny muted">{f.sections?.length ? f.sections.map((x) => x.heading).join(', ') : f.action}</span>
            </a>
          ))}
        </div>
      )}
      {card.corrections?.length > 0 && (
        <ul className="notes-corrections">{card.corrections.map((c, i) => <li key={i}><CornerDownRight size={11} /> {c.text}</li>)}</ul>
      )}
      {card.rules?.length > 0 && <div className="tiny muted">Saved for this course: {card.rules.join(' · ')}</div>}
      {open && (
        <div className="notes-feedback">
          <input autoFocus value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') send() }}
            placeholder={card.status === 'nothing' ? 'What should go in the notes?' : 'e.g. put the derivation before the example'} />
          <button className="btn small primary" onClick={send} disabled={!text.trim() || sending}>{sending ? <Loader2 size={13} className="spin" /> : 'Send'}</button>
        </div>
      )}
    </div>
  )
}

const COMMANDS = [
  { name: 'compact', hint: '', desc: 'Summarize this chat now, so answers stay fast and focused' },
  { name: 'notes', hint: '<what to write>', desc: "Ask this course's Notes agent, e.g. /notes add a summary of eigenvalues" },
  { name: 'review', hint: 'on | off', desc: 'Turn the Reviewer on or off' },
  { name: 'stop', hint: '', desc: 'Stop the current answer' },
]

/** The menu that opens when the message starts with "/". */
function SlashMenu({ text, onPick, active }) {
  const q = text.slice(1).split(/\s/)[0].toLowerCase()
  const items = COMMANDS.filter((c) => c.name.startsWith(q))
  if (!items.length || /\s/.test(text.trim()) && COMMANDS.some((c) => c.name === q)) return null
  return (
    <div className="slash-menu" role="listbox">
      <div className="slash-head">Commands</div>
      {items.map((c, i) => (
        <button key={c.name} className={`slash-item ${i === active ? 'on' : ''}`} onMouseDown={(e) => { e.preventDefault(); onPick(c) }}>
          <span className="slash-name">/{c.name}{c.hint && <span className="slash-hint"> {c.hint}</span>}</span>
          <span className="slash-desc">{c.desc}</span>
        </button>
      ))}
      <div className="slash-foot"><kbd>↑</kbd><kbd>↓</kbd> choose <kbd>↵</kbd> run <kbd>Tab</kbd> complete <kbd>Esc</kbd> close</div>
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
  const [queue, setQueue] = useState([])
  const [cards, setCards] = useState([])
  const upsertCard = (c) => setCards((cs) => [...cs.filter((x) => x.id !== c.id), c])
  const [ctx, setCtx] = useState(null)
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
      setQueue(c.queue || [])
      setCards(c.notes || [])
      setCtx(c.context || null)
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
    const h = (e) => { if (e.detail.chat === chatId) upsertCard(e.detail.card) }
    window.addEventListener('scaffold:notescard', h)
    return () => window.removeEventListener('scaffold:notescard', h)
  }, [chatId])

  // an answer started from another window (or the queue): follow it here too
  const tracking = useRef(false)
  useEffect(() => {
    const h = (e) => { if (e.detail === chatId && !tracking.current) { load(); track() } }
    window.addEventListener('scaffold:turn', h)
    return () => window.removeEventListener('scaffold:turn', h)
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
    if (tracking.current) return
    tracking.current = true
    try { await trackOnce() } finally { tracking.current = false }
  }
  const trackOnce = async () => {
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
        if (ev.type === 'steering') nb.steering = ev.text || 'your message'
        return nb
      })
      if (ev.type === 'queue') setQueue(ev.queue || [])
      if (ev.type === 'user_saved') { onChanged?.(); load() }
    })
    const c = await load()
    if (c.running) {
      // the next message (a steer or a queued one) already started: keep following it
      setBusy({ stage: 'context', elapsed: 0, detail: '', rounds: 0, activity: [] })
      return trackOnce()
    }
    setBusy(null)
    markBusy(false)
    if (res.error && c.messages?.length && c.messages[c.messages.length - 1].role === 'user') setFailed(res.error)
    else if (res.error) toast({ kind: 'error', title: 'The tutor could not answer', text: res.error, timeout: 10000 })
    taRef.current?.focus()
  }

  const [slashActive, setSlashActive] = useState(0)
  const runCommand = async (name, args) => {
    setText('')
    try {
      const r = await api(`/api/chats/${chatId}/command`, { method: 'POST', body: { name, args } })
      if (r.settings) setSettings(r.settings)
      if (r.card) setCards((cs) => [...cs.filter((x) => x.id !== r.card.id), r.card])
      if (r.message) toast({ text: r.message })
      if (r.started) { setBusy({ stage: 'compacting', elapsed: 0, detail: 'Compacting', rounds: 0, activity: [] }); track() }
    } catch (e) { toast({ kind: 'error', text: e.message }) }
  }

  const send = async (t = text, a = atts, mode = 'queue') => {
    const body = (t || '').trim()
    const cmd = body.match(/^\/(\w+)(?:\s+([\s\S]*))?$/)
    if (cmd && COMMANDS.some((c) => c.name === cmd[1].toLowerCase()) && a.length === 0) return runCommand(cmd[1].toLowerCase(), cmd[2] || '')
    if ((!body && a.length === 0) || a.some((x) => x.uploading)) return
    if (busy) {
      // the AI is still answering: queue it (Enter) or steer the current answer (⌘/Ctrl+Enter)
      setText(''); setAtts([])
      try {
        const r = await api(`/api/chats/${chatId}/messages`, { method: 'POST', body: { mode, text: body, attachments: a.map(({ id, name, kind, url }) => ({ id, name, kind, url })) } })
        if (r.queue) setQueue(r.queue)
        if (r.steered) setBusy((b) => (b ? { ...b, steering: body || 'your attachment' } : b))
      } catch (e) {
        setText(body); setAtts(a)
        toast({ kind: 'error', title: 'Not sent', text: e.message })
      }
      return
    }
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

  const stop = async () => { try { await api(`/api/chats/${chatId}/stop`, { method: 'POST' }) } catch (e) { toast({ kind: 'error', text: e.message }) } }
  const unqueue = async (qid) => { const r = await api(`/api/chats/${chatId}/queue/${qid}`, { method: 'DELETE' }); setQueue(r.queue) }
  const sendQueuedNow = async (qid) => {
    const r = await api(`/api/chats/${chatId}/queue/${qid}/send`, { method: 'POST' })
    setQueue(r.queue || [])
    if (r.steered) setBusy((b) => (b ? { ...b, steering: 'your queued message' } : b))
    else if (!busy) track()
  }
  const setCodexModel = async (cfg) => {
    const meta = await api(`/api/chats/${chatId}/codex`, { method: 'POST', body: { model: cfg.model, effort: cfg.effort } })
    setChat(meta)
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

  const empty = messages.length === 0 && !busy && chat?.kind !== 'planner'
  const needFolder = chat?.kind === 'planner' && settings && !settings.materials_path
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
          {chat?.codex && <span className="codex-chip" title={`Linked to your Codex chat. Folder: ${chat.codex.cwd}`}><Terminal size={12} /> Codex chat</span>}
          <ContextMeter ctx={ctx} />
        </div>
        {settings && chat?.kind === 'planner' && (
          <div className="chat-toggles">
            {catalog && chat?.codex && (
              <ModelPicker compact catalog={{ codex: catalog.codex }} value={{ provider: 'codex', model: chat.codex.model, effort: chat.codex.effort }} align="right" onChange={setCodexModel} />
            )}
            {catalog && !chat?.codex && settings.roles?.planner && (
              <ModelPicker compact catalog={catalog} value={settings.roles.planner} align="right"
                onChange={async (cfg) => { const s2 = await api('/api/settings', { method: 'PUT', body: { ...settings, roles: { ...settings.roles, planner: cfg } } }); setSettings(s2) }} />
            )}
          </div>
        )}
        {settings && chat?.kind !== 'planner' && (
          <div className="chat-toggles">
            <button className={`toggle ${settings.review ? 'on' : ''}`} onClick={() => toggleSetting('review')} title="A second agent checks every reply before you see it">
              <ShieldCheck size={14} /> Review {settings.review ? 'on' : 'off'}
            </button>
            <button className={`toggle ${settings.auto_notes ? 'on' : ''}`} onClick={() => toggleSetting('auto_notes')} title="Write notes automatically">
              <BookOpen size={14} /> Auto-notes {settings.auto_notes ? 'on' : 'off'}
            </button>
            {catalog && chat?.codex && (
              <ModelPicker compact catalog={{ codex: catalog.codex }} value={{ provider: 'codex', model: chat.codex.model, effort: chat.codex.effort }} align="right" onChange={setCodexModel} />
            )}
            {tutor && catalog && !chat?.codex && (
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
        {chat?.kind === 'planner' && messages.length <= 1 && <Pitch />}
        {messages.map((m, i) => m.role === 'event' ? <CompactDivider key={i} text={m.content} /> : (<Fragment key={i}>
          {chat?.codex && (() => {
            // one divider where the conversation moves between the Codex app and Scaffold
            const prev = messages.slice(0, i).reverse().find((x) => x.role !== 'event')
            const here = m.source === 'codex' ? 'codex' : 'scaffold'
            const before = prev ? (prev.source === 'codex' ? 'codex' : 'scaffold') : null
            if (here === before || (!prev && here === 'codex')) return null
            return <div className="source-divider"><span>{here === 'codex' ? <><Terminal size={12} /> In the Codex app</> : <><Sparkles size={12} /> Continued in Scaffold</>}</span></div>
          })()}
          <div className={`msg ${m.role}`}>
            {m.role === 'assistant' && <div className="avatar tutor"><Sparkles size={15} /></div>}
            <div className="bubble">
              {m.attachments?.length > 0 && (
                <div className="msg-atts">
                  {m.attachments.map((a) => a.kind === 'image'
                    ? <a key={a.id} href={a.url} target="_blank" rel="noreferrer"><img src={a.url} alt={a.name} /></a>
                    : <Attachment key={a.id} a={a} />)}
                </div>
              )}
              {m.role === 'user' && m.steer && <div className="steer-tag tiny"><CornerDownRight size={11} /> Steered while answering</div>}
              {m.role === 'assistant' && m.compacted && <div className="steer-tag tiny"><Layers size={11} /> Context was compacted for this answer</div>}
              {m.content && <Markdown source={m.content} />}

              {m.role === 'assistant' && m.plan_link && (
                <button className="btn primary small plan-link" onClick={() => { window.location.hash = '/plan'; window.dispatchEvent(new Event('scaffold:openplan')) }}>
                  <CalendarCheck size={14} /> Open my study plan
                </button>
              )}
              {m.role === 'assistant' && chat?.kind !== 'planner' && m.source !== 'codex' && <ReviewBadge review={m.review} />}
              {m.role === 'assistant' && <HowMade m={m} />}
              {m.role === 'assistant' && cards.filter((c) => c.msg_ts === m.ts).map((c) => <NotesCard key={c.id} card={c} chatId={chatId} onUpdate={upsertCard} />)}
            </div>
          </div>
        </Fragment>))}
        {cards.filter((c) => !messages.some((m) => m.ts === c.msg_ts)).map((c) => <NotesCard key={c.id} card={c} chatId={chatId} onUpdate={upsertCard} />)}
        {busy && <Pending {...busy} kind={chat?.kind} codex={!!chat?.codex} />}
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
        {chat?.kind === 'planner' && settings && (
          <MaterialsBar settings={settings} needFolder={needFolder} busy={!!busy}
            onChosen={async (s2, msg) => { setSettings(s2); send(msg, []) }} />
        )}
        <div className="composer-dock">
        {text.startsWith('/') && <SlashMenu text={text} active={slashActive} onPick={(c) => { if (c.hint) { setText(`/${c.name} `); taRef.current?.focus() } else runCommand(c.name, '') }} />}
        <div className={`composer ${busy ? 'is-busy' : ''}`}>
          <QueueList queue={queue} busy={!!busy} onRemove={unqueue} onSendNow={sendQueuedNow} />
          {atts.length > 0 && <div className="atts">{atts.map((a) => <Attachment key={a.id} a={a} onRemove={() => setAtts((x) => x.filter((y) => y.id !== a.id))} />)}</div>}
          <textarea
            ref={taRef}
            rows={1}
            value={text}
            placeholder={busy ? 'Add a follow-up… (↵ queues it, ⌘↵ steers now)' : chat?.kind === 'planner' ? (needFolder ? 'Choose your materials folder first, or just say hi' : 'Answer the planner, or tell it how your studying went…') : 'Ask, answer, or paste a screenshot. Math like x^2 is fine.'}
            onChange={(e) => { setText(e.target.value); setSlashActive(0) }}
            onPaste={onPaste}
            onKeyDown={(e) => {
              const menu = text.startsWith('/') && !/\s/.test(text) ? COMMANDS.filter((c) => c.name.startsWith(text.slice(1).toLowerCase())) : []
              if (menu.length && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
                e.preventDefault(); setSlashActive((i) => (i + (e.key === 'ArrowDown' ? 1 : menu.length - 1)) % menu.length); return
              }
              if (menu.length && (e.key === 'Tab' || (e.key === 'Enter' && text.slice(1).toLowerCase() !== menu[slashActive]?.name))) {
                e.preventDefault()
                const c = menu[Math.min(slashActive, menu.length - 1)]
                if (c.hint || e.key === 'Tab') setText(`/${c.name} `); else runCommand(c.name, '')
                return
              }
              if (e.key === 'Escape' && text.startsWith('/')) { e.preventDefault(); setText(''); return }
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                send(text, atts, busy && (e.metaKey || e.ctrlKey) ? 'steer' : 'queue')
              }
            }}
          />
          <div className="composer-bar">
            <div className="composer-tools">
              <button className="tool-btn" title="Attach images, PDFs or text files (or paste / drop them)" onClick={() => fileRef.current?.click()}><Paperclip size={16} /></button>
              <button className="tool-btn" title="Attach a page from your materials" onClick={() => setMatPicker(true)}><Library size={16} /></button>
            </div>
            <div className="composer-status">
              {busy
                ? <><span className="live-dot" /> {chat?.codex ? 'Codex is answering' : chat?.kind === 'planner' ? 'The planner is working' : 'The tutor is answering'} · <kbd>↵</kbd> queue · <kbd>⌘↵</kbd> steer</>
                : text ? <><kbd>⇧↵</kbd> new line</>
                  : <><kbd>/</kbd> commands · paste or drop screenshots</>}
            </div>
            <div className="send-group">
              {busy && (text.trim() || atts.length > 0) && (
                <button className="steer-btn" onClick={() => send(text, atts, 'steer')} title="Stop the current answer and continue with this message (⌘↵)">
                  <CornerDownRight size={14} /> Steer
                </button>
              )}
              {busy && !text.trim() && atts.length === 0 ? (
                <button className="send stop" onClick={stop} aria-label="Stop" title="Stop this answer"><Square size={11} fill="currentColor" /></button>
              ) : (
                <button className="send" onClick={() => send(text, atts, 'queue')} disabled={(!text.trim() && atts.length === 0) || atts.some((a) => a.uploading)}
                  aria-label={busy ? 'Queue' : 'Send'} title={busy ? 'Queue: send when this answer is done (↵)' : 'Send (↵)'}>
                  {busy ? <Clock3 size={15} /> : <ArrowUp size={16} />}
                </button>
              )}
            </div>
          </div>
          <input ref={fileRef} type="file" multiple accept="image/*,.pdf,.md,.txt,.csv,.tex,.py,.java,.c,.cpp,.sql,.json" hidden onChange={(e) => { addFiles([...e.target.files]); e.target.value = '' }} />
        </div>
        </div>
      </div>
      {drag && <div className="drop-overlay"><ImageIcon size={28} /> Drop to attach</div>}
      {matPicker && <MaterialPicker onClose={() => setMatPicker(false)} onPick={attachPage} />}
    </div>
  )
}
