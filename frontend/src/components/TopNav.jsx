export default function TopNav({ loggedIn, username }) {
  return (
    <header className="top-nav">
      <div className="nav-inner">
        <a className="wordmark" href="/">
          do<span className="dot">.</span>you<span className="dot">.</span>know
          <span className="dot">.</span>7
        </a>
        <div className="nav-actions">
          {loggedIn ? (
            <>
              <span className="nav-user">@{username}</span>
              <a className="btn btn-outline btn-sm" href="/login">
                Reconnect
              </a>
            </>
          ) : (
            <a className="btn btn-primary btn-sm" href="/login">
              Connect Instagram
            </a>
          )}
        </div>
      </div>
    </header>
  )
}
