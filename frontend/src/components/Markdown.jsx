import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import { materialUrl } from '../api'

/** Split YAML frontmatter off. Returns { body, meta, offset } where offset = lines removed. */
export function splitFrontmatter(src = '') {
  const m = src.match(/^---\n([\s\S]*?)\n---\n?/)
  if (!m) return { body: src, meta: {}, offset: 0 }
  const meta = {}
  m[1].split('\n').forEach((l) => {
    const mm = l.match(/^([\w-]+):\s*(.*)$/)
    if (mm && mm[2]) meta[mm[1]] = mm[2]
  })
  return { body: src.slice(m[0].length), meta, offset: m[0].split('\n').length - 1 }
}

/** Obsidian-flavoured preprocessing that keeps line numbers stable. */
function preprocess(src) {
  return src
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => `$$${m}$$`)
    .replace(/\\\((.+?)\\\)/g, (_, m) => `$${m}$`)
    .replace(/\[\[([^\]|#]*)(#\^?[^\]|]*)?(?:\|([^\]]+))?\]\]/g, (_, page, anchor, label) => {
      const text = label || page || (anchor || '').replace(/^#\^?/, '')
      return `[${text}](wiki:${encodeURIComponent(page || '')})`
    })
    .replace(/[ \t]\^[\w-]+$/gm, '')
    .replace(/^> \[!(\w+)\][ \t]*(.*)$/gm, (_, kind, title) => `> **${title || kind}**`)
}

export default function Markdown({ source, onToggle, onWikiLink, taskAction, lineOffset = 0, className = '' }) {
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
      if (href.startsWith('file://')) {
        return <a href={materialUrl(href)} target="_blank" rel="noreferrer" className="material-link" title="Open the file">{children}</a>
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
            onClick={() => onToggle?.(line + lineOffset, !checked)}
          >
            {checked && <svg viewBox="0 0 16 16" width="12" height="12"><path d="M3 8.5l3.2 3L13 4.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>}
          </button>
          <div className="task-body">{children}</div>
          {taskAction && !checked && taskAction(raw)}
        </li>
      )
    },
    table({ children }) {
      return <div className="table-wrap"><table>{children}</table></div>
    },
  }
  return (
    <div className={`md ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, [remarkMath, { singleDollarTextMath: true }]]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        urlTransform={(u) => u}
        components={components}
      >
        {preprocess(source || '')}
      </ReactMarkdown>
    </div>
  )
}
