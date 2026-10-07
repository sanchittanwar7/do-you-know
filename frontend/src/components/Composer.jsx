import { useState } from 'react'

export default function Composer({ loggedIn, onGenerate }) {
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    const q = question.trim()
    if (!q || busy) return
    setBusy(true)
    try {
      await onGenerate(q)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section id="compose" className="composer-band">
      <div className="compose-inner">
        {loggedIn ? (
          <form className="compose-form" onSubmit={handleSubmit}>
            <input
              className="text-input"
              type="text"
              name="question"
              placeholder="Why are there 7 days in a week?"
              autoFocus
              autoComplete="off"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? 'Generating…' : 'Generate'}
            </button>
          </form>
        ) : (
          <a className="btn btn-primary" href="/login">
            Connect Instagram
          </a>
        )}
      </div>
    </section>
  )
}
