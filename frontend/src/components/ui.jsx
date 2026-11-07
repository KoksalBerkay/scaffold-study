import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { Folder, ChevronUp, X, Check, AlertTriangle, Info, Loader2, CalendarCheck, GraduationCap, ShieldCheck, NotebookText, ChevronRight } from 'lucide-react'
import { api } from '../api'

/* ---------- Toasts ---------- */
const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const push = useCallback((t) => {
    const id = Math.random().toString(36).slice(2)
    const toast = { id, kind: 'info', timeout: 5000, ...(typeof t === 'string' ? { text: t } : t) }
    setToasts((ts) => [...ts, toast])
    if (toast.timeout) setTimeout(() => setToasts((ts) => ts.filter((x) => x.id !== id)), toast.timeout)
  }, [])
  const close = (id) => setToasts((ts) => ts.filter((x) => x.id !== id))
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>
            <span className="toast-icon">
              {t.kind === 'success' ? <Check size={16} /> : t.kind === 'error' ? <AlertTriangle size={16} /> : <Info size={16} />}
            </span>
            <div className="toast-text">
              {t.title && <strong>{t.title}</strong>}
              <span>{t.text}</span>
              {t.action && <button className="link" onClick={() => { t.action.onClick(); close(t.id) }}>{t.action.label}</button>}
            </div>
            <button className="icon-btn ghost" onClick={() => close(t.id)} aria-label="Dismiss"><X size={14} /></button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

/* ---------- Modal ---------- */
export function Modal({ title, onClose, children, footer, wide }) {
  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-label={title}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn ghost" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}

/* ---------- Folder picker ---------- */
export function FolderPicker({ initial, onPick, onClose, title = 'Choose a folder' }) {
  const [data, setData] = useState(null)
  const [path, setPath] = useState(initial || '')
  const [err, setErr] = useState('')
  const load = useCallback(async (p) => {
    try {
      setErr('')
      const d = await api(`/api/fs/browse?path=${encodeURIComponent(p || '')}`)
      setData(d)
      setPath(d.path)
    } catch (e) { setErr(e.message) }
  }, [])
  useEffect(() => { load(initial || '') }, [initial, load])
  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={<>
        <button className="btn ghost" onClick={onClose}>Cancel</button>
        <button className="btn primary" onClick={() => onPick(path)} disabled={!path}>Use this folder</button>
      </>}
    >
      <div className="picker-path">
        <input value={path} onChange={(e) => setPath(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && load(path)} spellCheck={false} />
        <button className="btn" onClick={() => load(path)}>Go</button>
      </div>
      {data?.shortcuts?.length > 0 && (
        <div className="chips">
          {data.shortcuts.map((s) => <button key={s.path} className="chip" onClick={() => load(s.path)}>{s.name}</button>)}
        </div>
      )}
      {err && <p className="error-text">{err}</p>}
      <div className="picker-list">
        {data?.parent && (
          <button className="picker-item" onClick={() => load(data.parent)}><ChevronUp size={16} /> Up one level</button>
        )}
        {data?.dirs.map((d) => (
          <button key={d.path} className="picker-item" onClick={() => load(d.path)}><Folder size={16} /> {d.name}</button>
        ))}
        {data && data.dirs.length === 0 && <p className="muted small pad">No subfolders here.</p>}
      </div>
    </Modal>
  )
}

/* ---------- Progress for long AI jobs ---------- */
export function JobProgress({ steps, current, elapsed, detail }) {
  return (
    <div className="job">
      {steps.map((s, i) => {
        const state = i < current ? 'done' : i === current ? 'active' : 'todo'
        return (
          <div key={s} className={`job-step ${state}`}>
            <span className="job-dot">
              {state === 'done' ? <Check size={13} /> : state === 'active' ? <Loader2 size={13} className="spin" /> : null}
            </span>
            <span>{s}</span>
            {state === 'active' && elapsed != null && <span className="muted small mono">{elapsed}s</span>}
          </div>
        )
      })}
      {detail && <p className="muted small job-detail">{detail}</p>}
    </div>
  )
}

export function Segmented({ options, value, onChange, small }) {
  return (
    <div className={`segmented ${small ? 'small' : ''}`} role="radiogroup">
      {options.map((o) => {
        const v = typeof o === 'string' ? o : o.value
        const label = typeof o === 'string' ? o : o.label
        return (
          <button key={v} role="radio" aria-checked={value === v} className={value === v ? 'on' : ''} onClick={() => onChange(v)}>
            {label}
          </button>
        )
      })}
    </div>
  )
}

/* ---------- Two-sentence pitch ---------- */
const FLOW = [
  { icon: CalendarCheck, label: 'Plan' },
  { icon: GraduationCap, label: 'Teach' },
  { icon: ShieldCheck, label: 'Review' },
  { icon: NotebookText, label: 'Notes' },
]
export function Pitch({ compact }) {
  return (
    <div className={`pitch ${compact ? 'compact' : ''}`}>
      <div className="pitch-flow" aria-hidden="true">
        {FLOW.map((f, i) => (
          <span key={f.label} className="pitch-step">
            <f.icon size={14} /> {f.label}
            {i < FLOW.length - 1 && <ChevronRight size={13} className="pitch-arrow" />}
          </span>
        ))}
      </div>
      <p>
        Scaffold <b>plans your semester from your real past exams</b> and <b>teaches you step by step</b>, without handing you the answer.
        {' '}A second AI <b>reviews every lesson before you see it</b>, and everything you learn becomes <b>clean notes you keep</b>.
      </p>
    </div>
  )
}
