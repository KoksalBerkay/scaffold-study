import { useEffect, useState } from 'react'
import { Cpu, KeyRound, ScrollText, Brain, FolderCog, CheckCircle2, XCircle, Loader2, RotateCcw, Save, FolderOpen, Terminal, Link2, CalendarDays, ChevronRight } from 'lucide-react'
import { api, apiRetry } from '../api'
import { FolderPicker, useToast } from '../components/ui'
import ModelPicker, { modelLabel } from '../components/ModelPicker'

const ROLE_INFO = {
  planner: { label: 'Planner', hint: 'Builds and updates your study plan. Benefits from strong reasoning.' },
  tutor: { label: 'Tutor', hint: 'Teaches you. Needs vision for screenshots.' },
  reviewer: { label: 'Reviewer', hint: 'Checks every tutor reply before you see it.' },
  background: { label: 'Background', hint: 'Notes, memory and chat summaries. A faster model is fine.' },
}
const PROMPT_INFO = {
  planner_chat: 'Planner conversation', planner: 'Study planner', plan_updater: 'Plan updater', tutor: 'Tutor', reviewer: 'Reviewer',
  notetaker: 'Note-taker', memory_updater: 'Memory updater', summary: 'Chat summary', math: 'Math formatting (shared)',
}
const SECTIONS = [
  { id: 'models', label: 'Models', icon: Cpu },
  { id: 'prompts', label: 'Prompts', icon: ScrollText },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'folders', label: 'Folders', icon: FolderCog },
  { id: 'codex', label: 'Codex chats', icon: Terminal },
]

function Models({ settings, setSettings, save }) {
  const toast = useToast()
  const [catalog, setCatalog] = useState(null)
  const [testing, setTesting] = useState({})
  const [keys, setKeys] = useState({ openai: '', anthropic: '' })
  const loadCatalog = () => apiRetry('/api/models').then((r) => setCatalog(r.catalog)).catch(() => {})
  useEffect(() => { loadCatalog() }, [])

  const setRole = (role, cfg) => {
    const roles = { ...settings.roles, [role]: cfg }
    setSettings({ ...settings, roles }); save({ roles })
    setTesting((t) => ({ ...t, [role]: null }))
  }
  const preset = (kind) => {
    const base = settings.roles.tutor
    const m = catalog?.[base.provider]?.models?.find((x) => x.id === base.model)
    const effs = m?.efforts || []
    const pickEff = (want) => (effs.includes(want) ? want : effs.includes('medium') ? 'medium' : effs[0] || '')
    const roles = Object.fromEntries(Object.keys(settings.roles).map((r) => [r, {
      provider: base.provider, model: base.model,
      effort: kind === 'same' ? base.effort : pickEff(r === 'planner' || r === 'tutor' ? 'high' : 'medium'),
    }]))
    setSettings({ ...settings, roles }); save({ roles })
    toast({ kind: 'success', text: kind === 'same' ? `Every agent now uses ${modelLabel(catalog, base)} · ${base.effort}.` : 'Recommended: strong reasoning for Planner and Tutor, faster for Reviewer and background.' })
  }
  const test = async (role) => {
    setTesting((t) => ({ ...t, [role]: 'run' }))
    const r = await api('/api/models/test', { method: 'POST', body: { role } })
    setTesting((t) => ({ ...t, [role]: r.ok ? 'ok' : r.reply }))
  }
  const saveKey = async (p) => {
    await save({ providers: { ...settings.providers, [p]: { api_key: keys[p] } } })
    setKeys((k) => ({ ...k, [p]: '' }))
    await loadCatalog()
    toast({ kind: 'success', text: 'API key saved on this computer. Its models are now in the list.' })
  }
  if (!catalog) return <p className="muted">Checking your subscriptions and keys…</p>

  return (
    <div className="stack">
      <section className="card">
        <div className="row between">
          <div>
            <h3>Model for each agent</h3>
            <p className="muted small">Pick from the models your subscription or API key actually offers. Each agent can use a different one.</p>
          </div>
          <div className="row">
            <button className="btn small ghost" onClick={() => preset('recommended')} title="Tutor's model for all; high reasoning for Planner and Tutor, medium for the rest">Recommended</button>
            <button className="btn small ghost" onClick={() => preset('same')} title="Use the Tutor's model and reasoning for every agent">Same for all</button>
          </div>
        </div>
        <div className="roles">
          {Object.keys(ROLE_INFO).map((role) => {
            const t = testing[role]
            return (
              <div key={role} className="role-row v2">
                <div className="role-name">
                  <b>{ROLE_INFO[role].label}</b>
                  <span className="muted small">{ROLE_INFO[role].hint}</span>
                </div>
                <ModelPicker catalog={catalog} value={settings.roles[role]} onChange={(cfg) => setRole(role, cfg)} align="right" />
                <button className="btn small" onClick={() => test(role)} disabled={t === 'run'}>
                  {t === 'run' ? <Loader2 size={13} className="spin" /> : t === 'ok' ? <><CheckCircle2 size={13} className="ok" /> Works</> : 'Test'}
                </button>
                {t && t !== 'run' && t !== 'ok' && <div className="role-test bad">{t}</div>}
              </div>
            )
          })}
        </div>
      </section>

      <section className="card">
        <h3>Connections</h3>
        <p className="muted small">Use a subscription you already have, or an API key. Keys stay on this computer.</p>
        <div className="provider-grid">
          {Object.entries(catalog).map(([id, p]) => (
            <div key={id} className={`provider ${p.status.ready ? 'ready' : ''}`}>
              <div className="provider-head">
                {p.status.ready ? <CheckCircle2 size={16} className="ok" /> : <XCircle size={16} className="bad" />}
                <b>{p.label}</b>
              </div>
              <div className="muted small">{p.status.ready ? `${p.models.length} models · ${p.source}` : p.status.detail}</div>
              {(id === 'openai' || id === 'anthropic') && (
                <div className="key-row">
                  <KeyRound size={14} className="muted" />
                  <input type="password" placeholder={settings.providers[id].api_key || (id === 'openai' ? 'Paste sk-…' : 'Paste sk-ant-…')}
                    value={keys[id]} onChange={(e) => setKeys((k) => ({ ...k, [id]: e.target.value }))}
                    onKeyDown={(e) => { if (e.key === 'Enter' && keys[id]) saveKey(id) }} />
                  <button className="btn small" disabled={!keys[id]} onClick={() => saveKey(id)}>Save</button>
                </div>
              )}
              {id === 'codex' && !p.status.ready && <code className="tiny">codex login</code>}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

function Prompts() {
  const toast = useToast()
  const [list, setList] = useState([])
  const [sel, setSel] = useState('tutor')
  const [draft, setDraft] = useState('')
  useEffect(() => { api('/api/prompts').then((l) => { setList(l); setDraft(l.find((p) => p.name === sel)?.content || '') }) }, []) // eslint-disable-line
  const cur = list.find((p) => p.name === sel)
  const pick = (n) => { setSel(n); setDraft(list.find((p) => p.name === n)?.content || '') }
  const save = async () => {
    await api(`/api/prompts/${sel}`, { method: 'PUT', body: { content: draft } })
    setList((l) => l.map((p) => (p.name === sel ? { ...p, content: draft, customized: true } : p)))
    toast({ kind: 'success', text: `${PROMPT_INFO[sel]} prompt saved.` })
  }
  const reset = async () => {
    const r = await api(`/api/prompts/${sel}`, { method: 'DELETE' })
    setDraft(r.content)
    setList((l) => l.map((p) => (p.name === sel ? { ...p, content: r.content, customized: false } : p)))
    toast({ text: 'Restored the default prompt.' })
  }
  return (
    <div className="prompts">
      <div className="prompt-list">
        {list.map((p) => (
          <button key={p.name} className={sel === p.name ? 'on' : ''} onClick={() => pick(p.name)}>
            {PROMPT_INFO[p.name] || p.name}
            {p.customized && <span className="dot" title="Customized" />}
          </button>
        ))}
      </div>
      <div className="prompt-edit card">
        <div className="row between">
          <div>
            <b>{PROMPT_INFO[sel]}</b>
            <div className="muted small">{'{{memory}}'}, {'{{math_rules}}'} and {'{{today}}'} are filled in automatically.</div>
          </div>
          <div className="row">
            <button className="btn ghost small" onClick={reset} disabled={!cur?.customized}><RotateCcw size={14} /> Reset to default</button>
            <button className="btn primary small" onClick={save} disabled={draft === cur?.content}><Save size={14} /> Save</button>
          </div>
        </div>
        <textarea className="mono code-area" value={draft} onChange={(e) => setDraft(e.target.value)} spellCheck={false} />
      </div>
    </div>
  )
}

function Memory() {
  const toast = useToast()
  const [courses, setCourses] = useState([])
  const [scope, setScope] = useState('')
  const [content, setContent] = useState(null)
  const [orig, setOrig] = useState('')
  useEffect(() => { api('/api/memory/courses').then(setCourses).catch(() => {}) }, [])
  useEffect(() => {
    setContent(null)
    api(`/api/memory${scope ? `?course=${encodeURIComponent(scope)}` : ''}`).then((r) => { setContent(r.content); setOrig(r.content) })
  }, [scope])
  const dirty = content != null && content !== orig
  const pick = (c) => { if (dirty && !window.confirm('Discard unsaved changes?')) return; setScope(c) }
  const save = async () => {
    await api('/api/memory', { method: 'PUT', body: { content, course: scope || null } })
    setOrig(content)
    setCourses((cs) => cs.map((c) => (c.name === scope ? { ...c, has_memory: true } : c)))
    toast({ kind: 'success', text: scope ? `Memory for ${scope} saved.` : 'Memory saved.' })
  }
  return (
    <div className="memory-layout">
      <div className="prompt-list">
        <button className={scope === '' ? 'on' : ''} onClick={() => pick('')}>All courses</button>
        {courses.length > 0 && <div className="list-label">Courses</div>}
        {courses.map((c) => (
          <button key={c.name} className={scope === c.name ? 'on' : ''} onClick={() => pick(c.name)}>
            {c.name}{c.has_memory && <span className="dot" title="Has its own rules" />}
          </button>
        ))}
      </div>
      <div className="card stack">
        <div className="row between">
          <div>
            <h3>{scope ? `Memory for ${scope}` : 'Your personal memory'}</h3>
            <p className="muted small">{scope
              ? `Rules only for chats in the ${scope} folder: its notation, exam style, how its notes should look. They are added to your general memory.`
              : 'Rules the Tutor and Reviewer follow for you in every course. It grows when you criticise the teaching ("you skipped why this works"). Each course folder can also have its own memory.'}</p>
          </div>
          <button className="btn primary small" onClick={save} disabled={!dirty}><Save size={14} /> Save</button>
        </div>
        {content == null ? <p className="muted">Loading…</p>
          : <textarea className="mono code-area" value={content} onChange={(e) => setContent(e.target.value)} spellCheck={false} />}
      </div>
    </div>
  )
}

function PlanFolder({ settings, save }) {
  const toast = useToast()
  const [v, setV] = useState(settings.plan_folder || '')
  const commit = async () => {
    const name = v.trim().replace(/^\/+|\/+$/g, '')
    if (name === (settings.plan_folder || '')) return
    await save({ plan_folder: name })
    toast({ kind: 'success', text: `The study plan now lives in “${name || 'Study Plan'}”.` })
  }
  return (
    <div className="field">
      <span>Study plan folder</span>
      <input value={v} placeholder="Study Plan" onChange={(e) => setV(e.target.value)} onBlur={commit}
        onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }} />
      <span className="muted small">A folder inside your notes folder. Quick Plan, Study Plan, Time Estimates and Context live here; any other note in it (for example “Past Exam Coverage”) gets its own tab on the plan page.</span>
    </div>
  )
}

function Folders({ settings, save }) {
  const [pick, setPick] = useState(null)
  return (
    <div className="card stack">
      <h3>Folders</h3>
      {[
        ['materials_path', 'Materials folder', 'Your course files. Only read, never changed.'],
        ['notes_path', 'Notes folder', 'Where notes and the study plan are written. Point it at an Obsidian vault if you like.'],
      ].map(([key, label, hint]) => (
        <div key={key} className="field">
          <span>{label}</span>
          <div className="folder-row">
            <div className="folder-path">{settings[key] || (key === 'notes_path' ? settings.notes_path_effective : 'Not set')}</div>
            <button className="btn" onClick={() => setPick(key)}><FolderOpen size={15} /> Change</button>
          </div>
          <span className="muted small">{hint}</span>
        </div>
      ))}
      <PlanFolder settings={settings} save={save} />
      <div className="field">
        <span>Tutor behaviour</span>
        <label className="check-row"><input type="checkbox" checked={settings.review} onChange={(e) => save({ review: e.target.checked })} /> Reviewer checks every reply</label>
        <label className="check-row"><input type="checkbox" checked={settings.auto_notes} onChange={(e) => save({ auto_notes: e.target.checked })} /> Write notes automatically</label>
      </div>
      {pick && <FolderPicker initial={settings[pick] || settings.notes_path_effective} onClose={() => setPick(null)} onPick={(p) => { save({ [pick]: p }); setPick(null) }} />}
    </div>
  )
}

const ago = (t) => {
  const d = (Date.now() / 1000 - t) / 86400
  return d < 1 ? 'today' : d < 2 ? 'yesterday' : `${Math.round(d)} days ago`
}

function CodexChats() {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [folders, setFolders] = useState([])
  const [open, setOpen] = useState({})
  const [folderFor, setFolderFor] = useState({})
  const [busy, setBusy] = useState(null)
  const load = () => api('/api/codex/threads').then((r) => {
    setData(r)
    setOpen((o) => (Object.keys(o).length ? o : Object.fromEntries((r.projects || []).slice(0, 2).map((p) => [p.name, true]))))
  })
  useEffect(() => { load(); api('/api/chat-folders').then((f) => setFolders(f.filter((x) => !x.name.startsWith('Reviewer tests')))) }, [])
  const link = async (t, asPlanner) => {
    setBusy(t.id)
    try {
      const meta = await api('/api/codex/link', { method: 'POST', body: { thread: t.id, folder: folderFor[t.id] || null, as_planner: !!asPlanner } })
      window.dispatchEvent(new Event('scaffold:chats'))
      toast({ kind: 'success', text: asPlanner ? `“${t.title}” is now your planner chat.` : `Linked “${t.title}”. It's in your chats.` })
      await load()
      if (!asPlanner) window.location.hash = `/chat/${meta.id}`
    } catch (e) { toast({ kind: 'error', text: e.message }) }
    setBusy(null)
  }
  if (!data) return <p className="muted">Reading your Codex chats…</p>
  if (!data.available) return <div className="card"><h3>Codex isn't set up</h3><p className="muted">Install the Codex CLI and sign in (<code>codex login</code>) to continue your Codex chats here.</p></div>
  return (
    <div className="stack">
      <div className="card">
        <h3>Continue your Codex chats in Scaffold</h3>
        <p className="muted small">Linking doesn't copy anything. Scaffold continues the <b>same</b> Codex chat: it keeps its whole history, files and settings, and new messages also show up in the Codex app.
          The Reviewer checks each answer, and the Notes agent writes your notes. Don't send in the same chat from Codex and Scaffold at the same moment.</p>
      </div>
      {data.projects.map((p) => (
        <section key={p.name} className="card codex-project">
          <button className="codex-project-head" onClick={() => setOpen((o) => ({ ...o, [p.name]: !o[p.name] }))}>
            <ChevronRight size={15} className={open[p.name] ? 'rot90' : ''} /> <b>{p.name}</b> <span className="muted small">{p.threads.length} chat{p.threads.length > 1 ? 's' : ''}</span>
          </button>
          {open[p.name] && p.threads.map((t) => (
            <div key={t.id} className="codex-thread">
              <div className="grow">
                <div className="codex-title">{t.title}</div>
                <div className="muted tiny">{[t.model, t.effort].filter(Boolean).join(' · ')} · {ago(t.updated)}</div>
              </div>
              {t.linked ? (
                <a className="btn small ghost" href={t.linked.kind === 'planner' ? '#/planchat' : `#/chat/${t.linked.chat}`}>
                  {t.linked.kind === 'planner' ? <><CalendarDays size={13} /> Planner chat</> : <><Link2 size={13} /> Linked · open</>}
                </a>
              ) : (
                <div className="row">
                  <select value={folderFor[t.id] || ''} onChange={(e) => setFolderFor((f) => ({ ...f, [t.id]: e.target.value }))} title="Course folder in the sidebar">
                    <option value="">No folder</option>
                    {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </select>
                  <button className="btn small primary" disabled={busy === t.id} onClick={() => link(t)}>{busy === t.id ? <Loader2 size={13} className="spin" /> : <Link2 size={13} />} Link</button>
                  <button className="btn small ghost" disabled={busy === t.id} onClick={() => link(t, true)} title="Use this chat as your study planner"><CalendarDays size={13} /> As planner</button>
                </div>
              )}
            </div>
          ))}
        </section>
      ))}
    </div>
  )
}

export default function SettingsView({ section, onSaved }) {
  const [settings, setSettings] = useState(null)
  const sec = section || 'models'
  useEffect(() => { apiRetry('/api/settings').then(setSettings).catch(() => {}) }, [])
  const save = async (patch) => {
    const s = await api('/api/settings', { method: 'PUT', body: { ...settings, ...patch } })
    setSettings(s); onSaved?.(s)
  }
  if (!settings) return <div className="center muted">Loading…</div>
  return (
    <div className="settings">
      <header className="page-head"><div><div className="eyebrow">Settings</div><h1>You're in control</h1></div></header>
      <div className="tabs">
        {SECTIONS.map((s) => (
          <button key={s.id} className={sec === s.id ? 'on' : ''} onClick={() => { window.location.hash = `/settings/${s.id}` }}>
            <s.icon size={15} /> {s.label}
          </button>
        ))}
      </div>
      {sec === 'models' && <Models settings={settings} setSettings={setSettings} save={save} />}
      {sec === 'prompts' && <Prompts />}
      {sec === 'memory' && <Memory />}
      {sec === 'folders' && <Folders settings={settings} save={save} />}
      {sec === 'codex' && <CodexChats />}
    </div>
  )
}
