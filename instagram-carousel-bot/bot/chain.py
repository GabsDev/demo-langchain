import json
import uuid
import os
import re
import io
import requests
import traceback
from datetime import date
from typing import Optional
from pathlib import Path

from PIL import Image
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv
from twilio.rest import Client
from google import genai

from bot.config import Config
from bot.sessions import sessions, CarouselSession, CarouselSlide
from bot.utils import log, api_retry

load_dotenv()

os.environ.pop("GOOGLE_API_KEY", None)

TEMP_DIR = Path(__file__).parent.parent / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _upload_to_imgbb(filepath: Path) -> str | None:
    """Upload image to ImgBB and return public URL, or None on failure."""
    api_key = os.getenv("IMGBB_API_KEY", "")
    if not api_key:
        return None
    try:
        with open(filepath, "rb") as f:
            resp = requests.post(
                "https://api.imgbb.com/1/upload",
                data={"key": api_key},
                files={"image": f},
                timeout=30,
            )
        data = resp.json()
        if data.get("success"):
            url = data["data"]["url"]
            log.info("imgbb_uploaded", url=url)
            return url
        log.warning("imgbb_upload_failed", response=data)
    except Exception as e:
        log.warning("imgbb_upload_error", error=str(e))
    return None


@tool
@api_retry
def send_whatsapp(body: str) -> str:
    """Send a WhatsApp message to the user via Twilio.

    Args:
        body: Message text to send
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    sandbox = os.getenv("TWILIO_SANDBOX_NUMBER", "")
    to_number = Config.ALLOWED_NUMBER or os.getenv("YOWN_WHATSAPP_NUMBER", "")

    if not all([account_sid, auth_token, sandbox, to_number]):
        return "ERROR: Twilio or target number not configured"

    client = Client(account_sid, auth_token)
    message = client.messages.create(
        from_=f"whatsapp:{sandbox}",
        body=body,
        to=f"whatsapp:{to_number}",
    )
    log.info("whatsapp_sent", to=to_number, sid=message.sid)
    return f"Message sent: {message.sid}"


_image_count_today: int = 0
_last_reset_day: date = date.today()


def _check_image_limit() -> str | None:
    global _image_count_today, _last_reset_day
    today = date.today()
    if today != _last_reset_day:
        _image_count_today = 0
        _last_reset_day = today
    if _image_count_today >= Config.IMAGE_MAX_PER_DAY:
        return f"Daily image limit reached ({Config.IMAGE_MAX_PER_DAY}/day)"
    return None


@tool
@api_retry
def generate_image(prompt: str, aspect_ratio: str = "1:1") -> str:
    """Generate an image using Gemini Nano Banana 2.

    Args:
        prompt: Text description of the image to generate
        aspect_ratio: Aspect ratio (1:1, 16:9, 4:5, etc.)
    """
    limit_err = _check_image_limit()
    if limit_err:
        return f"ERROR: {limit_err}"

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return "ERROR: Gemini API key not configured"

    valid_ratios = {"1:1", "16:9", "4:3", "3:4", "4:5", "9:16", "2:3", "3:2"}
    if aspect_ratio not in valid_ratios:
        aspect_ratio = "1:1"

    log.info("gemini_calling", prompt_preview=prompt[:80])
    client = genai.Client(api_key=api_key)

    interaction = client.interactions.create(
        model=Config.IMAGE_MODEL,
        input=prompt,
    )

    if not interaction.output_image or not interaction.output_image.data:
        log.warning("gemini_no_image", prompt_preview=prompt[:80])
        return "ERROR: Gemini returned no image data"

    import base64
    b64_data = interaction.output_image.data
    if isinstance(b64_data, str):
        pad = 4 - len(b64_data) % 4
        if pad != 4:
            b64_data += "=" * pad
    image_bytes = base64.b64decode(b64_data)

    # Convert to RGB JPEG (Instagram-friendly format)
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize: longest side to 1080px, maintain aspect ratio
    max_dim = 1080
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = TEMP_DIR / filename
    img.save(filepath, "JPEG", quality=95, optimize=True)
    log.info("image_saved", filename=filename, size=img.size, mode="RGB")

    # Upload to ImgBB if configured (preferred for Meta access)
    public_url = _upload_to_imgbb(filepath)
    if not public_url:
        public_url = f"/temp/{filename}"
        log.info("using_local_url", url=public_url)
    else:
        log.info("using_imgbb_url", url=public_url)

    global _image_count_today
    _image_count_today += 1
    log.info("image_generated", prompt_preview=prompt[:60], url=public_url)
    return public_url


tools = [send_whatsapp, generate_image]
tool_names = [t.name for t in tools]

CAROUSEL_PROMPT = """Eres un experto en marketing de Instagram especializado en generación de leads y ventas.
Genera un carrusel persuasivo basado en el tema del usuario. El objetivo es educar, generar interés y motivar a la acción.

Debes:
1. Crear un título atractivo que capte atención
2. Crear **exactamente 2 slides**, cada uno con:
   - Un prompt visual detallado para generar una imagen (en español, estilo profesional y atractivo)
   - Un texto de copia persuasivo para ese slide (máximo 150 caracteres)
3. Un caption principal para el post (máximo 500 caracteres, con hashtags y llamado a la acción)
4. Una **call_to_action** corta y directa para el último slide (ej: "Contáctanos para implementarlo en tu empresa" o "Escríbeme si quieres saber más")

IMPORTANTE: Genera 2 imágenes exactamente. Para CADA slide, usa la herramienta generate_image con un prompt visual detallado.
Después de generar cada imagen, confirma. No es necesario enviar WhatsApp.

Devuelve un JSON con esta estructura:
{
    "topic": "tema del carrusel",
    "main_caption": "caption principal con hashtags y CTA",
    "call_to_action": "frase corta de llamado a la acción",
    "slides": [
        {"slide_number": 1, "visual_prompt": "...", "caption": "texto persuasivo del slide"}
    ]
}"""

model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
    api_key=Config.OPENAI_API_KEY,
)

agent = create_react_agent(model, tools)


async def generate_carousel(user_number: str, message_text: str) -> Optional[CarouselSession]:
    session = sessions.get_or_create(user_number, message_text)
    session.status = "generating"

    log.info("agent_starting", user=user_number, topic=message_text)

    try:
        result = await agent.ainvoke({
            "messages": [
                {"role": "system", "content": CAROUSEL_PROMPT},
                {"role": "user", "content": f"Tema: {message_text}"},
            ]
        })

        log.info("agent_finished", user=user_number, msg_count=len(result["messages"]))

        # Log tool calls and their results
        for i, msg in enumerate(result["messages"]):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    log.info("agent_tool_call",
                        idx=i, name=tc.get("name"), args=tc.get("args"))
            if hasattr(msg, "content") and msg.content:
                log.info("agent_message", idx=i, preview=str(msg.content)[:120])

        final_msg = result["messages"][-1].content if result["messages"] else ""
        log.info("agent_final_response", preview=str(final_msg)[:300])

        # Parse JSON from response
        try:
            json_match = re.search(r'\{.*"slides".*\}', str(final_msg), re.DOTALL)
            if json_match:
                carousel_data = json.loads(json_match.group())
            else:
                carousel_data = json.loads(str(final_msg))
        except (json.JSONDecodeError, AttributeError) as e:
            log.error("json_parse_failed", error=str(e), response=str(final_msg)[:500])
            session.status = "error"
            sessions.update(session)
            return None

        log.info("carousel_parsed", slides_count=len(carousel_data.get("slides", [])))

        session.main_caption = carousel_data.get("main_caption", "")
        session.call_to_action = carousel_data.get("call_to_action", "")
        session.topic = carousel_data.get("topic", message_text)

        # Extract image URLs from ToolMessage results
        tool_results = {}
        for msg in result["messages"]:
            if hasattr(msg, "tool_call_id") and hasattr(msg, "content"):
                tool_results[msg.tool_call_id] = msg.content

        slide_idx = 0
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.get("name") == "generate_image":
                        call_id = tc.get("id", "")
                        image_url = str(tool_results.get(call_id, "") or "")
                        args = tc.get("args", {})
                        slide = CarouselSlide(
                            slide_number=slide_idx + 1,
                            image_url=image_url,
                            caption=slide_idx < len(carousel_data.get("slides", []))
                                and carousel_data["slides"][slide_idx].get("caption", "")
                                or args.get("prompt", "")[:80],
                        )
                        session.slides.append(slide)
                        slide_idx += 1

        # Fallback: if no tool results, build from JSON
        if not session.slides:
            log.info("building_from_json_fallback")
            for slide_data in carousel_data.get("slides", []):
                slide = CarouselSlide(
                    slide_number=slide_data.get("slide_number", len(session.slides) + 1),
                    image_url="",
                    caption=slide_data.get("caption", ""),
                )
                session.slides.append(slide)

        session.status = "ready"
        sessions.update(session)
        log.info("carousel_generated", user=user_number, slides=len(session.slides))
        return session

    except Exception as e:
        log.error("carousel_generation_failed",
            error=str(e),
            traceback=traceback.format_exc(),
            user=user_number)
        session.status = "error"
        sessions.update(session)
        return None
