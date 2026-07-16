import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
import requests
from dotenv import load_dotenv
from bot.utils import log, api_retry

load_dotenv()

server = Server("instagram")

ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
IG_USER_ID = os.getenv("INSTAGRAM_USER_ID", "")
API_VERSION = "v25.0"
GRAPH_URL = f"https://graph.facebook.com/{API_VERSION}"

# Simple in-memory rate limit tracker
_post_timestamps: list[float] = []


def _check_rate_limit() -> str | None:
    """Check if we're under the 50 posts per 24h limit."""
    now = time.time()
    cutoff = now - 86400
    # Keep only timestamps from last 24h
    recent = [t for t in _post_timestamps if t > cutoff]
    _post_timestamps.clear()
    _post_timestamps.extend(recent)
    
    if len(recent) >= 50:
        oldest = min(recent)
        wait = int(oldest + 86400 - now)
        return f"Rate limit reached (50/24h). Try again in {wait // 60}m {wait % 60}s"
    return None


def _get_server_url() -> str:
    """Get the public URL of the Flask server from env or use a placeholder."""
    return os.getenv("SERVER_PUBLIC_URL", "http://localhost:5000")


@server.tool()
@api_retry
async def create_carousel(image_urls: list[str], caption: str) -> str:
    """Create a carousel container on Instagram.
    
    First creates individual media containers for each image, 
    then bundles them into a carousel container.
    
    Args:
        image_urls: List of public image URLs (max 10)
        caption: Main caption for the carousel post
    
    Returns:
        Carousel container ID or error message
    """
    if not ACCESS_TOKEN or not IG_USER_ID:
        return "ERROR: Instagram not configured. Set INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID"

    if len(image_urls) > 10:
        return f"ERROR: Max 10 images per carousel, got {len(image_urls)}"

    rate_err = _check_rate_limit()
    if rate_err:
        return rate_err

    server_url = _get_server_url()
    child_ids = []

    # Step 1: Create individual media containers
    for idx, img_url in enumerate(image_urls):
        # Make sure URL is absolute
        if img_url.startswith("/"):
            img_url = f"{server_url}{img_url}"

        resp = requests.post(
            f"{GRAPH_URL}/{IG_USER_ID}/media",
            params={
                "image_url": img_url,
                "is_carousel_item": "true",
                "access_token": ACCESS_TOKEN,
            },
        )
        data = resp.json()
        
        if "id" not in data:
            return f"ERROR creating media {idx}: {data.get('error', {}).get('message', str(data))}"
        
        child_ids.append(data["id"])
        log.info("carousel_item_created", idx=idx, container_id=data["id"])

    # Step 2: Create carousel container with children
    children_str = ",".join(child_ids)
    resp = requests.post(
        f"{GRAPH_URL}/{IG_USER_ID}/media",
        params={
            "media_type": "CAROUSEL",
            "children": children_str,
            "caption": caption,
            "is_ai_generated": "true",
            "access_token": ACCESS_TOKEN,
        },
    )
    data = resp.json()

    if "id" not in data:
        return f"ERROR creating carousel: {data.get('error', {}).get('message', str(data))}"

    log.info("carousel_container_created", container_id=data["id"], slides=len(child_ids))
    return data["id"]


@server.tool()
@api_retry
async def publish(container_id: str) -> str:
    """Publish a carousel container to Instagram.
    
    Args:
        container_id: The carousel container ID from create_carousel
    
    Returns:
        Published media ID or error message
    """
    if not ACCESS_TOKEN or not IG_USER_ID:
        return "ERROR: Instagram not configured."

    rate_err = _check_rate_limit()
    if rate_err:
        return rate_err

    resp = requests.post(
        f"{GRAPH_URL}/{IG_USER_ID}/media_publish",
        params={
            "creation_id": container_id,
            "access_token": ACCESS_TOKEN,
        },
    )
    data = resp.json()

    if "id" not in data:
        return f"ERROR publishing: {data.get('error', {}).get('message', str(data))}"

    # Record the publish timestamp for rate limiting
    _post_timestamps.append(time.time())
    
    log.info("carousel_published", media_id=data["id"])
    return f"Published! Media ID: {data['id']}"


if __name__ == "__main__":
    from mcp.server.stdio import stdio_server
    
    import asyncio
    async def main():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    
    asyncio.run(main())
