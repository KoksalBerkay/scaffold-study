import { useEffect, useState } from 'react'
import { Cpu, KeyRound, ScrollText, Brain, FolderCog, CheckCircle2, XCircle, Loader2, RotateCcw, Save, FolderOpen } from 'lucide-react'
import { api } from '../api'
import { FolderPicker, Segmented, useToast } from '../components/ui'

const ROLE_INFO = {
  planner: { label: 'Planner', hint: 'Builds and updates your study plan. Benefits from strong reasoning.' },
  tutor: { label: 'Tutor', hint: 'Teaches you. Needs vision for screenshots.' },
  reviewer: { label: 'Reviewer', hint: 'Checks every tutor reply before you see it.' },
  background: { label: 'Background', hint: 'Notes, memory and chat summaries. A faster model is fine.' },
}
const PROMPT_INFO = {
  planner: 'Study planner', plan_updater: 'Plan updater', tutor: 'Tutor', reviewer: 'Reviewer',
  notetaker: 'Note-taker', memory_updater: 'Memory updater', summary: 'Chat summary', math: 'Math formatting (shared)',
}
const SHORT = { codex: 'ChatGPT · Codex', claude_code: 'Claude · Claude Code', openai: 'OpenAI API', anthropic: 'Anthropic API' }
const SECTIONS = [
  { id: 'models', label: 'Models', icon: Cpu },
  { id: 'prompts', label: 'Prompts', icon: ScrollText },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'folders', label: 'Folders', icon: FolderCog },
]

function Models({ settings, setSettings, save }) {
  const toast = useToast()
  const [info, setInfo] = useState(null)
  const [testing, setTesting] = useState({})
  const [keys, setKeys] = useState({ openai: '', anthropic: '' })
  useEffect(() => { api('/api/models').then(setInfo) }, [])
  if (!info) return <p className="muted">Checking providers…</p>

  const setRole = (role, patch) => {
    const roles = { ...settings.roles, [role]: { ...settings.roles[role], ...patch } }
    if (patch.provider) {
      roles[role].model = info.suggestions[patch.provider]?.[0] || ''
      const ef = info.efforts[patch.provider] || []
      if (!ef.includes(roles[role].effort)) roles[role].effort = ef.includes('medium') ? 'medium' : ef[0] || ''
    }
    setSettings({ ...settings, roles })
    save({ roles })
  }
  const applyAll = (role) => {
    const r = settings.roles[role]
    const roles = Object.fromEntries(Object.keys(settings.roles).map((k) => [k, { ...settings.roles[k], provider: r.provider, model: r.model }]))
    setSettings({ ...settings, roles }); save({ roles })
    toast({ kind: 'success', text: `All roles now use ${r.model || r.provider}.` })
  }
  const test = async (role) => {
    setTesting((t) => ({ ...t, [role]: 'run' }))
    const r = await api('/api/models/test', { method: 'POST', body: { role } })
    setTesting((t) => ({ ...t, [role]: r.ok ? 'ok' : r.reply }))
  }
  const saveKey = async (p) => {
    await save({ providers: { ...settings.providers, [p]: { api_key: keys[p] } } })
    setKeys((k) => ({ ...k, [p]: '' }))
    setInfo(await api('/api/models'))
    toast({ kind: 'success', text: 'API key saved locally.' })
  }

  return (
    <div className="stack">
      <section className="card">
        <h3>Providers</h3>
        <p className="muted small">Use a subscription you already have, or an API key. Keys are stored only on this computer.</p>
        <div className="provider-grid">
          {Object.entries(info.providers).map(([id, label]) => {
            const st = info.status[id]
            return (
              <div key={id} className="provider">
                <div className="provider-head">
                  {st.ready ? <CheckCircle2 size={16} className="ok" /> : <XCircle size={16} className="bad" />}
                  <b>{label}</b>
                </div>
                <div className="muted small">{st.detail}</div>
                {(id === 'openai' || id === 'anthropic') && (
                  <div className="key-row">
                    <KeyRound size={14} className="muted" />
                    <input type="password" placeholder={settings.providers[id].api_key || (id === 'openai' ? 'sk-…' : 'sk-ant-…')}
                      value={keys[id]} onChange={(e) => setKeys((k) => ({ ...k, [id]: e.target.value }))} />
                    <button className="btn small" disabled={!keys[id]} onClick={() => saveKey(id)}>Save</button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <section className="card">
        <h3>Model for each agent</h3>
        <p className="muted small">Each agent can run on a different provider and model.</p>
        <div className="roles">
          {Object.keys(ROLE_INFO).map((role) => {
            const r = settings.roles[role]
            const cm = r.provider === 'codex' && (info.codex_models || []).find((m) => m.id === r.model)
            const efforts = (cm && cm.efforts.length ? cm.efforts : info.efforts[r.provider]) || []
            const t = testing[role]
            return (
              <div key={role} className="role-row">
                <div className="role-name">
                  <b>{ROLE_INFO[role].label}</b>
                  <span className="muted small">{ROLE_INFO[role].hint}</span>
                </div>
                <label className="field compact">
                  <span>Provider</span>
                  <select value={r.provider} onChange={(e) => setRole(role, { provider: e.target.value })}>
                    {Object.keys(info.providers).map((id) => <option key={id} value={id}>{SHORT[id] || id}</option>)}
                  </select>
                </label>
                <label className="field compact">
                  <span>Model</span>
                  <input list={`models-${r.provider}`} value={r.model} placeholder="default" onChange={(e) => setRole(role, { model: e.target.value })} />
                  <datalist id={`models-${r.provider}`}>{(info.suggestions[r.provider] || []).map((m) => <option key={m} value={m} />)}</datalist>
                </label>
                <label className="field compact">
                  <span>Reasoning</span>
                  <select value={r.effort} onChange={(e) => setRole(role, { effort: e.target.value })}>
                    {!efforts.includes(r.effort) && <option value={r.effort}>{r.effort || 'default'}</option>}
                    {efforts.map((e) => <option key={e} value={e}>{e}</option>)}
                  </select>
                </label>
                <div className="role-actions">
                  <button className="btn small" onClick={() => test(role)} disabled={t === 'run'}>
                    {t === 'run' ? <Loader2 size={13} className="spin" /> : 'Test'}
                  </button>
                  {role === 'tutor' && <button className="btn small ghost" onClick={() => applyAll(role)} title="Use this provider and model for every agent">Use for all</button>}
                </div>
                {t && t !== 'run' && <div className={`role-test ${t === 'ok' ? 'ok' : 'bad'}`}>{t === 'ok' ? 'Connected ✓' : t}</div>}
              </div>
            )
          })}
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
  const [content, setContent] = useState(null)
  const [orig, setOrig] = useState('')
  useEffect(() => { api('/api/memory').then((r) => { setContent(r.content); setOrig(r.content) }) }, [])
  if (content == null) return null
  const save = async () => { await api('/api/memory', { method: 'PUT', body: { content } }); setOrig(content); toast({ kind: 'success', text: 'Memory saved.' }) }
  return (
    <div className="card stack">
      <div className="row between">
        <div>
          <h3>Your personal memory</h3>
          <p className="muted small">Rules the Tutor and Reviewer follow for you only. It grows when you criticise the teaching ("you skipped why this works"). You can edit it any time.</p>
        </div>
        <button className="btn primary small" onClick={save} disabled={content === orig}><Save size={14} /> Save</button>
      </div>
      <textarea className="mono code-area" value={content} onChange={(e) => setContent(e.target.value)} spellCheck={false} />
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
      <div className="field">
        <span>Tutor behaviour</span>
        <label className="check-row"><input type="checkbox" checked={settings.review} onChange={(e) => save({ review: e.target.checked })} /> Reviewer checks every reply</label>
        <label className="check-row"><input type="checkbox" checked={settings.auto_notes} onChange={(e) => save({ auto_notes: e.target.checked })} /> Write notes automatically</label>
      </div>
      {pick && <FolderPicker initial={settings[pick] || settings.notes_path_effective} onClose={() => setPick(null)} onPick={(p) => { save({ [pick]: p }); setPick(null) }} />}
    </div>
  )
}

export default function SettingsView({ section, onSaved }) {
  const [settings, setSettings] = useState(null)
  const sec = section || 'models'
  useEffect(() => { api('/api/settings').then(setSettings) }, [])
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
    </div>
  )
}
