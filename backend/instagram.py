"""Instagram Graph API operations (Facebook Login configuration)."""
import time

import requests

from .config import GRAPH, META_CONTENT_IS_AI_GENERATED, META_PAGE_ID


def get_connected_instagram_account(user_access_token):
    """Return the one Page-connected Instagram account used by this local app."""
    r = requests.get(
        f"{GRAPH}/me/accounts",
        params={
            "fields": "id,name,access_token,instagram_business_account",
            "access_token": user_access_token,
        },
        timeout=30,
    )
    r.raise_for_status()
    candidates = []
    for page in r.json().get("data", []):
        ig = page.get("instagram_business_account")
        if ig and ig.get("id") and page.get("access_token"):
            candidates.append(
                {
                    "page_id": page["id"],
                    "page_name": page.get("name", page["id"]),
                    "page_access_token": page["access_token"],
                    "ig_user_id": ig["id"],
                }
            )

    if META_PAGE_ID:
        candidates = [account for account in candidates if account["page_id"] == META_PAGE_ID]

    if not candidates:
        detail = f" matching META_PAGE_ID={META_PAGE_ID}" if META_PAGE_ID else ""
        raise RuntimeError(
            "No Page-connected Instagram Business/Creator account found"
            f"{detail}. Confirm the Page link and the requested permissions."
        )
    if len(candidates) > 1:
        page_names = ", ".join(account["page_name"] for account in candidates)
        raise RuntimeError(
            "More than one Page-connected Instagram account was found "
            f"({page_names}). Set META_PAGE_ID in .env to the Page you want to use."
        )
    return candidates[0]


def create_image_container(ig_user_id, image_url, page_access_token):
    r = requests.post(
        f"{GRAPH}/{ig_user_id}/media",
        params={
            "image_url": image_url,
            "is_carousel_item": "true",
            "access_token": page_access_token,
        },
        timeout=60,
    )
    data = r.json()
    if "id" not in data:
        raise RuntimeError(f"Image container failed: {data}")
    return data["id"]


def wait_for_container(container_id, page_access_token, tries=20):
    """Wait for a media container to finish processing before it is published."""
    for _ in range(tries):
        r = requests.get(
            f"{GRAPH}/{container_id}",
            params={"fields": "status_code,status", "access_token": page_access_token},
            timeout=30,
        )
        r.raise_for_status()
        status = r.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Media container {container_id} failed: {r.json()}")
        time.sleep(2)
    raise RuntimeError(f"Media container {container_id} did not finish processing in time.")


def publish_carousel(ig_user_id, image_urls, caption, page_access_token):
    child_ids = [
        create_image_container(ig_user_id, image_url, page_access_token)
        for image_url in image_urls
    ]
    for child_id in child_ids:
        wait_for_container(child_id, page_access_token)

    params = {
        "media_type": "CAROUSEL",
        "children": ",".join(child_ids),
        "caption": caption,
        "access_token": page_access_token,
    }
    if META_CONTENT_IS_AI_GENERATED:
        # Meta requires this on the parent carousel container, not its children.
        params["is_ai_generated"] = "true"
    r = requests.post(
        f"{GRAPH}/{ig_user_id}/media",
        params=params,
        timeout=60,
    )
    data = r.json()
    if "id" not in data:
        raise RuntimeError(f"Carousel container failed: {data}")
    carousel_id = data["id"]
    wait_for_container(carousel_id, page_access_token)

    r = requests.post(
        f"{GRAPH}/{ig_user_id}/media_publish",
        params={"creation_id": carousel_id, "access_token": page_access_token},
        timeout=60,
    )
    pub = r.json()
    if "id" not in pub:
        raise RuntimeError(f"Publish failed: {pub}")
    return pub["id"]


def post_comment(media_id, message, page_access_token):
    """Post the combined short + long answer as a comment on the media."""
    r = requests.post(
        f"{GRAPH}/{media_id}/comments",
        params={"message": message, "access_token": page_access_token},
        timeout=60,
    )
    data = r.json()
    if "id" not in data:
        raise RuntimeError(f"Comment failed: {data}")
    return data["id"]


def wait_for_permalink(media_id, page_access_token, tries=40):
    for _ in range(tries):
        # NOTE: `status_code` is only valid on *containers*, not on published
        # IG Media. Requesting it here returns a #100 error, so query only
        # fields that exist on media.
        r = requests.get(
            f"{GRAPH}/{media_id}",
            params={"fields": "permalink,shortcode", "access_token": page_access_token},
            timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        if d.get("permalink"):
            return d["permalink"]
        if d.get("shortcode"):
            return f"https://www.instagram.com/p/{d['shortcode']}/"
        time.sleep(3)
    return None
