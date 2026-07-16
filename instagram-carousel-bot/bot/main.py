import uuid
import asyncio
import os
import time
import traceback
import requests
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_file
from twilio.request_validator import RequestValidator
from dotenv import load_dotenv

from bot.config import Config
from bot.scheduler import run_async
from bot.sessions import sessions
from bot.chain import generate_carousel
from bot.utils import log, api_retry

load_dotenv()

app = Flask(__name__)
app.secret_key = Config.FLASK_SECRET_KEY
validator = RequestValidator(Config.TWILIO_AUTH_TOKEN)

# Ensure temp directory exists
Config.TEMP_DIR.mkdir(parents=True, exist_ok=True)


@app.route("/webhook", methods=["POST"])
def webhook():
    """Twilio WhatsApp webhook - receives messages async."""
    # Validate Twilio signature
    url = request.url
    params = request.form.to_dict()
    signature = request.headers.get("X-Twilio-Signature", "")

    if False:  # skip signature validation for POC
        log.warning("invalid_twilio_signature")
        return jsonify({"error": "Invalid signature"}), 403

    from_number = params.get("From", "").replace("whatsapp:", "")
    body = params.get("Body", "").strip()

    if not from_number or not body:
        return jsonify({"error": "Missing From or Body"}), 400

    # Single-user mode: reject if not allowed number
    if False:  # skip number filter for POC
        log.info("rejected_unauthenticated_user", user=from_number)
        return jsonify({"error": "Unauthorized number"}), 403

    log.info("whatsapp_received", from_=from_number, body=body[:100])

    # Acknowledge immediately (Twilio requires response within 15s)
    # Processing happens async
    run_async(_process_message, from_number, body)

    return str(""), 200


def _process_message(user_number: str, text: str):
    """Process message in background thread (runs async)."""
    try:
        asyncio.run(generate_carousel(user_number, text))
    except Exception as e:
        log.error("processing_failed", error=str(e), user=user_number)


@app.route("/temp/<filename>")
def serve_temp(filename: str):
    """Serve temporary generated images."""
    filepath = Config.TEMP_DIR / filename
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404
    ext = Path(filename).suffix.lower()
    mimetype = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    return send_file(
        str(filepath),
        mimetype=mimetype,
        as_attachment=False,
        download_name=filename,
    )


@app.route("/status/<user_number>")
def get_status(user_number: str):
    session = sessions.get(user_number)
    if not session:
        return jsonify({"status": "no_session"})
    return jsonify(session.to_dict())


@app.route("/latest-session")
def latest_session():
    session = sessions.get_latest()
    if not session:
        return jsonify({"status": "no_session"})
    return jsonify(session.to_dict())


_ig_post_timestamps: list[float] = []


def _ig_rate_limit_ok() -> str | None:
    now = time.time()
    cutoff = now - 86400
    recent = [t for t in _ig_post_timestamps if t > cutoff]
    _ig_post_timestamps.clear()
    _ig_post_timestamps.extend(recent)
    if len(recent) >= 50:
        wait = int(min(recent) + 86400 - now)
        return f"Rate limit (50/24h). Try again in {wait // 60}m"
    return None


def _resolve_ig_user_id(access_token: str) -> str | None:
    """Resolve Instagram User ID from token via /me for Instagram Login flow."""
    host = Config.instagram_graph_host()
    flow = Config.instagram_flow()
    if flow == "instagram-login":
        try:
            resp = requests.get(
                f"{host}/me",
                params={"fields": "user_id", "access_token": access_token},
            )
            data = resp.json()
            resolved = data.get("user_id") or data.get("id")
            log.info("ig_user_resolved", flow=flow, resolved=resolved)
            return resolved
        except Exception as e:
            log.error("ig_user_resolve_failed", error=str(e))
            return None
    return None


@app.route("/debug")
def debug():
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    ig_id = os.getenv("INSTAGRAM_USER_ID", "")
    pub_url = Config.SERVER_PUBLIC_URL

    env_file = Path(__file__).parent.parent / ".env"
    env_exists = env_file.exists()

    flow = Config.instagram_flow()
    host = Config.instagram_graph_host()

    imgbb_key = os.getenv("IMGBB_API_KEY", "")

    return jsonify({
        "instagram_token_exists": bool(token),
        "instagram_token_prefix": token[:10] + "..." if len(token) > 10 else "too_short",
        "instagram_token_length": len(token),
        "instagram_flow": flow,
        "instagram_api_host": host,
        "instagram_user_id": ig_id or "not_set",
        "imgbb_api_key_exists": bool(imgbb_key),
        "server_public_url": pub_url,
        "env_file_exists": env_exists,
    })


@app.route("/publish", methods=["POST"])
def publish():
    data = request.get_json(silent=True) or {}
    user_number = data.get("user_number", "")

    log.info("publish_requested", user=user_number)

    session = sessions.get(user_number)
    if not session:
        log.warning("publish_no_session", user=user_number)
        return jsonify({"error": "No session found"}), 404
    if session.status != "ready":
        log.warning("publish_wrong_status", status=session.status)
        return jsonify({"error": f"Session status is {session.status}, not ready"}), 400

    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    ig_user_id = os.getenv("INSTAGRAM_USER_ID", "")

    log.info("publish_creds",
        token_exists=bool(access_token),
        token_length=len(access_token),
        token_prefix=access_token[:15] + "..." if access_token else "EMPTY",
        ig_user_id=ig_user_id or "EMPTY",
    )

    if not access_token:
        return jsonify({"error": "INSTAGRAM_ACCESS_TOKEN is empty. Check .env file"}), 400

    flow = Config.instagram_flow()
    graph_host = Config.instagram_graph_host()
    if not ig_user_id or flow == "instagram-login":
        resolved = _resolve_ig_user_id(access_token)
        if resolved:
            ig_user_id = resolved
        elif not ig_user_id:
            return jsonify({"error": "Could not resolve IG User ID from token. Set INSTAGRAM_USER_ID in .env"}), 400

    rate_err = _ig_rate_limit_ok()
    if rate_err:
        log.warning("publish_rate_limited")
        return jsonify({"error": rate_err}), 429

    server_url = Config.SERVER_PUBLIC_URL
    slides = session.slides
    caption = session.main_caption or session.topic
    api_version = "v25.0"
    graph_url = f"{graph_host}/{api_version}"

    log.info("publish_starting",
        slides=len(slides),
        flow=flow,
        host=graph_host,
        server_url=server_url,
        caption_preview=caption[:60],
    )

    try:
        child_ids = []
        for idx, slide in enumerate(slides):
            img_url = slide.image_url
            if img_url.startswith("/"):
                img_url = f"{server_url}{img_url}"

            log.info("publish_creating_media",
                idx=idx, img_url=img_url,
                user_id=ig_user_id,
                img_url_exists=bool(img_url),
            )

            resp = requests.post(
                f"{graph_url}/{ig_user_id}/media",
                params={
                    "image_url": img_url,
                    "is_carousel_item": "true",
                    "access_token": access_token,
                },
            )
            data = resp.json()
            log.info("publish_media_response",
                idx=idx, status=resp.status_code,
                response_keys=list(data.keys()),
            )

            if "id" not in data:
                error_msg = data.get("error", {}).get("message", str(data))
                log.error("publish_media_failed",
                    idx=idx, error=error_msg,
                    full_response=data,
                )
                return jsonify({"error": f"Media {idx} failed: {error_msg}"}), 400

            child_ids.append(data["id"])
            log.info("media_container_created", idx=idx, id=data["id"])

        children_str = ",".join(child_ids)
        log.info("publish_creating_carousel", children=children_str)

        resp = requests.post(
            f"{graph_url}/{ig_user_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": children_str,
                "caption": caption,
                "is_ai_generated": "true",
                "access_token": access_token,
            },
        )
        data = resp.json()
        log.info("publish_carousel_response",
            status=resp.status_code,
            response_keys=list(data.keys()),
        )

        if "id" not in data:
            error_msg = data.get("error", {}).get("message", str(data))
            log.error("publish_carousel_failed", error=error_msg, full_response=data)
            return jsonify({"error": f"Carousel container failed: {error_msg}"}), 400

        container_id = data["id"]
        log.info("carousel_container_created", id=container_id)

        resp = requests.post(
            f"{graph_url}/{ig_user_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": access_token,
            },
        )
        data = resp.json()
        log.info("publish_final_response",
            status=resp.status_code,
            response_keys=list(data.keys()),
        )

        if "id" not in data:
            error_msg = data.get("error", {}).get("message", str(data))
            log.error("publish_final_failed", error=error_msg, full_response=data)
            return jsonify({"error": f"Publish failed: {error_msg}"}), 400

        _ig_post_timestamps.append(time.time())
        session.status = "published"
        session.carousel_container_id = container_id
        sessions.update(session)

        media_id = data["id"]
        log.info("carousel_published", media_id=media_id)
        return jsonify({"status": "published", "media_id": media_id})

    except Exception as e:
        log.error("publish_exception", error=str(e), traceback=traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/test-img")
def test_image():
    """Test if images are accessible via SERVER_PUBLIC_URL (ngrok)."""
    from urllib.parse import urljoin
    server = Config.SERVER_PUBLIC_URL
    files = list(Config.TEMP_DIR.glob("*.jpg")) + list(Config.TEMP_DIR.glob("*.png"))
    if not files:
        return jsonify({"error": "No image files in temp", "server_url": server})
    filename = files[0].name
    test_url = f"{server}/temp/{filename}"

    results = {}
    # test 1: local serve
    local_path = Config.TEMP_DIR / filename
    results["local_file_exists"] = local_path.exists()
    results["local_file_size"] = local_path.stat().st_size if results["local_file_exists"] else 0

    # test 2: fetch via SERVER_PUBLIC_URL using common UAs
    for label, ua in [
        ("no_ua", ""),
        ("curl", "curl/8.0"),
        ("chrome", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0"),
        ("meta", "META-AGENT"),
    ]:
        try:
            hdrs = {"User-Agent": ua} if ua else {}
            r = requests.get(test_url, headers=hdrs, timeout=10)
            results[f"fetch_{label}"] = {
                "status": r.status_code,
                "content_length": len(r.content),
                "content_type": r.headers.get("Content-Type", ""),
                "first_bytes_hex": r.content[:20].hex() if r.content else "empty",
            }
        except Exception as e:
            results[f"fetch_{label}"] = {"error": str(e)}

    return jsonify({
        "test_url": test_url,
        "server_url": server,
        "results": results,
    })


if __name__ == "__main__":
    Config.validate()
    log.info("starting_flask", port=Config.FLASK_PORT)
    app.run(host="0.0.0.0", port=Config.FLASK_PORT, debug=True)
