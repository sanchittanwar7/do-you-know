import { useState } from 'react'
import {
  Bookmark,
  Eye,
  Heart,
  MessageCircle,
  RefreshCw,
  Share2,
  TrendingUp,
} from 'lucide-react'
import { formatDate } from '../format.js'

const STAT_ICONS = {
  views: Eye,
  likes: Heart,
  comments: MessageCircle,
  shares: Share2,
  saves: Bookmark,
  reach: TrendingUp,
}

function StatusBadge({ status }) {
  return (
    <span className={`badge-pill badge-status status-${status}`}>
      <span className="status-dot"></span>
      {status}
    </span>
  )
}

function LinkCell({ post }) {
  const hasMedia = Boolean(post.media_link)
  const hasPost = post.status === 'published' && Boolean(post.permalink)

  return (
    <td className="nowrap">
      {hasMedia && (
        <a className="link" href={post.media_link} target="_blank" rel="noopener">
          Media ↗
        </a>
      )}
      {hasPost && (
        <>
          {hasMedia && ' · '}
          <a className="link" href={post.permalink} target="_blank" rel="noopener">
            Post ↗
          </a>
        </>
      )}
      {!hasMedia && !hasPost && (
        post.status === 'publishing' ? (
          <span className="caption text-muted">…</span>
        ) : post.status === 'failed' ? (
          <span className="post-error" title={post.error}>{post.error}</span>
        ) : null
      )}
    </td>
  )
}

function StatsCell({ post }) {
  const show = post.status === 'published' && post.stats
  return (
    <td className="stats nowrap">
      {show ? (
        <>
          {Object.entries(STAT_ICONS).map(([key, Icon]) => (
            <span className="stat" title={key[0].toUpperCase() + key.slice(1)} key={key}>
              <Icon />
              {post.stats[key]}
            </span>
          ))}
          {post.insights_error && (
            <div className="post-error">{post.insights_error}</div>
          )}
        </>
      ) : (
        <span className="text-muted-soft">—</span>
      )}
    </td>
  )
}

export default function PostTable({ posts, onRefresh, onPublish }) {
  const [publishingId, setPublishingId] = useState(null)

  async function handlePublish(id) {
    setPublishingId(id)
    try {
      await onPublish(id)
    } finally {
      setPublishingId(null)
    }
  }

  if (!posts || posts.length === 0) {
    return (
      <div className="empty-state">
        <p className="display-sm">Nothing here yet.</p>
        <p className="body-md">
          Ask your first question above and the first carousel will land in the library.
        </p>
      </div>
    )
  }

  return (
    <div className="table-card">
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Question</th>
              <th>Short</th>
              <th>Long</th>
              <th>Date</th>
              <th>Status</th>
              <th>Link</th>
              <th>
                Stats{' '}
                <a
                  className="th-refresh"
                  href="#"
                  title="Refresh stats"
                  onClick={(e) => {
                    e.preventDefault()
                    onRefresh()
                  }}
                >
                  <RefreshCw />
                </a>
              </th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {posts.map((p) => {
              const canPublish = p.status === 'generated' || p.status === 'failed'
              const isPublishing = p.status === 'publishing'
              return (
                <tr key={p.id}>
                  <td className="q">
                    <div className="clamp">{p.question}</div>
                  </td>
                  <td>
                    <div className="clamp">{p.short}</div>
                  </td>
                  <td className="long">
                    <div className="clamp">{p.long}</div>
                  </td>
                  <td className="nowrap text-muted caption">{formatDate(p.created_at)}</td>
                  <td className="nowrap">
                    <StatusBadge status={p.status} />
                  </td>
                  <LinkCell post={p} />
                  <StatsCell post={p} />
                  <td className="nowrap">
                    {canPublish && (
                      <button
                        className="btn btn-primary btn-sm"
                        type="button"
                        onClick={() => handlePublish(p.id)}
                        disabled={publishingId === p.id || isPublishing}
                      >
                        {p.status === 'failed' ? 'Retry' : 'Post'}
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
