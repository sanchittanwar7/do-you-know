import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchMe, fetchPosts, generatePost, publishDraft } from '../api.js'
import TopNav from '../components/TopNav.jsx'
import Composer from '../components/Composer.jsx'
import PostTable from '../components/PostTable.jsx'

export default function Home() {
  const navigate = useNavigate()
  const [me, setMe] = useState({ logged_in: false, username: '' })
  const [posts, setPosts] = useState(null)
  const [error, setError] = useState(null)
  const busyRef = useRef(false)

  const load = useCallback(async (refresh = false) => {
    if (busyRef.current) return
    busyRef.current = true
    try {
      const [meData, postsData] = await Promise.all([
        fetchMe(),
        fetchPosts(refresh),
      ])
      setMe(meData)
      setPosts(postsData.posts)
    } catch (e) {
      setError(e.message)
    } finally {
      busyRef.current = false
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Auto-refresh while any post is publishing (mirrors the original
  // `setTimeout(() => location.reload(), 3000)` behaviour).
  useEffect(() => {
    if (!posts || !posts.some((p) => p.status === 'publishing')) return
    const t = setTimeout(() => load(), 3000)
    return () => clearTimeout(t)
  }, [posts, load])

  async function handleGenerate(question) {
    const { draft_id } = await generatePost(question)
    navigate(`/preview/${draft_id}`)
  }

  async function handlePublish(draftId) {
    await publishDraft(draftId)
    await load()
  }

  return (
    <>
      <TopNav loggedIn={me.logged_in} username={me.username} />
      <Composer loggedIn={me.logged_in} onGenerate={handleGenerate} />
      <section id="library" className="section">
        <div className="container">
          <div className="section-head">
            <h2 className="display-lg">Your posts</h2>
          </div>
          {error && <div className="post-error">{error}</div>}
          <PostTable
            posts={posts}
            onRefresh={() => load(true)}
            onPublish={handlePublish}
          />
        </div>
      </section>
    </>
  )
}
