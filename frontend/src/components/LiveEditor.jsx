/**
 * Obsidian-style "live preview" markdown editor (CodeMirror 6).
 * Formatting renders in place; the raw markdown appears only where the cursor is.
 * The file text is never rewritten: what you type is exactly what is saved.
 */
import { useEffect, useRef } from 'react'
import { EditorState, StateField } from '@codemirror/state'
import { Decoration, EditorView, WidgetType, keymap, drawSelection, placeholder as phExt } from '@codemirror/view'
import { markdown, markdownLanguage } from '@codemirror/lang-markdown'
import { languages } from '@codemirror/language-data'
import { syntaxTree, syntaxHighlighting, HighlightStyle, indentOnInput } from '@codemirror/language'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { tags as t } from '@lezer/highlight'
import katex from 'katex'
import 'katex/dist/katex.min.css'

/* ---------------- helpers ---------------- */
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))

function renderMath(src, display) {
  try {
    return katex.renderToString(src, { displayMode: display, throwOnError: false, strict: false })
  } catch (e) {
    return `<span class="lp-math-error">${esc(src)}</span>`
  }
}

/** Small inline renderer for table cells and properties. */
function inlineHTML(s) {
  const maths = []
  let out = s.replace(/\$([^$\n]+?)\$/g, (_, m) => { maths.push(m); return `\u0000${maths.length - 1}\u0000` })
  out = esc(out)
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, '<span class="lp-wikilink">$2</span>')
    .replace(/\[\[([^\]]+)\]\]/g, (_, a) => `<span class="lp-wikilink">${a.replace(/^#\^?/, '')}</span>`)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<span class="lp-link">$1</span>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
  return out.replace(/\u0000(\d+)\u0000/g, (_, i) => renderMath(maths[+i], false))
}

/* ---------------- widgets ---------------- */
class MathWidget extends WidgetType {
  constructor(src, display) { super(); this.src = src; this.display = display }
  eq(o) { return o.src === this.src && o.display === this.display }
  toDOM() {
    const el = document.createElement(this.display ? 'div' : 'span')
    el.className = this.display ? 'lp-math-block' : 'lp-math'
    el.innerHTML = renderMath(this.src, this.display)
    return el
  }
  ignoreEvent() { return false }
}

class CheckboxWidget extends WidgetType {
  constructor(checked, pos) { super(); this.checked = checked; this.pos = pos }
  eq(o) { return o.checked === this.checked && o.pos === this.pos }
  toDOM(view) {
    const el = document.createElement('span')
    el.className = `lp-check ${this.checked ? 'on' : ''}`
    el.setAttribute('role', 'checkbox')
    el.setAttribute('aria-checked', String(this.checked))
    el.innerHTML = this.checked ? '<svg viewBox="0 0 16 16" width="11" height="11"><path d="M3 8.5l3.2 3L13 4.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''
    el.addEventListener('mousedown', (e) => {
      e.preventDefault()
      view.dispatch({ changes: { from: this.pos + 1, to: this.pos + 2, insert: this.checked ? ' ' : 'x' } })
    })
    return el
  }
  ignoreEvent() { return true }
}

class CodeLabelWidget extends WidgetType {
  constructor(lang, code) { super(); this.lang = lang; this.code = code }
  eq(o) { return o.lang === this.lang && o.code === this.code }
  toDOM() {
    const el = document.createElement('span')
    el.className = 'lp-code-label'
    const name = document.createElement('span')
    name.textContent = this.lang || ''
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.textContent = 'Copy'
    btn.addEventListener('mousedown', (e) => {
      e.preventDefault(); e.stopPropagation()
      navigator.clipboard?.writeText(this.code).then(() => { btn.textContent = 'Copied'; setTimeout(() => { btn.textContent = 'Copy' }, 1400) })
    })
    el.append(name, btn)
    return el
  }
  ignoreEvent() { return true }
}

class BulletWidget extends WidgetType {
  eq() { return true }
  toDOM() { const el = document.createElement('span'); el.className = 'lp-bullet'; el.textContent = '•'; return el }
}

class HrWidget extends WidgetType {
  eq() { return true }
  toDOM() { const el = document.createElement('div'); el.className = 'lp-hr'; return el }
}

class TableWidget extends WidgetType {
  constructor(src) { super(); this.src = src }
  eq(o) { return o.src === this.src }
  toDOM() {
    const rows = this.src.split('\n').filter((l) => l.trim())
    const cells = (l) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map((c) => c.trim())
    const head = cells(rows[0] || '')
    const aligns = cells(rows[1] || '').map((c) => (c.endsWith(':') ? (c.startsWith(':') ? 'center' : 'right') : 'left'))
    const body = rows.slice(2).map(cells)
    const wrap = document.createElement('div')
    wrap.className = 'lp-table'
    wrap.innerHTML = `<table><thead><tr>${head.map((h, i) => `<th style="text-align:${aligns[i] || 'left'}">${inlineHTML(h)}</th>`).join('')}</tr></thead><tbody>${
      body.map((r) => `<tr>${head.map((_, i) => `<td style="text-align:${aligns[i] || 'left'}">${inlineHTML(r[i] || '')}</td>`).join('')}</tr>`).join('')}</tbody></table>`
    return wrap
  }
  ignoreEvent() { return false }
}

const PROP_ICONS = {
  tags: '<path d="M3 3h6l8 8-6 6-8-8z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="6.5" cy="6.5" r="1.2" fill="currentColor"/>',
  date: '<rect x="3" y="4.5" width="14" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M3 8.5h14M7 3v3M13 3v3" stroke="currentColor" stroke-width="1.6"/>',
  list: '<path d="M7 6h10M7 10h10M7 14h10" stroke="currentColor" stroke-width="1.6"/><circle cx="3.5" cy="6" r="1" fill="currentColor"/><circle cx="3.5" cy="10" r="1" fill="currentColor"/><circle cx="3.5" cy="14" r="1" fill="currentColor"/>',
  text: '<path d="M4 6h12M4 10h12M4 14h8" stroke="currentColor" stroke-width="1.6"/>',
}
const icon = (k) => `<svg viewBox="0 0 20 20" width="14" height="14">${PROP_ICONS[k]}</svg>`

class PropertiesWidget extends WidgetType {
  constructor(src, end) { super(); this.src = src; this.end = end }
  eq(o) { return o.src === this.src }
  toDOM(view) {
    const el = document.createElement('div')
    el.className = 'lp-props'
    el.title = 'Click to edit properties'
    el.addEventListener('mousedown', (e) => { e.preventDefault(); view.dispatch({ selection: { anchor: 4 } }); view.focus() })
    const lines = this.src.split('\n').slice(1, -1)
    const rows = []
    let cur = null
    lines.forEach((l) => {
      const m = l.match(/^([\w-]+):\s*(.*)$/)
      if (m) { cur = { k: m[1], v: m[2] ? [m[2]] : [] }; rows.push(cur) } else if (cur && l.trim().startsWith('-')) cur.v.push(l.trim().slice(1).trim())
    })
    const kind = (r) => (r.k === 'tags' || r.k === 'aliases' ? 'tags' : /^\d{4}-\d\d-\d\d/.test(r.v[0] || '') ? 'date' : r.v.length > 1 ? 'list' : 'text')
    const val = (r) => {
      const k = kind(r)
      if (!r.v.length) return '<span class="empty">Empty</span>'
      if (k === 'tags' || k === 'list') return r.v.map((x) => `<span class="pill">${esc(x.replace(/^["']|["']$/g, ''))}</span>`).join('')
      return `<span class="txt">${esc(r.v.join(', ').replace(/^["']|["']$/g, ''))}</span>`
    }
    el.innerHTML = `<div class="lp-props-title">Properties</div>${rows.map((r) => `<div class="lp-prop"><span class="k">${icon(kind(r))}${esc(r.k)}</span><span class="v">${val(r)}</span></div>`).join('')}`
    return el
  }
  ignoreEvent() { return false }
}

/* ---------------- decorations ---------------- */
const hide = Decoration.replace({})
const line = (cls) => Decoration.line({ class: cls })
const mark = (cls) => Decoration.mark({ class: cls })

function touches(sel, from, to) {
  return sel.ranges.some((r) => r.from <= to && r.to >= from)
}

function build(state) {
  const decos = []
  const sel = state.selection
  const doc = state.doc
  const add = (from, to, d) => { if (from <= to) decos.push(d.range(from, to)) }
  const lineOf = (pos) => doc.lineAt(pos)
  const onCursorLine = (from, to) => touches(sel, lineOf(from).from, lineOf(to).to)
  const skip = [] // ranges where math/wikilink scanning is off (code, rendered tables)

  // Frontmatter
  let fmEnd = -1
  if (doc.lines > 1 && doc.line(1).text === '---') {
    for (let i = 2; i <= Math.min(doc.lines, 60); i++) {
      if (doc.line(i).text === '---') { fmEnd = doc.line(i).to; break }
    }
    if (fmEnd > 0) {
      skip.push([0, fmEnd])
      const inside = sel.ranges.some((r) => r.from > 0 && r.from < fmEnd)
      if (!inside) add(0, fmEnd, Decoration.replace({ widget: new PropertiesWidget(doc.sliceString(0, fmEnd), fmEnd), block: true }))
      else for (let p = 0; p <= fmEnd;) { const l = lineOf(p); add(l.from, l.from, line('lp-fm')); p = l.to + 1 }
    }
  }

  syntaxTree(state).iterate({
    enter: (node) => {
      const { from, to, name } = node
      if (from < fmEnd) return name === 'Document' ? undefined : false
      const h = name.match(/^ATXHeading(\d)$/)
      if (h) {
        add(lineOf(from).from, lineOf(from).from, line(`lp-h lp-h${h[1]}`))
        return
      }
      switch (name) {
        case 'HeaderMark': {
          if (!onCursorLine(from, to)) {
            const after = doc.sliceString(to, to + 1) === ' ' ? to + 1 : to
            add(from, after, hide)
          } else add(from, to, mark('lp-syntax'))
          return
        }
        case 'StrongEmphasis': add(from, to, mark('lp-strong')); break
        case 'Emphasis': add(from, to, mark('lp-em')); break
        case 'Strikethrough': add(from, to, mark('lp-strike')); break
        case 'InlineCode': {
          skip.push([from, to])
          add(from, to, mark('lp-code'))
          break
        }
        case 'EmphasisMark': case 'StrikethroughMark': case 'CodeMark': {
          const parent = node.node.parent
          if (parent && parent.name === 'FencedCode') return
          if (parent && !touches(sel, parent.from, parent.to)) add(from, to, hide)
          else add(from, to, mark('lp-syntax'))
          return
        }
        case 'Link': {
          const n = node.node
          const marks = []
          for (let c = n.firstChild; c; c = c.nextSibling) if (c.name === 'LinkMark') marks.push(c)
          if (marks.length >= 2 && !touches(sel, from, to)) {
            add(marks[0].from, marks[0].to, hide)
            add(marks[0].to, marks[1].from, mark('lp-link'))
            add(marks[1].from, to, hide)
            return false
          }
          add(from, to, mark('lp-link-src'))
          return false
        }
        case 'FencedCode': case 'CodeBlock': {
          skip.push([from, to])
          if (name === 'FencedCode' && !touches(sel, lineOf(from).from, lineOf(to).to)) {
            const open = lineOf(from), close = lineOf(to)
            const lang = (open.text.match(/^\s*(?:```|~~~)\s*([\w+#-]*)/) || [])[1] || ''
            const code = doc.sliceString(open.to + 1, close.from > open.to ? close.from - 1 : open.to)
            add(open.from, open.to, Decoration.replace({ widget: new CodeLabelWidget(lang, code) }))
            if (close.from !== open.from && /^\s*(```|~~~)\s*$/.test(close.text)) add(close.from, close.to, hide)
          }
          for (let p = from; p <= to;) {
            const l = lineOf(p)
            const first = l.from === lineOf(from).from
            const last = l.from === lineOf(to).from
            add(l.from, l.from, line(`lp-codeblock${first ? ' first' : ''}${last ? ' last' : ''}${(first || last) && name === 'FencedCode' ? ' fence' : ''}`))
            p = l.to + 1
          }
          return false
        }
        case 'Blockquote': {
          const firstLine = lineOf(from)
          const callout = firstLine.text.match(/^>\s*\[!(\w+)\][-+]?\s*(.*)$/)
          for (let p = from; p <= to;) {
            const l = lineOf(p)
            add(l.from, l.from, line(callout ? `lp-callout lp-callout-${callout[1].toLowerCase()}${l.from === firstLine.from ? ' title' : ''}` : 'lp-quote'))
            p = l.to + 1
          }
          if (callout && !onCursorLine(firstLine.from, firstLine.to)) {
            const m = firstLine.text.match(/^>\s*\[!\w+\][-+]?\s*/)
            add(firstLine.from, firstLine.from + m[0].length, hide)
            if (!callout[2]) add(firstLine.from + m[0].length, firstLine.from + m[0].length, Decoration.widget({ widget: new (class extends WidgetType { toDOM() { const s = document.createElement('span'); s.textContent = callout[1][0].toUpperCase() + callout[1].slice(1); return s } })() }))
          }
          break
        }
        case 'QuoteMark': {
          if (!onCursorLine(from, to)) {
            const after = doc.sliceString(to, to + 1) === ' ' ? to + 1 : to
            const l = lineOf(from)
            const isCalloutTitle = /^>\s*\[!\w+\]/.test(l.text) && !onCursorLine(l.from, l.to)
            if (!isCalloutTitle) add(from, after, hide)
          } else add(from, to, mark('lp-syntax'))
          return
        }
        case 'ListMark': {
          const item = node.node.parent
          const list = item?.parent
          const task = item?.getChild('Task')
          if (!onCursorLine(from, to)) {
            if (task) add(from, Math.min(to + 1, task.from), hide)
            else if (list?.name === 'BulletList') add(from, to, Decoration.replace({ widget: new BulletWidget() }))
          }
          if (list?.name === 'OrderedList') add(from, to, mark('lp-olmark'))
          return
        }
        case 'TaskMarker': {
          const checked = /x/i.test(doc.sliceString(from, to))
          if (!touches(sel, from, to)) add(from, to, Decoration.replace({ widget: new CheckboxWidget(checked, from) }))
          if (checked) {
            const l = lineOf(from)
            add(to, l.to, mark('lp-done'))
          }
          return
        }
        case 'HorizontalRule': {
          if (!onCursorLine(from, to)) add(from, to, Decoration.replace({ widget: new HrWidget() }))
          return
        }
        case 'Table': {
          if (!touches(sel, lineOf(from).from, lineOf(to).to)) {
            skip.push([from, to])
            add(lineOf(from).from, lineOf(to).to, Decoration.replace({ widget: new TableWidget(doc.sliceString(lineOf(from).from, lineOf(to).to)), block: true }))
          } else {
            for (let p = from; p <= to;) { const l = lineOf(p); add(l.from, l.from, line('lp-table-src')); p = l.to + 1 }
          }
          return false
        }
        default:
      }
    },
  })

  // Regex passes: display math, inline math, wikilinks, block ids
  const text = doc.toString()
  const inSkip = (a, b) => skip.some(([s, e]) => a < e && b > s)
  const taken = []
  const free = (a, b) => !taken.some(([s, e]) => a < e && b > s)

  for (const m of text.matchAll(/\$\$([\s\S]+?)\$\$/g)) {
    const a = m.index, b = a + m[0].length
    if (inSkip(a, b)) continue
    taken.push([a, b])
    const la = lineOf(a), lb = lineOf(b)
    const block = la.text.trim().startsWith('$$') && lb.text.trim().endsWith('$$')
    if (!touches(sel, la.from, lb.to)) {
      add(block ? la.from : a, block ? lb.to : b, Decoration.replace({ widget: new MathWidget(m[1].trim(), true), block }))
    } else {
      for (let p = la.from; p <= lb.to;) { const l = lineOf(p); add(l.from, l.from, line('lp-math-src')); p = l.to + 1 }
    }
  }
  for (const m of text.matchAll(/(?<![\\$])\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\$)/g)) {
    const a = m.index, b = a + m[0].length
    if (inSkip(a, b) || !free(a, b)) continue
    taken.push([a, b])
    if (!touches(sel, a, b)) add(a, b, Decoration.replace({ widget: new MathWidget(m[1], false) }))
    else add(a, b, mark('lp-math-inline-src'))
  }
  for (const m of text.matchAll(/\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]/g)) {
    const a = m.index, b = a + m[0].length
    if (inSkip(a, b) || !free(a, b)) continue
    if (!touches(sel, a, b)) {
      const label = m[2] || m[1].replace(/^#\^?/, '').replace(/#\^?/, ' › ')
      const startLabel = m[2] ? a + 3 + m[1].length : a + 2
      const endLabel = m[2] ? b - 2 : b - 2
      if (m[2]) {
        add(a, startLabel, hide); add(startLabel, endLabel, mark('lp-wikilink')); add(endLabel, b, hide)
      } else if (label === m[1]) {
        add(a, a + 2, hide); add(a + 2, b - 2, mark('lp-wikilink')); add(b - 2, b, hide)
      } else {
        add(a, b, Decoration.replace({ widget: new (class extends WidgetType { eq(o) { return o.l === this.l } constructor() { super(); this.l = label } toDOM() { const s = document.createElement('span'); s.className = 'lp-wikilink'; s.textContent = label; return s } })() }))
      }
    } else add(a, b, mark('lp-link-src'))
  }
  for (const m of text.matchAll(/(^|[\s(])(#[\p{L}\p{N}_\-/]*[\p{L}_\-/][\p{L}\p{N}_\-/]*)/gmu)) {
    const a = m.index + m[1].length, b = a + m[2].length
    if (inSkip(a, b) || !free(a, b)) continue
    const l = lineOf(a)
    if (/^#{1,6}\s/.test(l.text) && a === l.from) continue
    add(a, b, mark('lp-tag'))
  }
  for (const m of text.matchAll(/[ \t]\^[\w-]+$/gm)) {
    const a = m.index, b = a + m[0].length
    if (inSkip(a, b)) continue
    add(a, b, mark('lp-blockid'))
  }

  return Decoration.set(decos, true)
}

const livePreview = StateField.define({
  create: (state) => build(state),
  update: (deco, tr) => (tr.docChanged || tr.selection || syntaxTree(tr.startState) !== syntaxTree(tr.state) ? build(tr.state) : deco),
  provide: (f) => EditorView.decorations.from(f),
})

const highlight = HighlightStyle.define([
  { tag: t.monospace, fontFamily: 'var(--mono)' },
  { tag: [t.keyword, t.modifier, t.controlKeyword, t.operatorKeyword, t.definitionKeyword, t.moduleKeyword], color: 'var(--syn-keyword)' },
  { tag: [t.string, t.special(t.string), t.regexp, t.character], color: 'var(--syn-string)' },
  { tag: [t.comment, t.lineComment, t.blockComment, t.docComment], color: 'var(--syn-comment)', fontStyle: 'italic' },
  { tag: [t.number, t.bool, t.null, t.atom], color: 'var(--syn-number)' },
  { tag: [t.function(t.variableName), t.function(t.propertyName), t.macroName], color: 'var(--syn-function)' },
  { tag: [t.typeName, t.className, t.namespace, t.standard(t.typeName)], color: 'var(--syn-type)' },
  { tag: [t.propertyName, t.attributeName], color: 'var(--syn-property)' },
  { tag: [t.operator, t.punctuation, t.bracket], color: 'var(--syn-punct)' },
  { tag: [t.tagName, t.meta, t.annotation], color: 'var(--syn-tag)' },
  { tag: t.url, color: 'var(--muted)' },
  { tag: t.processingInstruction, color: 'var(--muted)' },
])

const theme = EditorView.theme({
  '&': { fontSize: '16px', color: 'var(--text)', backgroundColor: 'transparent' },
  '.cm-content': { fontFamily: 'var(--font)', lineHeight: '1.7', padding: '8px 0 40vh', caretColor: 'var(--accent)' },
  '.cm-line': { padding: '0 2px' },
  '&.cm-focused': { outline: 'none' },
  '.cm-cursor': { borderLeftColor: 'var(--accent)', borderLeftWidth: '2px' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection': { backgroundColor: 'var(--accent-soft) !important' },
  '.cm-scroller': { overflow: 'visible' },
})

export default function LiveEditor({ value, onChange, onWikiLink, placeholder }) {
  const host = useRef(null)
  const view = useRef(null)
  const cb = useRef({ onChange, onWikiLink })
  cb.current = { onChange, onWikiLink }

  useEffect(() => {
    const v = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: value || '',
        selection: { anchor: (() => { const m = (value || '').match(/^---\n[\s\S]*?\n---\n?/); return m ? m[0].length : 0 })() },
        extensions: [
          history(),
          drawSelection(),
          indentOnInput(),
          markdown({ base: markdownLanguage, codeLanguages: languages }),
          syntaxHighlighting(highlight),
          livePreview,
          EditorView.lineWrapping,
          keymap.of([indentWithTab, ...defaultKeymap, ...historyKeymap]),
          theme,
          phExt(placeholder || 'Start writing…'),
          EditorView.updateListener.of((u) => { if (u.docChanged) cb.current.onChange?.(u.state.doc.toString()) }),
          EditorView.domEventHandlers({
            mousedown(e) {
              const wl = e.target.closest?.('.lp-wikilink')
              if (wl && (e.metaKey || e.ctrlKey)) { e.preventDefault(); cb.current.onWikiLink?.(wl.textContent); return true }
              return false
            },
          }),
        ],
      }),
    })
    view.current = v
    return () => v.destroy()
  }, []) // eslint-disable-line

  // External updates (e.g. the Note-taker rewrote the file)
  useEffect(() => {
    const v = view.current
    if (v && value != null && value !== v.state.doc.toString()) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } })
    }
  }, [value])

  return <div className="live-editor" ref={host} />
}
