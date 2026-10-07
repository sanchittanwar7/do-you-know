async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    ...options,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.error || `Request failed (${res.status})`)
  }
  return res.json()
}

export const fetchMe = () => request('/api/me')

export const fetchPosts = (refresh = false) =>
  request(`/api/posts${refresh ? '?refresh=1' : ''}`)

export const fetchDraft = (draftId) => request(`/api/posts/${draftId}`)

export const generatePost = (question) =>
  request('/api/generate', {
    method: 'POST',
    body: JSON.stringify({ question }),
  })

export const publishDraft = (draftId) =>
  request(`/api/posts/${draftId}/publish`, { method: 'POST' })
