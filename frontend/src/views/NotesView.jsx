import { useEffect, useMemo, useRef, useState } from 'react'
import { FileText, Folder, BookOpen, PencilLine, Search, Check, Loader2, FilePlus } from 'lucide-react'
import { api } from '../api'
import Markdown, { splitFrontmatter } from '../components/Markdown'
import LiveEditor from '../components/LiveEditor'
import { useToast } from '../components/ui'

export default function NotesView({ initial }) {
  const toast = useToast()
  const [tree, setTree] = useState(null)
  const [sel, setSel] = useState(initial || '')
  const [content, setContent] = useState(null)
  const [reading, setReading] = useState(false)
  const [saveState, setSaveState] = useState('saved') // saved | dirty | saving
  const [q, setQ] = useState('')
  const timer = useRef(null)
  const latest = useRef({ sel, text: null })

  const loadTree = () => api('/api/notes').then(setTree)
  useEffect(() => { loadTree() }, [])
  useEffect(() => { if (initial) setSel(initial) }, [initial])

  const flush = async () => {
    clearTimeout(timer.current)
    const { sel: path, text } = latest.current
    if (text == null || !path) return
    setSaveState('saving')
    try {
      await api('/api/notes/file', { method: 'PUT', body: { path, content: text } })
      latest.current.text = null
      setSaveState('saved')
    } catch (e) { setSaveState('dirty'); toast({ kind: 'error', text: `Could not save: ${e.message}` }) }
  }

  useEffect(() => {
    if (!sel) return
    flush()
    setContent(null)
    api(`/api/notes/file?path=${encodeURIComponent(sel)}`).then((r) => { setContent(r.content); setSaveState('saved') }).catch(() => setContent(''))
    latest.current = { sel, text: null }
  }, [sel]) // eslint-disable-line

  // Live-reload when a background agent rewrites the open note (only if there are no unsaved edits)
  useEffect(() => {
    const es = new EventSource('/api/events')
    es.onmessage = (m) => {
      const ev = JSON.parse(m.data)
      if (ev.type !== 'notes') return
      loadTree()
      if (ev.paths.includes(latest.current.sel) && latest.current.text == null) {
        api(`/api/notes/file?path=${encodeURIComponent(latest.current.sel)}`).then((r) => setContent(r.content))
      }
    }
    return () => es.close()
  }, [])
  useEffect(() => () => flush(), []) // eslint-disable-line

  const onEdit = (text) => {
    latest.current = { sel, text }
    setSaveState('dirty')
    clearTimeout(timer.current)
    timer.current = setTimeout(flush, 700)
  }

  const groups = useMemo(() => {
    const g = {}
    ;(tree?.notes || []).filter((n) => !q || n.path.toLowerCase().includes(q.toLowerCase()))
      .forEach((n) => { (g[n.folder || 'Notes'] = g[n.folder || 'Notes'] || []).push(n) })
    return Object.entries(g).sort()
  }, [tree, q])

  const openWiki = (name) => {
    const n = tree?.notes.find((x) => x.name === name.split(' › ')[0])
    if (n) setSel(n.path)
  }

  const newNote = async () => {
    const folder = sel.includes('/') ? sel.split('/').slice(0, -1).join('/') + '/' : ''
    let path = `${folder}Untitled.md`
    let i = 2
    while (tree?.notes.some((n) => n.path === path)) path = `${folder}Untitled ${i++}.md`
    await api('/api/notes/file', { method: 'PUT', body: { path, content: `# ${path.split('/').pop().replace('.md', '')}\n\n` } })
    await loadTree()
    setSel(path)
  }

  const current = latest.current.text ?? content
  return (
    <div className="notes">
      <div className="notes-tree">
        <div className="row">
          <div className="search grow"><Search size={14} /><input placeholder="Filter notes" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <button className="icon-btn ghost" onClick={newNote} title="New note"><FilePlus size={16} /></button>
        </div>
        {tree && tree.notes.length === 0 && <p className="muted small pad">No notes yet. They appear here as you study.</p>}
        {groups.map(([folder, notes]) => (
          <div key={folder} className="tree-group">
            <div className="tree-folder"><Folder size={14} /> {folder}</div>
            {notes.map((n) => (
              <button key={n.path} className={`tree-item ${sel === n.path ? 'on' : ''}`} onClick={() => setSel(n.path)}>
                <FileText size={14} /> {n.name}
              </button>
            ))}
          </div>
        ))}
        {tree && <p className="muted tiny pad mono" title={tree.root}>{tree.root}</p>}
      </div>
      <div className="notes-view">
        {!sel && <div className="center muted">Pick a note on the left.</div>}
        {sel && (
          <div className="note-page">
            <div className="note-bar">
              <span className="muted small">{sel.split('/').slice(0, -1).join(' / ') || 'Notes'}</span>
              <div className="row">
                <span className={`save-state ${saveState}`}>
                  {saveState === 'saving' ? <><Loader2 size={12} className="spin" /> Saving</> : saveState === 'dirty' ? 'Edited' : <><Check size={12} /> Saved</>}
                </span>
                <button className="icon-btn ghost" onClick={() => { flush(); setReading(!reading) }} title={reading ? 'Edit (live preview)' : 'Reading view'}>
                  {reading ? <PencilLine size={16} /> : <BookOpen size={16} />}
                </button>
              </div>
            </div>
            <h1 className="note-title">{sel.split('/').pop().replace(/\.md$/, '')}</h1>
            {content == null
              ? <p className="muted">Loading…</p>
              : reading
                ? <div className="note-doc"><Markdown source={splitFrontmatter(current).body} onWikiLink={openWiki} /></div>
                : <LiveEditor key={sel} value={content} onChange={onEdit} onWikiLink={openWiki} />}
          </div>
        )}
      </div>
    </div>
  )
}
