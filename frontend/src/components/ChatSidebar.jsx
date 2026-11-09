import { useEffect, useRef, useState } from 'react'
import {
  ChevronRight, Folder, FolderOpen, FolderPlus, MessageSquare, MoreHorizontal, Pencil, Plus, Trash2, FolderInput, FlaskConical, Terminal, GraduationCap,
} from 'lucide-react'
import { api } from '../api'
import { Modal, useToast } from './ui'

function useOutside(ref, onOut) {
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) onOut() }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [ref, onOut])
}

function InlineInput({ initial, onDone, placeholder }) {
  const [v, setV] = useState(initial || '')
  const ref = useRef(null)
  useEffect(() => { ref.current?.focus(); ref.current?.select() }, [])
  const finish = (save) => onDone(save ? v.trim() : null)
  return (
    <input ref={ref} className="inline-input" value={v} placeholder={placeholder} onChange={(e) => setV(e.target.value)}
      onKeyDown={(e) => { if (e.key === 'Enter') finish(true); if (e.key === 'Escape') finish(false) }}
      onBlur={() => finish(true)} />
  )
}

function Menu({ items, onClose }) {
  const ref = useRef(null)
  const [confirm, setConfirm] = useState(null)
  useOutside(ref, onClose)
  return (
    <div className="menu" ref={ref} role="menu">
      {items.map((it, i) => it.header
        ? <div key={i} className="menu-header">{it.header}</div>
        : (
          <button key={i} role="menuitem" className={`${it.danger ? 'danger' : ''} ${it.active ? 'active' : ''}`}
            onClick={() => {
              if (it.danger && confirm !== i) { setConfirm(i); return }
              it.onClick(); onClose()
            }}>
            {it.icon && <it.icon size={14} />} {it.danger && confirm === i ? 'Click again to confirm' : it.label}
          </button>
        ))}
    </div>
  )
}

/** Connect a course folder to its notes folder and its materials folder. */
function CourseSettings({ folder, onClose, onSaved }) {
  const toast = useToast()
  const [opts, setOpts] = useState(null)
  const [notes, setNotes] = useState(folder.notes_folder || '')
  const [mats, setMats] = useState(folder.materials_folder || '')
  useEffect(() => { api('/api/course-folders').then(setOpts).catch(() => setOpts({ notes: [], materials: [] })) }, [])
  const save = async () => {
    const fs = await api(`/api/chat-folders/${folder.id}/course`, { method: 'PATCH', body: { notes_folder: notes, materials_folder: mats } })
    onSaved(fs); onClose()
    toast({ kind: 'success', text: `${folder.name}: course folders saved.` })
  }
  return (
    <Modal title={`Course settings · ${folder.name}`} onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn primary" onClick={save} disabled={!opts}>Save</button></>}>
      <p className="muted small">Chats in this folder belong to the course <b>{folder.name}</b>. They share its memory and its Notes agent.</p>
      <label className="field">
        <span>Notes folder</span>
        <select value={notes} onChange={(e) => setNotes(e.target.value)}>
          <option value="">Automatic (a notes folder named “{folder.name}”)</option>
          {(opts?.notes || []).map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <span className="muted small">Where this course's Notes agent writes.</span>
      </label>
      <label className="field">
        <span>Materials folder</span>
        <select value={mats} onChange={(e) => setMats(e.target.value)}>
          <option value="">Automatic (matched by name)</option>
          {(opts?.materials || []).map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <span className="muted small">Its past exams and slides come first when the tutor searches.</span>
      </label>
    </Modal>
  )
}

export default function ChatSidebar({ chats, activeId, onOpen, onNewChat, onChanged }) {
  const [folders, setFolders] = useState([])
  const [editing, setEditing] = useState(null) // {type:'folder'|'chat'|'new', id}
  const [menu, setMenu] = useState(null) // {type, id}
  const [dragOver, setDragOver] = useState(null)
  const [courseFor, setCourseFor] = useState(null)

  const loadFolders = async () => { try { setFolders(await api('/api/chat-folders')) } catch (e) { setFolders([]) } }
  useEffect(() => { loadFolders() }, [chats.length])

  const createFolder = async (name) => {
    setEditing(null)
    if (!name) return
    await api('/api/chat-folders', { method: 'POST', body: { name } })
    loadFolders()
  }
  const renameFolder = async (id, name) => {
    setEditing(null)
    if (name) setFolders(await api(`/api/chat-folders/${id}`, { method: 'PATCH', body: { name } }))
  }
  const toggleFolder = async (f) => {
    setFolders((fs) => fs.map((x) => (x.id === f.id ? { ...x, collapsed: !x.collapsed } : x)))
    api(`/api/chat-folders/${f.id}`, { method: 'PATCH', body: { collapsed: !f.collapsed } })
  }
  const deleteFolder = async (id) => { await api(`/api/chat-folders/${id}`, { method: 'DELETE' }); await loadFolders(); onChanged() }
  const moveChat = async (cid, folder) => { await api(`/api/chats/${cid}`, { method: 'PATCH', body: { folder } }); onChanged() }
  const renameChat = async (cid, title) => { setEditing(null); if (title) { await api(`/api/chats/${cid}`, { method: 'PATCH', body: { title } }); onChanged() } }
  const deleteChat = async (cid) => { await api(`/api/chats/${cid}`, { method: 'DELETE' }); onChanged(cid) }

  const folderIds = new Set(folders.map((f) => f.id))
  const loose = chats.filter((c) => !c.folder || !folderIds.has(c.folder))

  const dropProps = (target) => ({
    onDragOver: (e) => { e.preventDefault(); setDragOver(target ?? 'root') },
    onDragLeave: () => setDragOver(null),
    onDrop: (e) => { e.preventDefault(); setDragOver(null); const cid = e.dataTransfer.getData('text/chat'); if (cid) moveChat(cid, target) },
  })

  const chatRow = (c, nested) => (
    <div key={c.id} className={`chat-item ${activeId === c.id ? 'on' : ''} ${nested ? 'nested' : ''}`} draggable
      onDragStart={(e) => { e.dataTransfer.setData('text/chat', c.id); e.dataTransfer.effectAllowed = 'move' }}>
      {editing?.type === 'chat' && editing.id === c.id
        ? <InlineInput initial={c.title} onDone={(v) => renameChat(c.id, v)} />
        : (
          <button className="chat-link" onClick={() => onOpen(c.id)} onDoubleClick={() => setEditing({ type: 'chat', id: c.id })} title={c.title}>
            {c.harness ? <FlaskConical size={14} /> : c.codex ? <Terminal size={14} title="Linked Codex chat" /> : <MessageSquare size={14} />} <span>{c.title || 'New chat'}</span>
            {c.badge && <em className={`chat-badge ${/on$/.test(c.badge) ? 'on' : ''}`} title={c.badge}>{c.badge.replace('Reviewer ', '')}</em>}
          </button>
        )}
      <button className="icon-btn ghost row-action" onClick={() => setMenu({ type: 'chat', id: c.id })} aria-label="Chat actions"><MoreHorizontal size={14} /></button>
      {menu?.type === 'chat' && menu.id === c.id && (
        <Menu onClose={() => setMenu(null)} items={[
          { label: 'Rename', icon: Pencil, onClick: () => setEditing({ type: 'chat', id: c.id }) },
          { header: 'Move to' },
          ...folders.map((f) => ({ label: f.name, icon: Folder, active: c.folder === f.id, onClick: () => moveChat(c.id, f.id) })),
          { label: 'No folder', icon: FolderInput, active: !c.folder, onClick: () => moveChat(c.id, null) },
          { label: 'Delete chat', icon: Trash2, danger: true, onClick: () => deleteChat(c.id) },
        ]} />
      )}
    </div>
  )

  return (
    <>
      <div className="nav-label row between-center">
        <span>Chats</span>
        <button className="icon-btn ghost mini" title="New folder" onClick={() => setEditing({ type: 'new' })}><FolderPlus size={14} /></button>
      </div>
      <div className="chat-list">
        {editing?.type === 'new' && (
          <div className="folder-row-item editing"><Folder size={14} /><InlineInput placeholder="Folder name" onDone={createFolder} /></div>
        )}
        {folders.map((f) => {
          const items = chats.filter((c) => c.folder === f.id)
          if (items.length && items.every((c) => c.harness)) items.sort((a, b) => (a.title + (a.badge || '')).localeCompare(b.title + (b.badge || '')))
          const open = !f.collapsed
          return (
            <div key={f.id} className={`folder ${dragOver === f.id ? 'drop' : ''}`} {...dropProps(f.id)}>
              <div className="folder-row-item">
                <button className="folder-toggle" onClick={() => toggleFolder(f)} aria-expanded={open}>
                  <ChevronRight size={13} className={open ? 'rot90' : ''} />
                  {open ? <FolderOpen size={14} /> : <Folder size={14} />}
                </button>
                {editing?.type === 'folder' && editing.id === f.id
                  ? <InlineInput initial={f.name} onDone={(v) => renameFolder(f.id, v)} />
                  : <button className="folder-name" onClick={() => toggleFolder(f)} onDoubleClick={() => setEditing({ type: 'folder', id: f.id })}>{f.name}<span className="count">{items.length}</span></button>}
                <button className="icon-btn ghost row-action" title="New chat in this folder" onClick={() => onNewChat(f.id)}><Plus size={14} /></button>
                <button className="icon-btn ghost row-action" onClick={() => setMenu({ type: 'folder', id: f.id })} aria-label="Folder actions"><MoreHorizontal size={14} /></button>
                {menu?.type === 'folder' && menu.id === f.id && (
                  <Menu onClose={() => setMenu(null)} items={[
                    { label: 'New chat here', icon: Plus, onClick: () => onNewChat(f.id) },
                    { label: 'Rename', icon: Pencil, onClick: () => setEditing({ type: 'folder', id: f.id }) },
                    { label: 'Course settings…', icon: GraduationCap, onClick: () => setCourseFor(f) },
                    { label: 'Delete folder (keeps chats)', icon: Trash2, danger: true, onClick: () => deleteFolder(f.id) },
                  ]} />
                )}
              </div>
              {open && items.map((c) => chatRow(c, true))}
              {open && items.length === 0 && <div className="folder-empty">Drag chats here</div>}
            </div>
          )
        })}
        <div className={`loose ${dragOver === 'root' ? 'drop' : ''}`} {...dropProps(null)}>
          {folders.length > 0 && loose.length > 0 && <div className="loose-label">Not in a folder</div>}
          {loose.map((c) => chatRow(c, false))}
          {chats.length === 0 && <p className="muted small pad">No chats yet. Start one from a plan task or paste an exam question.</p>}
        </div>
      </div>
      {courseFor && <CourseSettings folder={courseFor} onClose={() => setCourseFor(null)} onSaved={setFolders} />}
    </>
  )
}
