import { useEffect, useMemo, useRef, useState } from 'react'
import { FileText, Folder, FolderOpen, ChevronRight, BookOpen, PencilLine, Search, Check, Loader2, FilePlus } from 'lucide-react'
import { api, apiRetry, setBusy, materialUrl } from '../api'
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
  const [anchor, setAnchor] = useState(null) // { path, id, seq }: a heading or block a link asked to show
  // folders the student opened or closed in the list (remembered): { 'A/B': true | false }
  const [folderState, setFolderState] = useState(() => { try { return JSON.parse(localStorage.getItem('scaffold:notes-folders') || '{}') || {} } catch { return {} } })
  const setFolders = (patch) => setFolderState((s0) => {
    const s1 = { ...s0, ...patch }
    try { localStorage.setItem('scaffold:notes-folders', JSON.stringify(s1)) } catch { /* private mode */ }
    return s1
  })
  const docRef = useRef(null)
  const revealed = useRef(null) // the note whose folders were last opened in the list
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
    // show the open note in the list: open its folders, then scroll to it
    if (!sel || !tree) return
    if (revealed.current !== sel) {
      revealed.current = sel
      const parts = sel.split('/').slice(0, -1)
      const shut = parts.map((_, i) => parts.slice(0, i + 1).join('/')).filter((f) => folderState[f] !== true)
      if (shut.length) setFolders(Object.fromEntries(shut.map((f) => [f, true])))
    }
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

  // Nested folder tree: { name, path, folders: [...], notes: [...], count }
  const root = useMemo(() => {
    const top = { name: '', path: '', kids: {}, notes: [], count: 0 }
    ;(tree?.notes || []).filter((n) => !q || n.path.toLowerCase().includes(q.toLowerCase())).forEach((n) => {
      let node = top
      top.count++
      for (const part of (n.folder ? n.folder.split('/') : [])) {
        const path = node.path ? `${node.path}/${part}` : part
        node = node.kids[part] = node.kids[part] || { name: part, path, kids: {}, notes: [], count: 0 }
        node.count++
      }
      node.notes.push(n)
    })
    const finish = (node) => ({ ...node, folders: Object.values(node.kids).sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true })).map(finish) })
    return finish(top)
  }, [tree, q])

  /** Find a note by a link target: a name ("Past Exams") or a path ("Databases/Past Exams"), preferring the open note's folder. */
  const findNote = (target) => {
    const t = target.replace(/\.md$/i, '').replace(/^\/+/, '').toLowerCase()
    if (!t) return null
    const notes = tree?.notes || []
    const here = sel.split('/').slice(0, -1).join('/')
    const byPath = notes.find((n) => n.path.replace(/\.md$/i, '').toLowerCase() === t)
      || notes.find((n) => n.path.replace(/\.md$/i, '').toLowerCase() === (here ? `${here}/${t}` : t).toLowerCase())
    if (byPath) return byPath
    const base = t.split('/').pop()
    const named = notes.filter((n) => n.path.split('/').pop().replace(/\.md$/i, '').toLowerCase() === base
      && (!t.includes('/') || n.path.replace(/\.md$/i, '').toLowerCase().endsWith(t)))
    return named.find((n) => n.folder === here) || named[0] || null
  }

  /** Open a note (and optionally a heading or ^block in it). An empty page means the open note. */
  const goTo = (page, anchorId) => {
    const n = page ? findNote(page) : tree?.notes.find((x) => x.path === sel) || { path: sel }
    if (!n) { toast({ kind: 'error', text: `There is no note called "${page}" yet.` }); return }
    if (n.path !== sel) { flush(); setSel(n.path) }
    setAnchor(anchorId ? { path: n.path, id: anchorId, seq: Date.now() } : null)
  }

  const openWiki = (target) => {
    const [page, ...rest] = target.split('#')
    const id = rest.filter(Boolean).pop() // Obsidian allows "Note#Section#Subsection": the last one is the target
    goTo(page.trim(), id && id.trim())
  }

  const openExternal = (url) => {
    const a = document.createElement('a')
    a.href = url; a.target = '_blank'; a.rel = 'noreferrer'
    document.body.appendChild(a); a.click(); a.remove()
  }

  const openLink = (href) => {
    if (!href) return
    if (href.startsWith('file://')) return openExternal(materialUrl(href))
    if (/^(https?|mailto):/i.test(href)) return openExternal(href)
    if (/^[a-z][\w+.-]*:/i.test(href)) return // other schemes (javascript:, data:, …) never open
    let raw = href
    try { raw = decodeURIComponent(href) } catch { /* keep as written */ }
    const [page, ...rest] = raw.split('#')
    goTo(page.trim(), rest.filter(Boolean).pop()?.trim())
  }

  // Reading view: scroll to the heading a link asked for
  useEffect(() => {
    if (!reading || !anchor || anchor.path !== sel || content == null) return
    const norm = (t) => t.replace(/\s+/g, ' ').trim().toLowerCase()
    const t = setTimeout(() => {
      const h = [...(docRef.current?.querySelectorAll('h1, h2, h3, h4, h5, h6') || [])].find((el) => norm(el.textContent) === norm(anchor.id))
      h?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    }, 30)
    return () => clearTimeout(t)
  }, [anchor, reading, content, sel])

  const renderFolder = (node, depth) => {
    const isOpen = !!q || (folderState[node.path] ?? (depth === 0 && root.folders.length <= 4))
    return (
      <div key={node.path} className="tree-group">
        <button className="tree-folder" style={{ paddingLeft: 8 + depth * 14 }} onClick={() => setFolders({ [node.path]: !isOpen })} aria-expanded={isOpen}>
          <ChevronRight size={13} className={`chev ${isOpen ? 'rot90' : ''}`} />
          {isOpen ? <FolderOpen size={14} /> : <Folder size={14} />}
          <span className="grow">{node.name}</span><span className="tree-count">{node.count}</span>
        </button>
        {isOpen && (
          <div className="tree-children" style={{ '--indent': `${15 + depth * 14}px` }}>
            {node.folders.map((f) => renderFolder(f, depth + 1))}
            {node.notes.map((n) => noteItem(n, depth + 1))}
          </div>
        )}
      </div>
    )
  }
  const noteItem = (n, depth) => (
    <button key={n.path} data-path={n.path} className={`tree-item ${sel === n.path ? 'on' : ''}`} style={{ paddingLeft: 8 + depth * 14 }} onClick={() => setSel(n.path)}>
      <FileText size={14} /> {n.name}
    </button>
  )

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
        {root.folders.map((f) => renderFolder(f, 0))}
        {root.notes.map((n) => noteItem(n, 0))}
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
                ? <div className="note-doc" ref={docRef}><Properties props={splitFrontmatter(current).props} /><Markdown source={splitFrontmatter(current).body} onWikiLink={openWiki} onLink={openLink} /></div>
                : <LiveEditor key={sel} value={current} onChange={onEdit} onWikiLink={openWiki} onLink={openLink} anchor={anchor?.path === sel ? anchor : null} />}
          </div>
        )}
      </div>
    </div>
  )
}
