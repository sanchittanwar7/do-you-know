"""Flask application factory and API routes."""
import secrets
import threading
import time
import uuid
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, redirect, request, send_file, send_from_directory, session, url_for

from . import config
from . import deepseek
from . import imaging
from . import insights
from . import instagram
from . import storage
from . import supabase_store


def create_app():
    app = Flask(
        __name__,
        static_folder=None,
    )
    app.secret_key = config.FLASK_SECRET

    # ------------------------------------------------------------------ #
    # View-model builder (shared by the posts list endpoint)
    # ------------------------------------------------------------------ #
    def build_posts_view(force):
        token = storage.load_token()
        posts = storage.load_posts()
        now = int(time.time())
        page_token = token.get("page_access_token")
        for p in posts:
            if p.get("status") == "deleted":
                continue
            p["media_link"] = (
                supabase_store.supabase_folder_url(p["id"]) if p.get("image_urls") else None
            )
            p["stats"] = None
            p["insights_error"] = None
            # Permalink backfill: Instagram often returns it a while after publish.
            if (
                p.get("status") == "published"
                and p.get("media_id")
                and not p.get("permalink")
                and page_token
            ):
                pat = p.get("permalink_attempt_at", 0)
                if force or (now - pat) > 60:
                    p["permalink_attempt_at"] = now
                    try:
                        pl = instagram.wait_for_permalink(p["media_id"], page_token, tries=4)
                        if pl:
                            p["permalink"] = pl
                            p["updated_at"] = now
                    except Exception:
                        pass
                    storage.persist_post(p)
            if p.get("status") == "published" and p.get("media_id") and page_token:
                cached = p.get("insights")
                at = p.get("insights_at", 0)
                if cached is None or force or (now - at) > 600:
                    try:
                        cached = insights.fetch_post_insights(p["media_id"], page_token)
                        p["insights"] = cached
                        p["insights_at"] = now
                        storage.persist_post(p)
                    except insights.MediaNotFoundError:
                        # Post was deleted on Instagram; hide it from the table.
                        p["status"] = "deleted"
                        p["error"] = None
                        p["updated_at"] = now
                        storage.persist_post(p)
                        continue
                    except Exception as exc:
                        p["insights_error"] = str(exc)
                p["stats"] = insights.format_insights(cached or {})
        return [p for p in posts if p.get("status") != "deleted"]

    # ------------------------------------------------------------------ #
    # Auth (OAuth is a full-page redirect flow, kept server-side)
    # ------------------------------------------------------------------ #
    @app.route("/login")
    def login():
        if not config.META_APP_ID:
            return "Missing META_APP_ID. Add it to .env before connecting Instagram.", 500

        state = secrets.token_urlsafe(16)
        session["oauth_state"] = state
        params = {
            "client_id": config.META_APP_ID,
            "redirect_uri": config.REDIRECT_URI,
            "response_type": "code",
            "scope": config.SCOPES,
            "state": state,
        }
        oauth_url = (
            f"https://www.facebook.com/{config.GRAPH_VERSION}/dialog/oauth"
            f"?{urlencode(params)}"
        )
        return redirect(oauth_url)

    @app.route("/callback")
    def callback():
        if request.args.get("error"):
            description = request.args.get("error_description", request.args["error"])
            return f"OAuth failed: {description}", 400

        expected_state = session.pop("oauth_state", None)
        received_state = request.args.get("state")
        if (
            not expected_state
            or not isinstance(received_state, str)
            or not secrets.compare_digest(expected_state, received_state)
        ):
            return "OAuth state did not match. Start the login again.", 400

        code = request.args.get("code")
        if not code:
            return "OAuth failed: no authorization code returned.", 400

        try:
            short_token_response = requests.get(
                f"{config.GRAPH}/oauth/access_token",
                params={
                    "client_id": config.META_APP_ID,
                    "client_secret": config.META_APP_SECRET,
                    "redirect_uri": config.REDIRECT_URI,
                    "code": code,
                },
                timeout=30,
            )
            short_token_response.raise_for_status()
            short_lived_token = short_token_response.json()["access_token"]

            long_token_response = requests.get(
                f"{config.GRAPH}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": config.META_APP_ID,
                    "client_secret": config.META_APP_SECRET,
                    "fb_exchange_token": short_lived_token,
                },
                timeout=30,
            )
            long_token_response.raise_for_status()
            long_lived_token = long_token_response.json()["access_token"]

            account = instagram.get_connected_instagram_account(long_lived_token)
            r = requests.get(
                f"{config.GRAPH}/{account['ig_user_id']}",
                params={"fields": "username", "access_token": account["page_access_token"]},
                timeout=30,
            )
            r.raise_for_status()
        except (requests.RequestException, RuntimeError, KeyError):
            app.logger.warning("Instagram connection failed during token or Page-account lookup.")
            return (
                "Could not connect the Instagram account. Check the app credentials and "
                "Page link, then try again.",
                400,
            )

        storage.save_token(
            {
                "user_access_token": long_lived_token,
                "page_access_token": account["page_access_token"],
                "page_id": account["page_id"],
                "ig_user_id": account["ig_user_id"],
                "username": r.json().get("username", ""),
                "data_access_expires_at": long_token_response.json().get(
                    "data_access_expiration_time"
                ),
            }
        )
        return redirect("/")

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    @app.route("/api/me")
    def api_me():
        token = storage.load_token()
        logged_in = bool(token.get("page_access_token") and token.get("ig_user_id"))
        return jsonify(
            {
                "logged_in": logged_in,
                "username": token.get("username", ""),
            }
        )

    @app.route("/api/posts", methods=["GET"])
    def api_posts():
        force = request.args.get("refresh") == "1"
        posts = build_posts_view(force)
        return jsonify({"posts": posts})

    @app.route("/api/posts/<draft_id>", methods=["GET"])
    def api_post(draft_id):
        draft = storage.get_post(draft_id)
        if not draft:
            return jsonify({"error": "Draft not found."}), 404
        return jsonify({"draft": draft})

    @app.route("/api/generate", methods=["POST"])
    def api_generate():
        token = storage.load_token()
        if not token.get("page_access_token"):
            return jsonify({"error": "Instagram is not linked."}), 401

        body = request.get_json(silent=True) or {}
        question = (body.get("question") or "").strip()
        if not question:
            return jsonify({"error": "Question is required."}), 400

        short_answer, long_answer, hashtags = deepseek.generate_answers(question)
        caption = deepseek.build_caption(question, hashtags)
        draft_id = uuid.uuid4().hex[:12]
        paths = imaging.render_images(question, short_answer, long_answer, draft_id)

        image_urls = []
        try:
            image_urls = supabase_store.upload_to_storage(paths, draft_id)
        except Exception as exc:
            app.logger.warning("Supabase upload at generate failed: %s", exc)

        now = int(time.time())
        storage.upsert_post(
            {
                "id": draft_id,
                "question": question,
                "short": short_answer,
                "long": long_answer,
                "caption": caption,
                "hashtags": hashtags,
                "status": "generated",
                "image_urls": image_urls,
                "local_images": paths,
                "permalink": None,
                "media_id": None,
                "error": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        return jsonify({"draft_id": draft_id})

    def publish_in_background(post_id):
        token = storage.load_token()
        record = storage.get_post(post_id)
        if not record:
            return
        if not token.get("page_access_token"):
            record["status"] = "failed"
            record["error"] = "Instagram is not linked."
            record["updated_at"] = int(time.time())
            storage.upsert_post(record)
            return

        try:
            urls = record.get("image_urls") or supabase_store.upload_to_storage(
                record["local_images"], post_id
            )
            if not record.get("image_urls"):
                record["image_urls"] = urls
            caption = record.get("caption") or deepseek.build_caption(
                record.get("question", ""),
                record.get("hashtags", []),
            )
            media_id = instagram.publish_carousel(
                token["ig_user_id"], urls, caption, token["page_access_token"]
            )
            comment_id = instagram.post_comment(
                media_id,
                deepseek.build_comment(record.get("short", ""), record.get("long", "")),
                token["page_access_token"],
            )
            # Mark published as soon as Meta accepts the carousel — the permalink
            # resolves lazily and can lag behind the publish itself.
            record.update(
                {
                    "status": "published",
                    "media_id": media_id,
                    "comment_id": comment_id,
                    "permalink": None,
                    "error": None,
                    "updated_at": int(time.time()),
                }
            )
            storage.upsert_post(record)

            try:
                permalink = instagram.wait_for_permalink(
                    media_id, token["page_access_token"], tries=40
                )
                if permalink:
                    record["permalink"] = permalink
                    record["updated_at"] = int(time.time())
                    storage.upsert_post(record)
            except Exception:
                pass
        except Exception as exc:
            record.update(
                {"status": "failed", "error": str(exc), "updated_at": int(time.time())}
            )
        storage.upsert_post(record)

    @app.route("/api/posts/<draft_id>/publish", methods=["POST"])
    def api_publish(draft_id):
        record = storage.get_post(draft_id)
        if not record:
            return jsonify({"error": "Draft not found."}), 404
        record["status"] = "publishing"
        record["updated_at"] = int(time.time())
        storage.upsert_post(record)
        threading.Thread(
            target=publish_in_background, args=(draft_id,), daemon=True
        ).start()
        return jsonify({"status": "publishing"})

    # ------------------------------------------------------------------ #
    # Local image serving (preview slides)
    # ------------------------------------------------------------------ #
    @app.route("/img/<draft_id>/<int:n>")
    def image(draft_id, n):
        draft = storage.get_post(draft_id)
        if not draft or n >= len(draft.get("local_images", [])):
            return "Not found", 404
        rel = draft["local_images"][n]
        # Local paths are stored repo-relative (out/<draft>/n.jpg).
        path = config.BASE_DIR / rel
        if not path.is_file():
            return "Not found", 404
        return send_file(path, mimetype="image/jpeg")

    # ------------------------------------------------------------------ #
    # Frontend (React build) + SPA fallback
    # ------------------------------------------------------------------ #
    @app.route("/")
    def spa_index():
        return _serve_spa(app)

    @app.route("/<path:path>")
    def spa_fallback(path):
        # API/image/auth routes are registered above and take precedence.
        if path.startswith(("api/", "img/")):
            return "Not found", 404
        return _serve_spa(app)

    return app


def _serve_spa(app):
    dist = config.FRONTEND_DIST
    index = dist / "index.html"
    if index.is_file():
        return send_from_directory(dist, "index.html")
    return (
        "Frontend not built. Run `npm run build` in frontend/, or use the Vite dev "
        "server (http://localhost:5173) during development.",
        404,
    )


def repair_missing_permalinks():
    """Fill permalink for published posts where Meta hadn't returned it yet."""
    token = storage.load_token()
    if not token.get("page_access_token"):
        return
    for p in storage.load_posts():
        if p.get("status") == "published" and p.get("media_id") and not p.get("permalink"):
            try:
                pl = instagram.wait_for_permalink(p["media_id"], token["page_access_token"], tries=10)
                if pl:
                    p["permalink"] = pl
                    p["updated_at"] = int(time.time())
                    storage.upsert_post(p)
            except Exception:
                pass


app = create_app()
