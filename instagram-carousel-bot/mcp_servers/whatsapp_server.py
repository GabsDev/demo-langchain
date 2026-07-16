import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from dotenv import load_dotenv
from twilio.rest import Client
from bot.utils import log, api_retry

load_dotenv()

server = Server("whatsapp")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_SANDBOX_NUMBER = os.getenv("TWILIO_SANDBOX_NUMBER", "")


@server.tool()
@api_retry
async def send_message(to: str, body: str) -> str:
    """Send a WhatsApp message via Twilio.
    
    Args:
        to: Recipient phone number with country code (e.g. +521234567890)
        body: Message text to send
    
    Returns:
        Confirmation message with SID
    """
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SANDBOX_NUMBER]):
        return "ERROR: Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SANDBOX_NUMBER"

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    message = client.messages.create(
        from_=f"whatsapp:{TWILIO_SANDBOX_NUMBER}",
        body=body,
        to=f"whatsapp:{to}",
    )
    
    log.info("whatsapp_sent", to=to, sid=message.sid, body_preview=body[:50])
    return f"Message sent. SID: {message.sid}"


if __name__ == "__main__":
    from mcp.server.stdio import stdio_server
    
    import asyncio
    async def main():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    
    asyncio.run(main())
