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

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export async function upload(file) {
  let lastErr
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const fd = new FormData()
      fd.append('file', file, file.name || 'pasted.png')
      const res = await fetch('/api/uploads', { method: 'POST', body: fd })
      if (res.ok) return res.json()
      lastErr = new Error(`Upload failed (${res.status})`)
      if (res.status < 500) break
    } catch (e) { lastErr = e }
    await sleep(600 * (attempt + 1))
  }
  throw new Error(lastErr?.message === 'Load failed' || lastErr?.message === 'Failed to fetch' ? 'Could not reach Scaffold. Is it still running?' : lastErr?.message || 'Upload failed')
}

/**
 * Follow a server-side job (tutor answer, study plan). Survives dropped connections and server restarts:
 * it reconnects and resumes from the last event it saw. Resolves with { ok, error, idle }.
 */
export async function follow(url, onEvent, { signal } = {}) {
  let after = 0
  let failures = 0
  let error = null
  while (!signal?.aborted) {
    try {
      const res = await fetch(`${url}${url.includes('?') ? '&' : '?'}after=${after}`, { signal })
      if (!res.ok || !res.body) throw new Error(`status ${res.status}`)
      failures = 0
      const reader = res.body.getReader()
      const dec = new TextDecoder()
      let buf = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        let i
        while ((i = buf.indexOf('\n\n')) >= 0) {
          const chunk = buf.slice(0, i)
          buf = buf.slice(i + 2)
          const idLine = chunk.split('\n').find((l) => l.startsWith('id: '))
          const line = chunk.split('\n').find((l) => l.startsWith('data: '))
          if (idLine) after = Number(idLine.slice(4))
          if (!line) continue
          const ev = JSON.parse(line.slice(6))
          if (ev.type === 'idle') return { ok: false, idle: true, error }
          if (ev.type === 'error') error = ev.message
          if (ev.type === 'end') return { ok: ev.ok, error }
          onEvent(ev)
        }
      }
      // stream closed without an end event: reconnect
    } catch (e) {
      if (signal?.aborted) break
      failures += 1
      onEvent({ type: 'reconnecting', attempt: failures })
      if (failures > 60) return { ok: false, error: 'Lost the connection to Scaffold.' }
    }
    await sleep(Math.min(3000, 400 * (failures + 1)))
  }
  return { ok: false, error: 'Stopped.' }
}

export function materialUrl(href) {
  return `/api/materials/raw?path=${encodeURIComponent(href)}`
}

/* Work-in-progress tracking so auto-update never reloads in the middle of something */
let busy = 0
export function setBusy(on) { busy = Math.max(0, busy + (on ? 1 : -1)) }
export function isBusy() { return busy > 0 }
