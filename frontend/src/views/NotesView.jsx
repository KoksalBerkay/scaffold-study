import { useEffect, useMemo, useRef, useState } from 'react'
import { FileText, Folder, FolderOpen, ChevronRight, BookOpen, PencilLine, Search, Check, Loader2, FilePlus } from 'lucide-react'
import { api, apiRetry, setBusy } from '../api'
import Markdown, { Properties, splitFrontmatter } from '../components/Markdown'
import LiveEditor from '../components/LiveEditor'
import { useToast } from '../components/ui'

export default function NotesView({ initial }) {
  const toast = useToast()
  const [tree, setTree] = useState(null)
  const [sel, setSel] = useState(initial || '')
  const [content, setContent] = useState(null)
  const [loadError, setLoadError] = useState(null) // the note exists but could not be read: never open an empty editor over it
  const [reload, setReload] = useState(0)
  const [reading, setReading] = useState(false)
  const [saveState, setSaveState] = useState('saved') // saved | dirty | saving
  const [q, setQ] = useState('')
  // folders the student opened in the list (remembered); the open note's folder is always shown
  const [openFolders, setOpenFolders] = useState(() => { try { return new Set(JSON.parse(localStorage.getItem('scaffold:notes-open') || '[]')) } catch { return new Set() } })
  const toggleFolder = (f) => setOpenFolders((s0) => {
    const s1 = new Set(s0); if (s1.has(f)) s1.delete(f); else s1.add(f)
    try { localStorage.setItem('scaffold:notes-open', JSON.stringify([...s1])) } catch { /* private mode */ }
    return s1
  })
  const treeRef = useRef(null)
  const timer = useRef(null)
  const latest = useRef({ sel, text: null })
  const saving = useRef(null) // the save in flight: saves go out one at a time, in order
  const held = useRef(false) // whether unsaved edits hold off the auto-update reload
  const hold = (on) => { if (held.current !== on) { held.current = on; setBusy(on) } }

  const loadTree = () => apiRetry('/api/notes').then(setTree).catch(() => {})
  useEffect(() => { loadTree() }, [])
  useEffect(() => { if (initial) setSel(initial) }, [initial])
  useEffect(() => {
    // show the open note in the list
    if (!sel || !tree) return
    const t = setTimeout(() => {
      const el = treeRef.current?.querySelector(`[data-path="${CSS.escape(sel)}"]`)
      el?.scrollIntoView({ block: 'nearest' })
    }, 50)
    return () => clearTimeout(t)
  }, [sel, tree])

  const flush = async () => {
    clearTimeout(timer.current)
    const edit = latest.current
    const { sel: path, text } = edit
    if (text == null || !path) return
    const prev = saving.current
    const run = (async () => {
      await prev
      setSaveState('saving')
      try {
        await api('/api/notes/file', { method: 'PUT', body: { path, content: text } })
        // only what was saved is clean: edits typed during the save stay pending for the next one
        if (latest.current === edit) { latest.current = { sel: path, text: null }; setContent(text) }
        if (latest.current.text == null) { hold(false); setSaveState('saved') }
      } catch (e) { setSaveState('dirty'); toast({ kind: 'error', text: `Could not save: ${e.message}` }) }
    })()
    saving.current = run
    await run
  }

  useEffect(() => {
    if (!sel) return
    flush()
    setContent(null)
    setLoadError(null)
    let live = true // a slower answer for the previous note must not land in this one
    api(`/api/notes/file?path=${encodeURIComponent(sel)}`).then((r) => { if (live) { setContent(r.content); setSaveState('saved') } }).catch((e) => { if (!live) return; if (e.status === 404) setContent(''); else setLoadError(e.message || 'Could not reach Scaffold') })
    latest.current = { sel, text: null }
    return () => { live = false }
  }, [sel, reload]) // eslint-disable-line

  // Live-reload when a background agent rewrites the open note (only if there are no unsaved edits)
  useEffect(() => {
    const es = new EventSource('/api/events')
    es.onmessage = (m) => {
      const ev = JSON.parse(m.data)
      if (ev.type !== 'notes') return
      loadTree()
      const path = latest.current.sel
      if (ev.paths.includes(path) && latest.current.text == null) {
        api(`/api/notes/file?path=${encodeURIComponent(path)}`)
          .then((r) => { if (latest.current.sel === path && latest.current.text == null) setContent(r.content) }).catch(() => {})
      }
    }
    return () => es.close()
  }, [])
  useEffect(() => () => flush(), []) // eslint-disable-line

  const onEdit = (text) => {
    hold(true)
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
      <div className="notes-tree" ref={treeRef}>
        <div className="row">
          <div className="search grow"><Search size={14} /><input placeholder="Filter notes" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <button className="icon-btn ghost" onClick={newNote} title="New note"><FilePlus size={16} /></button>
        </div>
        {tree && tree.notes.length === 0 && <p className="muted small pad">No notes yet. They appear here as you study.</p>}
        {groups.map(([folder, notes]) => {
          const isOpen = groups.length <= 4 || !!q || openFolders.has(folder) || notes.some((n) => n.path === sel)
          return (
            <div key={folder} className="tree-group">
              <button className="tree-folder" onClick={() => toggleFolder(folder)} aria-expanded={isOpen}>
                <ChevronRight size={13} className={`chev ${isOpen ? 'rot90' : ''}`} />
                {isOpen ? <FolderOpen size={14} /> : <Folder size={14} />}
                <span className="grow">{folder}</span><span className="tree-count">{notes.length}</span>
              </button>
              {isOpen && notes.map((n) => (
                <button key={n.path} data-path={n.path} className={`tree-item ${sel === n.path ? 'on' : ''}`} onClick={() => setSel(n.path)}>
                  <FileText size={14} /> {n.name}
                </button>
              ))}
            </div>
          )
        })}
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
            {loadError
              ? <p className="muted">This note could not be loaded ({loadError}). <button className="link" onClick={() => setReload((n) => n + 1)}>Try again</button></p>
              : content == null
              ? <p className="muted">Loading…</p>
              : reading
                ? <div className="note-doc"><Properties props={splitFrontmatter(current).props} /><Markdown source={splitFrontmatter(current).body} onWikiLink={openWiki} /></div>
                : <LiveEditor key={sel} value={current} onChange={onEdit} onWikiLink={openWiki} />}
          </div>
        )}
      </div>
    </div>
  )
}
