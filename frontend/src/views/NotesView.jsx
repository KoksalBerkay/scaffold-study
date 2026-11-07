import { useEffect, useMemo, useState } from 'react'
import { FileText, Folder, PencilLine, Eye, Save, Search } from 'lucide-react'
import { api } from '../api'
import Markdown, { splitFrontmatter } from '../components/Markdown'
import { useToast } from '../components/ui'

export default function NotesView({ initial }) {
  const toast = useToast()
  const [tree, setTree] = useState(null)
  const [sel, setSel] = useState(initial || '')
  const [content, setContent] = useState('')
  const [draft, setDraft] = useState(null)
  const [q, setQ] = useState('')

  useEffect(() => { api('/api/notes').then(setTree) }, [])
  useEffect(() => { if (initial) setSel(initial) }, [initial])
  useEffect(() => {
    if (!sel) return
    setDraft(null)
    api(`/api/notes/file?path=${encodeURIComponent(sel)}`).then((r) => setContent(r.content)).catch(() => setContent(''))
  }, [sel])

  const groups = useMemo(() => {
    const g = {}
    ;(tree?.notes || []).filter((n) => !q || n.path.toLowerCase().includes(q.toLowerCase()))
      .forEach((n) => { (g[n.folder || 'Notes'] = g[n.folder || 'Notes'] || []).push(n) })
    return Object.entries(g).sort()
  }, [tree, q])

  const openWiki = (name) => {
    const n = tree?.notes.find((x) => x.name === name)
    if (n) setSel(n.path)
  }
  const save = async () => {
    await api('/api/notes/file', { method: 'PUT', body: { path: sel, content: draft } })
    setContent(draft); setDraft(null)
    toast({ kind: 'success', text: 'Note saved.' })
  }
  const { body, meta } = splitFrontmatter(content)

  return (
    <div className="notes">
      <div className="notes-tree">
        <div className="search"><Search size={14} /><input placeholder="Filter notes" value={q} onChange={(e) => setQ(e.target.value)} /></div>
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
          <>
            <header className="page-head">
              <div>
                <div className="eyebrow">{sel.split('/').slice(0, -1).join(' / ') || 'Notes'}{meta.tags ? '' : ''}</div>
                <h1>{sel.split('/').pop().replace(/\.md$/, '')}</h1>
              </div>
              <div className="head-actions">
                {draft == null
                  ? <button className="btn ghost" onClick={() => setDraft(content)}><PencilLine size={16} /> Edit</button>
                  : <>
                    <button className="btn ghost" onClick={() => setDraft(null)}><Eye size={16} /> Cancel</button>
                    <button className="btn primary" onClick={save}><Save size={16} /> Save</button>
                  </>}
              </div>
            </header>
            {draft == null
              ? <div className="card doc note-doc"><Markdown source={body} onWikiLink={openWiki} /></div>
              : <div className="split-edit">
                <textarea className="mono code-area" value={draft} onChange={(e) => setDraft(e.target.value)} spellCheck={false} />
                <div className="card doc note-doc"><Markdown source={splitFrontmatter(draft).body} /></div>
              </div>}
          </>
        )}
      </div>
    </div>
  )
}
