import { useEffect, useMemo, useRef, useState } from 'react'
import {
  FolderOpen, CalendarDays, Clock, Sparkles, ArrowRight, ArrowLeft, RefreshCw, PencilLine,
  NotebookPen, Play, BookOpen, FileText, Timer, ListChecks, Check, MessageSquare,
} from 'lucide-react'
import { api, apiRetry, follow, setBusy } from '../api'
import Markdown, { splitFrontmatter } from '../components/Markdown'
import TodayCard from '../components/TodayCard'
import ChatView from './ChatView'
import { FolderPicker, JobProgress, Modal, Pitch, Segmented, useToast } from '../components/ui'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const CONFIDENCE = [
  { value: 'never seen it', label: 'New to me' },
  { value: 'partly known', label: 'Partly known' },
  { value: 'revising', label: 'Revising' },
]
const PREF_CHIPS = [
  'Past exams first, newest to oldest.',
  'Two sessions a day with a break between.',
  'Keep Sunday free.',
  'I work slowly on proofs and derivations.',
  'Start with the course whose exam comes first.',
  'Mix courses within a day.',
]
const KIND_LABEL = { exam: 'exams', solution: 'solutions', slides: 'slides', exercises: 'exercises', notes: 'notes', other: 'other' }
const TABS = [
  { id: 'Quick Plan', label: 'This week', icon: ListChecks },
  { id: 'Study Plan', label: 'Full plan', icon: CalendarDays },
  { id: 'Time Estimates', label: 'Time estimates', icon: Timer },
  { id: 'Context', label: 'Context', icon: FileText },
]

function isoDate(d) { return d.toISOString().slice(0, 10) }
function addDays(iso, n) { const d = new Date(iso); d.setDate(d.getDate() + n); return isoDate(d) }

/* ================= Wizard ================= */
function Wizard({ initial, onGenerate, onCancel, onDemo }) {
  const toast = useToast()
  const [step, setStep] = useState(0)
  const [picker, setPicker] = useState(false)
  const [scan, setScan] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [s, setS] = useState(() => initial || {
    materials_path: '', courses: [], start: isoDate(new Date()), end: '', hours_per_day: 3,
    days: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], session_minutes: 90, preferences: '',
  })
  const set = (patch) => setS((x) => ({ ...x, ...patch }))

  const doScan = async (path) => {
    setScanning(true)
    try {
      const r = await api('/api/materials/scan', { method: 'POST', body: { path } })
      setScan(r)
      const prev = Object.fromEntries((s.courses || []).map((c) => [c.name, c]))
      set({
        materials_path: r.path,
        courses: r.courses.map((c) => prev[c.name] || { name: c.name, included: true, exam_date: '', credits: '', confidence: 'never seen it', note: '' }),
      })
    } catch (e) { toast({ kind: 'error', text: e.message }) }
    setScanning(false)
  }
  useEffect(() => { if (s.materials_path) doScan(s.materials_path) }, []) // eslint-disable-line

  const included = s.courses.filter((c) => c.included)
  const earliestExam = included.map((c) => c.exam_date).filter(Boolean).sort()[0]
  useEffect(() => {
    if (step === 2 && !s.end) set({ end: earliestExam ? addDays(earliestExam, -1) : addDays(s.start, 56) })
  }, [step]) // eslint-disable-line

  const weeklyHours = (s.hours_per_day * s.days.length).toFixed(1).replace('.0', '')
  const steps = ['Materials', 'Courses', 'Time', 'Preferences']
  const canNext = [!!scan && included.length > 0, included.length > 0, s.start && s.end && s.days.length > 0, true][step]

  const updateCourse = (i, patch) => set({ courses: s.courses.map((c, j) => (j === i ? { ...c, ...patch } : c)) })

  return (
    <div className="wizard">
      <div className="wizard-head">
        <Pitch />
        <h1>Let's build a plan you can actually follow.</h1>
        <p className="muted">The planner reads every file in your materials, estimates the time each question really takes, and writes your plan as notes you keep.</p>
      </div>

      <ol className="stepper">
        {steps.map((name, i) => (
          <li key={name} className={i === step ? 'active' : i < step ? 'done' : ''}>
            <button onClick={() => i < step && setStep(i)} disabled={i > step}>
              <span className="num">{i < step ? <Check size={13} /> : i + 1}</span>{name}
            </button>
          </li>
        ))}
      </ol>

      <div className="card wizard-card">
        {step === 0 && (
          <div className="stack">
            <h2><FolderOpen size={20} /> Where are your study materials?</h2>
            <p className="muted">Pick one folder with <b>one subfolder per course</b>. Past exams, solutions, slides, exercise sheets, screenshots. PDFs, images and markdown all work.</p>
            <div className="folder-row">
              <div className={`folder-path ${s.materials_path ? '' : 'empty'}`}>{s.materials_path || 'No folder selected'}</div>
              <button className="btn primary" onClick={() => setPicker(true)}><FolderOpen size={16} /> {s.materials_path ? 'Change' : 'Choose folder'}</button>
            </div>
            {!s.materials_path && onDemo && (
              <p className="muted small">No materials at hand? <button className="link" onClick={onDemo}>Load the demo semester</button> with a ready-made plan and notes.</p>
            )}
            {scanning && <p className="muted small">Scanning…</p>}
            {scan && (
              <div className="course-grid">
                {scan.courses.map((c) => (
                  <div key={c.name} className="course-tile">
                    <div className="course-name"><BookOpen size={15} /> {c.name}</div>
                    <div className="muted small">{c.n_files} files</div>
                    <div className="chips tight">
                      {Object.entries(c.counts).map(([k, n]) => <span key={k} className={`tag kind-${k}`}>{n} {KIND_LABEL[k] || k}</span>)}
                    </div>
                  </div>
                ))}
                {scan.courses.length === 0 && <p className="muted">No supported files found in this folder.</p>}
              </div>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="stack">
            <h2><BookOpen size={20} /> Your courses</h2>
            <p className="muted">Exam dates drive the plan. Leave a date empty if you don't know it yet. The plan will say so instead of guessing.</p>
            <div className="course-rows">
              {s.courses.map((c, i) => (
                <div key={c.name} className={`course-row ${c.included ? '' : 'off'}`}>
                  <label className="switch">
                    <input type="checkbox" checked={c.included} onChange={(e) => updateCourse(i, { included: e.target.checked })} />
                    <span />
                  </label>
                  <div className="course-row-name">{c.name}</div>
                  <label className="field compact">
                    <span>Exam date</span>
                    <input type="date" value={c.exam_date} onChange={(e) => updateCourse(i, { exam_date: e.target.value })} disabled={!c.included} />
                  </label>
                  <label className="field compact narrow">
                    <span>Credits</span>
                    <input type="number" min="0" max="30" value={c.credits} placeholder="?" onChange={(e) => updateCourse(i, { credits: e.target.value })} disabled={!c.included} />
                  </label>
                  <div className="field compact">
                    <span>How well do you know it?</span>
                    <Segmented small options={CONFIDENCE} value={c.confidence} onChange={(v) => updateCourse(i, { confidence: v })} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="stack">
            <h2><Clock size={20} /> Your time</h2>
            <div className="grid-2">
              <label className="field"><span>Start</span><input type="date" value={s.start} onChange={(e) => set({ start: e.target.value })} /></label>
              <label className="field"><span>End {earliestExam && <em className="muted">(first exam {earliestExam})</em>}</span><input type="date" value={s.end} onChange={(e) => set({ end: e.target.value })} /></label>
            </div>
            <div className="field">
              <span>Hours per study day: <b>{s.hours_per_day} h</b></span>
              <input type="range" min="0.5" max="10" step="0.5" value={s.hours_per_day} onChange={(e) => set({ hours_per_day: Number(e.target.value) })} />
            </div>
            <div className="field">
              <span>Study days</span>
              <div className="day-picker">
                {DAYS.map((d) => (
                  <button key={d} className={s.days.includes(d) ? 'on' : ''} onClick={() => set({ days: s.days.includes(d) ? s.days.filter((x) => x !== d) : DAYS.filter((x) => s.days.includes(x) || x === d) })}>{d}</button>
                ))}
              </div>
            </div>
            <div className="field">
              <span>Typical session</span>
              <Segmented options={[45, 60, 90, 120].map((m) => ({ value: m, label: `${m} min` }))} value={s.session_minutes} onChange={(v) => set({ session_minutes: v })} />
            </div>
            <div className="callout"><Sparkles size={16} /> That's <b>{weeklyHours} hours a week</b> across {included.length} course{included.length === 1 ? '' : 's'}.</div>
          </div>
        )}

        {step === 3 && (
          <div className="stack">
            <h2><NotebookPen size={20} /> Anything the planner should know?</h2>
            <p className="muted">Optional. Write it the way you'd tell a friend. Your preferences override the planner's defaults.</p>
            <textarea rows={5} value={s.preferences} onChange={(e) => set({ preferences: e.target.value })} placeholder="e.g. I learn best from past exams. I have a lab every Tuesday afternoon." />
            <div className="chips">
              {PREF_CHIPS.map((p) => (
                <button key={p} className="chip" onClick={() => set({ preferences: (s.preferences ? s.preferences.trim() + ' ' : '') + p })}>+ {p}</button>
              ))}
            </div>
            <div className="summary-box">
              <div><span className="muted">Courses</span><b>{included.map((c) => c.name).join(', ')}</b></div>
              <div><span className="muted">Period</span><b>{s.start} → {s.end}</b></div>
              <div><span className="muted">Time</span><b>{s.hours_per_day} h × {s.days.length} days = {weeklyHours} h/week</b></div>
            </div>
          </div>
        )}
      </div>

      <div className="wizard-nav">
        {step > 0 ? <button className="btn ghost" onClick={() => setStep(step - 1)}><ArrowLeft size={16} /> Back</button> : (onCancel ? <button className="btn ghost" onClick={onCancel}>Cancel</button> : <span />)}
        {step < 3
          ? <button className="btn primary" disabled={!canNext} onClick={() => setStep(step + 1)}>Continue <ArrowRight size={16} /></button>
          : <button className="btn primary big" onClick={() => onGenerate(s)}><Sparkles size={16} /> Build my plan</button>}
      </div>

      {picker && (
        <FolderPicker initial={s.materials_path} title="Choose your materials folder" onClose={() => setPicker(false)}
          onPick={(p) => { setPicker(false); doScan(p) }} />
      )}
    </div>
  )
}

/* ================= Plan ================= */
function weekProgress(src) {
  const done = (src.match(/^\s*[-*] \[[xX]\]/gm) || []).length
  const all = (src.match(/^\s*[-*] \[[ xX]\]/gm) || []).length
  return { done, all }
}

export default function PlanView({ onStudy }) {
  const toast = useToast()
  const [state, setState] = useState(null)
  const [mode, setMode] = useState('view') // view | wizard | generating
  const [tab, setTab] = useState('Quick Plan')
  const [job, setJob] = useState(null)
  const [logOpen, setLogOpen] = useState(false)
  const [logText, setLogText] = useState('')

  const [loadErr, setLoadErr] = useState(null)
  const load = async () => {
    try {
      const r = await apiRetry('/api/planner', { onRetry: (n) => setLoadErr(n) })
      setLoadErr(null)
      setState(r)
      return r
    } catch (e) {
      setLoadErr('failed')
      return { files: {} }
    }
  }
  const hasPlanRef = useRef(false)
  // stop following the planner job when this page closes (it keeps running on the server)
  const aborter = useRef(null)
  useEffect(() => { const ac = new AbortController(); aborter.current = ac; return () => ac.abort() }, [])
  useEffect(() => {
    const refresh = () => { if (hasPlanRef.current) load() } // live refresh of an existing plan; never yank the user out of the planning chat
    const open = () => load()
    window.addEventListener('scaffold:plan', refresh)
    window.addEventListener('scaffold:openplan', open)
    return () => { window.removeEventListener('scaffold:plan', refresh); window.removeEventListener('scaffold:openplan', open) }
  }, []) // eslint-disable-line
  useEffect(() => { api('/api/planchat').catch(() => {}); load().then((r) => { if (r.running) watch(['Reading your materials', 'Thinking it through and scheduling', 'Writing your plan'], 'Your plan is ready.') }) }, []) // eslint-disable-line

  const hasPlan = state && Object.keys(state.files || {}).length > 0
  hasPlanRef.current = !!hasPlan
  const allTabs = [...TABS, ...Object.keys(state?.extras || {}).map((n) => ({ id: n, label: n, icon: FileText, extra: true }))]
  const current = state?.files?.[tab] ?? state?.extras?.[tab] ?? ''
  const { body, meta, offset } = useMemo(() => splitFrontmatter(current), [current])
  const progress = useMemo(() => weekProgress(state?.files?.['Quick Plan'] || ''), [state])

  const watch = async (steps, doneMsg) => {
    setMode('generating')
    setJob((j) => j || { steps, current: 0, elapsed: 0, detail: '' })
    setBusy(true)
    const signal = aborter.current?.signal
    const res = await follow('/api/planner/events', (ev) => {
      if (ev.type === 'restart') return setJob((j) => ({ ...j, current: 0, elapsed: 0, detail: '' }))
      if (ev.type === 'reconnecting') return setJob((j) => ({ ...j, detail: 'Connection dropped. Reconnecting; the planner keeps working on the server…' }))
      if (ev.type === 'status') setJob((j) => ({ ...j, current: ev.stage === 'scan' ? 0 : 1, elapsed: ev.elapsed, detail: ev.detail }))
      if (ev.type === 'done') setJob((j) => ({ ...j, current: j.steps.length }))
    }, { signal })
    setBusy(false)
    if (signal?.aborted) return
    const st = await load()
    if (res.ok) {
      setTab('Quick Plan'); setMode('view')
      toast({ kind: 'success', text: doneMsg })
    } else if (!res.idle) {
      toast({ kind: 'error', title: 'The planner stopped', text: res.error || 'Unknown error', timeout: 12000 })
      setMode(Object.keys(st.files || {}).length ? 'view' : 'wizard')
    } else {
      setMode(Object.keys(st.files || {}).length ? 'view' : 'wizard')
    }
  }

  const runJob = async (url, payload, steps, doneMsg) => {
    setJob({ steps, current: 0, elapsed: 0, detail: '' })
    try {
      await api(url, { method: 'POST', body: payload })
    } catch (e) {
      toast({ kind: 'error', title: 'Could not start the planner', text: /load failed|failed to fetch/i.test(e.message) ? 'Could not reach Scaffold. Is it still running?' : e.message, timeout: 10000 })
      return
    }
    watch(steps, doneMsg)
  }

  const generate = (setup) => runJob('/api/planner/generate', setup,
    ['Reading your materials', 'Estimating time per question and scheduling', 'Writing your plan'],
    'Your plan is ready: Quick Plan, Study Plan, Time Estimates and Context.')

  const submitLog = () => {
    const text = logText.trim()
    if (!text) return
    setLogOpen(false)
    setLogText('')
    runJob('/api/planner/log', { text }, ['Reading your log', 'Recalibrating estimates and rescheduling', 'Updating files'], 'Plan updated with your progress.')
  }

  const checkIn = async (message, doneLines) => {
    for (const raw of doneLines) {
      const n = (state.files['Quick Plan'] || '').split('\n').indexOf(raw) + 1
      if (n > 0) { try { await api('/api/planner/toggle', { method: 'POST', body: { line: n, checked: true, file: 'Quick Plan', text: raw } }) } catch (e) { /* the planner will still record it */ } }
    }
    try {
      await api('/api/chats/studyplanner/messages', { method: 'POST', body: { text: message } })
      window.location.hash = '/planchat'
    } catch (e) { toast({ kind: 'error', text: e.message }) }
  }

  const toggle = async (line, checked, text) => {
    try {
      const r = await api('/api/planner/toggle', { method: 'POST', body: { line, checked, file: tab, text } })
      setState((st) => (st.extras?.[tab] != null ? { ...st, extras: { ...st.extras, [tab]: r.content } } : { ...st, files: { ...st.files, [tab]: r.content } }))
    } catch (e) { toast({ kind: 'error', text: e.message }); load() }
  }

  if (!state) {
    return (
      <div className="center muted">
        {loadErr === 'failed'
          ? <div className="stack" style={{ alignItems: 'center' }}><span>Couldn't reach Scaffold.</span><button className="btn" onClick={load}>Try again</button></div>
          : loadErr ? 'Still connecting to Scaffold…' : 'Loading…'}
      </div>
    )
  }

  if (mode === 'generating') {
    return (
      <div className="center-col">
        <div className="card job-card">
          <div className="pulse-orb"><Sparkles size={22} /></div>
          <h2>Building your plan</h2>
          <p className="muted">The planner is reading your exams question by question. This usually takes a minute or two.</p>
          <JobProgress {...job} />
        </div>
      </div>
    )
  }

  if (!hasPlan && mode !== 'wizard') {
    return <ChatView key="studyplanner" chatId="studyplanner" onChanged={() => load()} />
  }

  if (mode === 'wizard') {
    return <Wizard initial={state.setup} onGenerate={generate} onCancel={hasPlan ? () => setMode('view') : null} />
  }

  const pct = progress.all ? Math.round((100 * progress.done) / progress.all) : 0

  return (
    <div className="plan">
      <Pitch compact />
      <header className="page-head">
        <div>
          <div className="eyebrow">Study plan {meta.updated && <span className="muted">· updated {meta.updated}</span>}</div>
          <h1>{tab === 'Quick Plan' ? 'This week' : allTabs.find((t) => t.id === tab)?.label}</h1>
        </div>
        <div className="head-actions">
          <a className="btn primary" href="#/planchat"><MessageSquare size={16} /> Talk to your planner</a>
        </div>
      </header>

      <TodayCard quickPlan={state.files['Quick Plan']} onTalk={() => { window.location.hash = '/planchat' }} onSend={checkIn} />

      <div className="tabs">
        {allTabs.map((t) => (
          <button key={t.id} className={tab === t.id ? 'on' : ''} onClick={() => setTab(t.id)} disabled={!state.files[t.id] && !t.extra}>
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'Quick Plan' && progress.all > 0 && (
        <div className="progress-row">
          <div className="progress"><div style={{ width: `${pct}%` }} /></div>
          <span className="muted small">{progress.done} of {progress.all} tasks done</span>
        </div>
      )}

      <div className="card doc">
        <Markdown
          source={body}
          lineOffset={offset}
          onToggle={toggle}
          onWikiLink={(name) => { const t = allTabs.find((x) => x.id === name); if (t) setTab(t.id) }}
          taskAction={tab === 'Quick Plan' && onStudy ? (raw) => (
            <button className="btn small study-btn" onClick={() => onStudy(raw)}><Play size={13} /> Study this</button>
          ) : null}
        />
      </div>

      {logOpen && (
        <Modal title="Log progress" onClose={() => setLogOpen(false)}
          footer={<>
            <button className="btn ghost" onClick={() => setLogOpen(false)}>Cancel</button>
            <button className="btn primary" onClick={submitLog} disabled={!logText.trim()}><Sparkles size={16} /> Update my plan</button>
          </>}>
          <p className="muted">Say what you did and how long it really took. The planner records it in <b>Time Estimates</b>, recalibrates similar questions and moves unfinished work forward.</p>
          <textarea autoFocus rows={6} value={logText} onChange={(e) => setLogText(e.target.value)}
            placeholder={'e.g. Databases 2 July: Q1–Q3 done in 35 min. Q4 SQL took 70 min, much longer than planned.\nSkipped Linear Algebra today.'} />
          <p className="muted small">Ticked tasks are sent along automatically.</p>
        </Modal>
      )}
    </div>
  )
}
