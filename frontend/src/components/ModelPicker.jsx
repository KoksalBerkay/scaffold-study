import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, Eye, PencilLine, List, Circle, CheckCircle2 } from 'lucide-react'

const SHORT = { codex: 'ChatGPT', claude_code: 'Claude', openai: 'OpenAI API', anthropic: 'Anthropic API' }
export const providerShort = (p) => SHORT[p] || p

export function modelLabel(catalog, cfg) {
  const m = catalog?.[cfg.provider]?.models?.find((x) => x.id === cfg.model)
  return m?.label || cfg.model || 'Default model'
}

/** A button that shows the current choice and opens a picker popover. */
export default function ModelPicker({ catalog, value, onChange, compact, align = 'left' }) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState(value.provider)
  const [custom, setCustom] = useState(false)
  const [draft, setDraft] = useState(value.model || '')
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    setTab(value.provider)
    const known = catalog?.[value.provider]?.models?.some((m) => m.id === value.model)
    setCustom(!!value.model && !known)
    setDraft(value.model || '')
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const k = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', h)
    document.addEventListener('keydown', k)
    return () => { document.removeEventListener('mousedown', h); document.removeEventListener('keydown', k) }
  }, [open]) // eslint-disable-line

  if (!catalog) return <button className="mp-button" disabled>Loading models…</button>
  const prov = catalog[tab] || { models: [] }
  const current = catalog[value.provider]?.models?.find((m) => m.id === value.model)
  const efforts = (current?.efforts?.length ? current.efforts : catalog[value.provider]?.models?.[0]?.efforts) || []

  const pick = (provider, m) => {
    const eff = m.efforts?.length ? (m.efforts.includes(value.effort) ? value.effort : m.default_effort || m.efforts[0]) : ''
    onChange({ provider, model: m.id, effort: eff })
  }
  const applyCustom = () => {
    const id = draft.trim()
    if (!id) return
    const effs = prov.models?.[0]?.efforts || []
    onChange({ provider: tab, model: id, effort: effs.includes(value.effort) ? value.effort : (effs.includes('medium') ? 'medium' : effs[0] || '') })
    setOpen(false)
  }

  return (
    <div className={`mp ${compact ? 'compact' : ''}`} ref={ref}>
      <button type="button" className={`mp-button ${open ? 'open' : ''}`} onClick={() => setOpen(!open)} aria-haspopup="dialog" aria-expanded={open}>
        <span className={`mp-dot ${catalog[value.provider]?.status?.ready ? 'ok' : 'bad'}`} />
        <span className="mp-prov">{providerShort(value.provider)}</span>
        <span className="mp-sep">·</span>
        <b className="mp-model">{modelLabel(catalog, value)}</b>
        {value.effort && <span className="mp-effort">{value.effort}</span>}
        <ChevronDown size={14} className="mp-chev" />
      </button>

      {open && (
        <div className={`mp-pop ${align}`} role="dialog" aria-label="Choose a model">
          <div className="mp-tabs">
            {Object.entries(catalog).map(([id, p]) => (
              <button key={id} className={tab === id ? 'on' : ''} onClick={() => { setTab(id); setCustom(false) }} title={p.status?.detail}>
                {p.status?.ready ? <CheckCircle2 size={13} className="ok" /> : <Circle size={13} className="muted" />}
                {providerShort(id)}
              </button>
            ))}
          </div>
          <div className="mp-source">
            <span>{prov.status?.ready ? `Models from ${prov.source}` : prov.status?.detail}</span>
            <button className="link small" onClick={() => setCustom(!custom)}>
              {custom ? <><List size={12} /> Pick from list</> : <><PencilLine size={12} /> Custom ID</>}
            </button>
          </div>

          {custom ? (
            <div className="mp-custom">
              <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={prov.models?.[0]?.id || 'model id'}
                onKeyDown={(e) => { if (e.key === 'Enter') applyCustom() }} spellCheck={false} />
              <button className="btn primary small" onClick={applyCustom} disabled={!draft.trim()}>Use</button>
              <p className="muted tiny">Type any model ID this provider accepts. Use Test to check it works.</p>
            </div>
          ) : (
            <div className="mp-list" role="listbox">
              {prov.models?.map((m) => {
                const sel = value.provider === tab && value.model === m.id
                return (
                  <button key={m.id} role="option" aria-selected={sel} className={`mp-item ${sel ? 'sel' : ''}`} onClick={() => pick(tab, m)}>
                    <div className="mp-item-main">
                      <span className="mp-item-name">{m.label}{m.vision && <Eye size={12} className="muted" title="Can read images" />}</span>
                      {m.description && <span className="muted tiny">{m.description}</span>}
                    </div>
                    {sel && <Check size={15} className="ok" />}
                  </button>
                )
              })}
              {!prov.models?.length && <p className="muted small pad">No models found.</p>}
            </div>
          )}

          {efforts.length > 0 && (
            <div className="mp-effort-row">
              <span className="muted tiny">Reasoning</span>
              <div className="segmented small">
                {efforts.map((e) => (
                  <button key={e} className={value.effort === e ? 'on' : ''} title={current?.effort_help?.[e] || ''}
                    onClick={() => onChange({ ...value, effort: e })}>{e}</button>
                ))}
              </div>
              {current?.effort_help?.[value.effort] && <span className="muted tiny mp-effort-help">{current.effort_help[value.effort]}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
