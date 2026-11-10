import ReactMarkdown, { defaultUrlTransform } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeHighlight from 'rehype-highlight'
import { useRef, useState } from 'react'
import 'katex/dist/katex.min.css'
import { materialUrl } from '../api'

const LANG_NAMES = { js: 'JavaScript', javascript: 'JavaScript', ts: 'TypeScript', typescript: 'TypeScript', py: 'Python', python: 'Python',
  java: 'Java', c: 'C', cpp: 'C++', 'c++': 'C++', cs: 'C#', csharp: 'C#', go: 'Go', rust: 'Rust', rs: 'Rust', sql: 'SQL', bash: 'Bash', sh: 'Shell',
  shell: 'Shell', zsh: 'Shell', json: 'JSON', yaml: 'YAML', yml: 'YAML', html: 'HTML', xml: 'XML', css: 'CSS', kotlin: 'Kotlin', swift: 'Swift',
  php: 'PHP', ruby: 'Ruby', r: 'R', matlab: 'MATLAB', verilog: 'Verilog', vhdl: 'VHDL', asm: 'Assembly', x86asm: 'Assembly', armasm: 'Assembly',
  md: 'Markdown', markdown: 'Markdown', plaintext: 'Text', text: 'Text' }

function CodeBlock({ children, ...rest }) {
  const ref = useRef(null)
  const [copied, setCopied] = useState(false)
  const code = Array.isArray(children) ? children[0] : children
  const cls = code?.props?.className || ''
  const lang = (cls.match(/language-([\w+#-]+)/) || [])[1]
  const copy = async () => {
    try { await navigator.clipboard.writeText(ref.current?.innerText || ''); setCopied(true); setTimeout(() => setCopied(false), 1400) } catch (e) { /* no clipboard */ }
  }
  return (
    <div className="codeblock">
      <div className="codeblock-bar">
        <span>{lang ? LANG_NAMES[lang.toLowerCase()] || lang : ''}</span>
        <button type="button" onClick={copy}>{copied ? 'Copied' : 'Copy'}</button>
      </div>
      <pre ref={ref} {...rest}>{children}</pre>
    </div>
  )
}

/** Split YAML frontmatter off. Returns { body, meta, offset } where offset = lines removed. */
export function splitFrontmatter(src = '') {
  const m = src.match(/^---\n([\s\S]*?)\n---\n?/)
  if (!m) return { body: src, meta: {}, props: [], offset: 0 }
  const meta = {}
  const props = []
  let cur = null
  m[1].split('\n').forEach((l) => {
    const mm = l.match(/^([\w-]+):\s*(.*)$/)
    if (mm) { cur = { k: mm[1], v: mm[2] ? [mm[2].replace(/^["']|["']$/g, '')] : [] }; props.push(cur); if (mm[2]) meta[mm[1]] = mm[2] }
    else if (cur && l.trim().startsWith('-')) cur.v.push(l.trim().slice(1).trim().replace(/^["']|["']$/g, ''))
  })
  return { body: src.slice(m[0].length), meta, props, offset: m[0].split('\n').length - 1 }
}

/** Obsidian-style Properties block for reading view. */
export function Properties({ props }) {
  if (!props?.length) return null
  return (
    <div className="props">
      {props.map((p) => (
        <div key={p.k} className="prop">
          <span className="k">{p.k}</span>
          <span className="v">
            {p.v.length === 0 && <span className="muted">Empty</span>}
            {(p.k === 'tags' || p.k === 'aliases' || p.v.length > 1)
              ? p.v.map((x) => <span key={x} className="pill">{x}</span>)
              : p.v.map((x) => <span key={x}>{x}</span>)}
          </span>
        </div>
      ))}
    </div>
  )
}

/** Obsidian-flavoured preprocessing that keeps line numbers stable. */
function preprocess(src) {
  return src
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => `$$${m}$$`)
    .replace(/\\\((.+?)\\\)/g, (_, m) => `$${m}$`)
    .replace(/\[\[([^\]|#]*)(#\^?[^\]|]*)?(?:\|([^\]]+))?\]\]/g, (_, page, anchor, label) => {
      const text = label || page || (anchor || '').replace(/^#\^?/, '')
      return `[${text}](wiki:${encodeURIComponent((page || '') + (anchor || ''))})`
    })
    .replace(/[ \t]\^[\w-]+$/gm, '')
    .replace(/^> \[!(\w+)\][-+]?[ \t]*(.*)$/gm, (_, kind, title) => `> **${title || kind[0].toUpperCase() + kind.slice(1)}**`)
}

/** Our own link kinds pass; everything else goes through react-markdown's filter (no javascript: or data: URLs from model output or notes). */
const urlTransform = (u) => (/^(wiki|tag):/.test(u) || u.startsWith('file://') ? u : defaultUrlTransform(u))

function tagify(src) {
  return src.split(/(```[\s\S]*?```|`[^`\n]*`|\$\$[\s\S]*?\$\$|\$[^$\n]*\$)/).map((part, i) => (i % 2 ? part : part.replace(
    /(^|[\s(])#([\p{L}_\-/][\p{L}\p{N}_\-/]*)/gmu,
    (all, pre, tag, off, str) => {
      const lineStart = str.lastIndexOf('\n', off) + 1
      if (off + pre.length === lineStart && /^#{1,6}\s/.test(str.slice(lineStart))) return all
      return `${pre}[#${tag}](tag:${tag})`
    },
  ))).join('')
}

export default function Markdown({ source, onToggle, onWikiLink, onLink, taskAction, lineOffset = 0, className = '' }) {
  const lines = (source || '').split('\n')
  const components = {
    a({ href = '', children, node, ...rest }) {
      if (href.startsWith('wiki:')) {
        return (
          <a href="#" className="wikilink" onClick={(e) => { e.preventDefault(); onWikiLink?.(decodeURIComponent(href.slice(5))) }}>
            {children}
          </a>
        )
      }
      if (href.startsWith('tag:')) return <span className="md-tag">{children}</span>
      if (href.startsWith('file://')) {
        return <a href={materialUrl(href)} target="_blank" rel="noreferrer" className="material-link" title="Open the file">{children}</a>
      }
      // links inside the notes (another note, a heading): the notes view opens them itself
      if (onLink && !/^[a-z][\w+.-]*:/i.test(href)) {
        return <a href="#" onClick={(e) => { e.preventDefault(); onLink(href) }}>{children}</a>
      }
      return <a href={href} target="_blank" rel="noreferrer" {...rest}>{children}</a>
    },
    input({ node, ...props }) {
      if (props.type === 'checkbox') return null
      return <input {...props} />
    },
    li({ node, children, className: cls, ...rest }) {
      if (!cls || !cls.includes('task-list-item')) return <li {...rest}>{children}</li>
      const line = node?.position?.start?.line
      const raw = line ? lines[line - 1] || '' : ''
      const checked = /\[[xX]\]/.test(raw)
      return (
        <li className={`task ${checked ? 'done' : ''}`}>
          <button
            type="button"
            className={`check ${checked ? 'on' : ''}`}
            aria-label={checked ? 'Mark as not done' : 'Mark as done'}
            disabled={!onToggle}
            onClick={() => onToggle?.(line + lineOffset, !checked, raw)}
          >
            {checked && <svg viewBox="0 0 16 16" width="12" height="12"><path d="M3 8.5l3.2 3L13 4.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>}
          </button>
          <div className="task-body">{children}</div>
          {taskAction && !checked && taskAction(raw)}
        </li>
      )
    },
    pre({ node, children, ...rest }) {
      return <CodeBlock {...rest}>{children}</CodeBlock>
    },
    table({ children }) {
      return <div className="table-wrap"><table>{children}</table></div>
    },
  }
  return (
    <div className={`md ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, [remarkMath, { singleDollarTextMath: true }]]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }], [rehypeHighlight, { detect: false, ignoreMissing: true, aliases: { cpp: ['c++'], bash: ['sh', 'zsh', 'shell'] } }]]}
        urlTransform={urlTransform}
        components={components}
      >
        {tagify(preprocess(source || ''))}
      </ReactMarkdown>
    </div>
  )
}
