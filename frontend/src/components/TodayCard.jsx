import { useMemo, useState } from 'react'
import { Check, Clock, X, CalendarClock, MessageSquare, Send, Coffee, AlertCircle } from 'lucide-react'

const MONTHS = { jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11 }
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const nice = (d) => d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

/** Parse "### Mon 9 Nov 2026" days and their "- [ ]" tasks from the Quick Plan. */
export function parseDays(src) {
  const days = []
  let cur = null
  ;(src || '').split('\n').forEach((line) => {
    const h = line.match(/^#{2,4}\s+.*?(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})/)
    if (h && MONTHS[h[2].toLowerCase()] != null) {
      const d = new Date(Number(h[3]), MONTHS[h[2].toLowerCase()], Number(h[1]))
      cur = { date: iso(d), label: nice(d), tasks: [] }
      days.push(cur)
      return
    }
    if (/^#{1,3}\s/.test(line)) { cur = null; return }
    const t = line.match(/^\s*[-*] \[([ xX])\]\s+(.*)$/)
    if (t && cur) {
      const raw = line
      const text = t[2].replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/\*\*/g, '')
      const mins = Number((text.match(/~\s*(\d+)\s*min/) || [])[1] || 0)
      const [head, ...rest] = text.split(/:\s/)
      cur.tasks.push({ raw, done: t[1] !== ' ', text, head, detail: rest.join(': '), mins })
    }
  })
  return days
}

function TaskRow({ t, state, setState }) {
  const s = state || {}
  return (
    <div className={`today-task ${t.done ? 'was-done' : ''} ${s.status || ''}`}>
      <div className="today-task-main">
        <span className="today-task-head">{t.head}</span>
        {t.detail && <span className="muted small">{t.detail}</span>}
      </div>
      {t.done && !s.status ? <span className="pill-ok"><Check size={12} /> Done</span> : (
        <div className="today-actions">
          <button className={s.status === 'done' ? 'on ok' : ''} onClick={() => setState({ status: s.status === 'done' ? null : 'done', minutes: s.minutes })}><Check size={13} /> Done</button>
          <button className={s.status === 'time' ? 'on warn' : ''} onClick={() => setState({ status: s.status === 'time' ? null : 'time', minutes: s.minutes || '' })}><Clock size={13} /> Different time</button>
          <button className={s.status === 'skip' ? 'on bad' : ''} onClick={() => setState({ status: s.status === 'skip' ? null : 'skip' })}><X size={13} /> Skipped</button>
        </div>
      )}
      {s.status === 'time' && (
        <div className="today-time">
          <span className="muted small">It took about</span>
          {[30, 45, 60, 90, 120, 150].map((m) => (
            <button key={m} className={`chip ${Number(s.minutes) === m ? 'sel' : ''}`} onClick={() => setState({ ...s, minutes: m })}>{m < 60 ? `${m} min` : `${m / 60} h`}</button>
          ))}
          <input type="number" min="5" step="5" placeholder="min" value={s.minutes} onChange={(e) => setState({ ...s, minutes: e.target.value })} />
          {t.mins > 0 && <span className="muted tiny">planned ~{t.mins} min</span>}
        </div>
      )}
    </div>
  )
}

export default function TodayCard({ quickPlan, onSend, onTalk }) {
  const days = useMemo(() => parseDays(quickPlan), [quickPlan])
  const todayIso = iso(new Date())
  const today = days.find((d) => d.date === todayIso)
  const missed = days.filter((d) => d.date < todayIso && d.tasks.some((t) => !t.done))
  const next = days.find((d) => d.date > todayIso && d.tasks.length)
  const [state, setStateMap] = useState({})
  const [note, setNote] = useState('')
  const setFor = (key) => (v) => setStateMap((m) => ({ ...m, [key]: v }))
  const marked = Object.values(state).filter((v) => v?.status).length

  const send = () => {
    const lines = []
    const label = today ? today.label : nice(new Date())
    ;(today?.tasks || []).forEach((t, i) => {
      const s = state[i]
      if (!s?.status) return
      if (s.status === 'done') lines.push(`- Done: ${t.head}${t.mins ? ` (took about the planned ~${t.mins} min)` : ''}`)
      if (s.status === 'time') lines.push(`- ${s.minutes ? 'Done' : 'Worked on'}: ${t.head}, it took ${s.minutes || '?'} min${t.mins ? ` (planned ~${t.mins} min)` : ''}`)
      if (s.status === 'skip') lines.push(`- Skipped: ${t.head}`)
    })
    const msg = `Check-in for ${label}:\n${lines.join('\n')}${note.trim() ? `\n\n${note.trim()}` : ''}\n\nPlease update my plan.`
    const ticks = (today?.tasks || []).map((t, i) => ({ t, s: state[i] })).filter(({ s }) => s?.status === 'done' || (s?.status === 'time' && s.minutes))
    onSend(msg, ticks.map(({ t }) => t.raw))
    setStateMap({}); setNote('')
  }

  return (
    <section className="today card">
      {missed.length > 0 && (
        <div className="missed">
          <AlertCircle size={16} />
          <span><b>{missed.reduce((n, d) => n + d.tasks.filter((t) => !t.done).length, 0)} unfinished tasks</b> from {missed.map((d) => d.label).join(', ')}. No problem: the planner can move them.</span>
          <button className="btn small" onClick={() => onSend(`I didn't finish these days: ${missed.map((d) => `${d.label} (${d.tasks.filter((t) => !t.done).map((t) => t.head).join('; ')})`).join(', ')}. Please reschedule what's left from today on.`, [])}>
            <CalendarClock size={14} /> Reschedule them
          </button>
        </div>
      )}
      <div className="today-head">
        <div>
          <div className="eyebrow">Today · {nice(new Date())}</div>
          <h2>{today?.tasks.length ? 'How did it go?' : 'Nothing planned today'}</h2>
        </div>
        <div className="row">
          {today?.tasks.length > 0 && (
            <button className="btn ghost small" onClick={() => onSend(`I didn't study today (${today.label}). Please move today's tasks forward.`, [])}><Coffee size={14} /> I didn't study today</button>
          )}
          <button className="btn small" onClick={onTalk}><MessageSquare size={14} /> Talk to your planner</button>
        </div>
      </div>

      {today?.tasks.length > 0 ? (
        <>
          <p className="muted small">Mark each task, then send it. The planner updates your schedule and its time estimates.</p>
          <div className="today-tasks">
            {today.tasks.map((t, i) => <TaskRow key={i} t={t} state={state[i]} setState={setFor(i)} />)}
          </div>
          <div className="today-foot">
            <input className="grow" placeholder="Anything else? e.g. “Q4 was really hard”, “I'm busy Thursday”" value={note} onChange={(e) => setNote(e.target.value)} />
            <button className="btn primary" disabled={!marked && !note.trim()} onClick={send}><Send size={14} /> Update my plan</button>
          </div>
        </>
      ) : (
        <p className="muted">
          {next ? <>Next study day: <b>{next.label}</b>, {next.tasks.length} task{next.tasks.length > 1 ? 's' : ''}. </> : null}
          Plans change: tell the planner anytime, for example “I can only study 2 hours this week”.
        </p>
      )}
    </section>
  )
}
