export async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(path, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let msg = res.statusText
    try { const j = await res.json(); msg = j.detail || msg } catch (e) { /* ignore */ }
    throw new Error(msg)
  }
  return res.json()
}

/** POST and read a server-sent-event stream. onEvent gets each parsed event. */
export async function stream(path, body, onEvent, { signal } = {}) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`Request failed (${res.status})`)
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  let last = null
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i)
      buf = buf.slice(i + 2)
      const line = chunk.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      const ev = JSON.parse(line.slice(6))
      last = ev
      if (ev.type === 'error') throw new Error(ev.message)
      onEvent(ev)
    }
  }
  return last
}

export async function upload(file) {
  const fd = new FormData()
  fd.append('file', file, file.name || 'pasted.png')
  const res = await fetch('/api/uploads', { method: 'POST', body: fd })
  if (!res.ok) throw new Error('Upload failed')
  return res.json()
}

export function materialUrl(href) {
  return `/api/materials/raw?path=${encodeURIComponent(href)}`
}
