import os
import sys
import base64
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from google import genai
from google.genai import types
from dotenv import load_dotenv
from bot.utils import log, api_retry

load_dotenv()

server = Server("banana_pro")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_ID = "gemini-3-pro-image-preview"
TEMP_DIR = Path(__file__).parent.parent / "temp"


@server.tool()
@api_retry
async def generate_image(prompt: str, aspect_ratio: str = "1:1") -> str:
    """Generate an image using Google Gemini Nano Banana Pro.
    
    Args:
        prompt: Text description of the image to generate
        aspect_ratio: Aspect ratio (1:1, 16:9, 4:5, etc.)
    
    Returns:
        Public URL of the generated image (temporary)
    """
    if not GEMINI_API_KEY:
        return "ERROR: Gemini API key not configured. Set GEMINI_API_KEY"

    valid_ratios = {"1:1", "16:9", "4:3", "3:4", "4:5", "9:16", "2:3", "3:2"}
    if aspect_ratio not in valid_ratios:
        aspect_ratio = "1:1"

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
            ),
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            image_bytes = base64.b64decode(part.inline_data.data)
            filename = f"{uuid.uuid4().hex}.png"
            filepath = TEMP_DIR / filename
            filepath.write_bytes(image_bytes)

            image_url = f"/temp/{filename}"
            log.info("image_generated", prompt_preview=prompt[:60], url=image_url)
            return image_url

    return "ERROR: No image data in response"


if __name__ == "__main__":
    from mcp.server.stdio import stdio_server
    
    import asyncio
    async def main():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    
    asyncio.run(main())
