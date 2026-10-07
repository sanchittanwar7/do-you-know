"""S3-compatible uploads to Supabase Storage."""
import boto3

from .config import (
    BASE_DIR,
    IMG_KEY_PREFIX,
    SUPABASE_BUCKET,
    SUPABASE_ENDPOINT,
    SUPABASE_KEY,
    SUPABASE_PUBLIC_BASE,
    SUPABASE_REGION,
    SUPABASE_SECRET,
)


def supabase_client():
    return boto3.client(
        "s3",
        endpoint_url=SUPABASE_ENDPOINT,
        aws_access_key_id=SUPABASE_KEY,
        aws_secret_access_key=SUPABASE_SECRET,
        region_name=SUPABASE_REGION,
        config=boto3.session.Config(s3={"addressing_style": "path"}),
    )


def _resolve(path):
    """Accept repo-relative paths (out/<draft>/n.jpg) stored in posts.json."""
    p = BASE_DIR / path
    return str(p)


def upload_to_storage(local_paths, draft_id):
    if not (SUPABASE_ENDPOINT and SUPABASE_KEY and SUPABASE_SECRET and SUPABASE_BUCKET):
        raise RuntimeError("Supabase storage is not configured. Set SUPABASE_* in .env.")
    client = supabase_client()
    urls = []
    for i, p in enumerate(local_paths):
        key = f"{IMG_KEY_PREFIX}/{draft_id}/{i}.jpg"
        client.upload_file(
            _resolve(p), SUPABASE_BUCKET, key, ExtraArgs={"ContentType": "image/jpeg"}
        )
        urls.append(f"{SUPABASE_PUBLIC_BASE}/{key}")
    return urls


def supabase_folder_url(draft_id):
    """Dashboard link to the folder in the public bucket holding a draft's images."""
    if not (SUPABASE_ENDPOINT and SUPABASE_BUCKET):
        return None
    try:
        ref = SUPABASE_ENDPOINT.split("//")[1].split(".")[0]
    except IndexError:
        return None
    folder = f"{IMG_KEY_PREFIX}/{draft_id}"
    return (
        f"https://supabase.com/dashboard/project/{ref}/storage/files/buckets/"
        f"{SUPABASE_BUCKET}?path={folder}"
    )
