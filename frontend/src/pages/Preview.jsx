import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { fetchDraft, generatePost, publishDraft, previewReel } from '../api.js'

export default function Preview() {
  const { draftId } = useParams()
  const navigate = useNavigate()
  const [draft, setDraft] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [reelUrl, setReelUrl] = useState(null)
  const [reelBusy, setReelBusy] = useState(false)
  const [reelError, setReelError] = useState(null)

  useEffect(() => {
    let active = true
    fetchDraft(draftId)
      .then((data) => active && setDraft(data.draft))
      .catch((e) => active && setError(e.message))
    return () => {
      active = false
    }
  }, [draftId])

  async function handlePublish(mediaType = 'carousel') {
    if (busy) return
    setBusy(true)
    try {
      await publishDraft(draftId, mediaType)
      navigate('/')
    } finally {
      setBusy(false)
    }
  }

  async function handlePreviewReel() {
    if (reelBusy) return
    setReelBusy(true)
    setReelError(null)
    try {
      const { video_url } = await previewReel(draftId)
      setReelUrl(`${video_url}?t=${Date.now()}`)
    } catch (e) {
      setReelError(e.message)
    } finally {
      setReelBusy(false)
    }
  }

  async function handleRegenerate() {
    if (busy) return
    setBusy(true)
    try {
      const { draft_id } = await generatePost(draft.question)
      navigate(`/preview/${draft_id}`)
    } finally {
      setBusy(false)
    }
  }

  if (error) {
    return (
      <section className="section">
        <div className="container">
          <div className="post-error">{error}</div>
          <Link className="back-link" to="/">← New question</Link>
        </div>
      </section>
    )
  }

  if (!draft) {
    return (
      <section className="section">
        <div className="container">
          <p className="body-md text-muted">Loading…</p>
        </div>
      </section>
    )
  }

  return (
    <section className="section">
      <div className="container">
        <div className="section-head">
          <span className="badge-pill">Preview</span>
          <h1 className="display-xl">{draft.question}</h1>
        </div>

        <div className="preview-grid">
          <figure className="preview-slide">
            <img src={`/img/${draftId}/0`} alt="Question slide" />
            <figcaption className="slide-caption caption">Slide 1 · Question</figcaption>
          </figure>
          <figure className="preview-slide">
            <img src={`/img/${draftId}/1`} alt="Short answer slide" />
            <figcaption className="slide-caption caption">Slide 2 · Short answer</figcaption>
          </figure>
          <figure className="preview-slide">
            <img src={`/img/${draftId}/2`} alt="Long answer slide" />
            <figcaption className="slide-caption caption">Slide 3 · The why</figcaption>
          </figure>
        </div>

        <div className="answer">
          <span className="caption-uppercase text-muted-soft">Reel preview</span>
          <div className="reel-preview-box">
            <button
              className="btn btn-outline"
              type="button"
              onClick={handlePreviewReel}
              disabled={reelBusy}
            >
              {reelBusy ? 'Rendering…' : reelUrl ? 'Re-render reel' : 'Preview reel'}
            </button>
            <span className="body-sm text-muted-soft">
              Question · Short answer · Long answer
            </span>
          </div>
          {reelError && <div className="post-error">{reelError}</div>}
          {reelUrl && (
            <video
              className="reel-video"
              src={reelUrl}
              controls
              autoPlay
              loop
              playsInline
            />
          )}
        </div>

        <div className="preview-answers">
          <div className="answer">
            <span className="caption-uppercase text-muted-soft">Short answer</span>
            <p className="body-strong">{draft.short}</p>
          </div>
          <div className="answer">
            <span className="caption-uppercase text-muted-soft">The why</span>
            <p className="body-md">{draft.long}</p>
          </div>
        </div>

        {draft.caption && (
          <div className="answer caption-box">
            <span className="caption-uppercase text-muted-soft">Instagram caption</span>
            <pre className="caption-text">{draft.caption}</pre>
          </div>
        )}

        <div className="answer caption-box">
          <span className="caption-uppercase text-muted-soft">
            First comment (short + long answer)
          </span>
          <pre className="caption-text">{`${draft.short}\n\n${draft.long}`}</pre>
        </div>

        <div className="preview-ctas">
          <button
            className="btn btn-primary"
            type="button"
            onClick={() => handlePublish('carousel')}
            disabled={busy}
          >
            Post as Carousel
          </button>
          <button
            className="btn btn-outline"
            type="button"
            onClick={() => handlePublish('reel')}
            disabled={busy}
          >
            Post as Reel
          </button>
          <button
            className="btn btn-outline"
            type="button"
            onClick={handleRegenerate}
            disabled={busy}
          >
            Regenerate
          </button>
        </div>

        <Link className="back-link" to="/">← New question</Link>
      </div>
    </section>
  )
}
