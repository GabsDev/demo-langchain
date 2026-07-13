from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from langchain_core.tools import tool

from langchain_community.tools.gmail.search import GmailSearch
from langchain_community.tools.gmail.get_message import GmailGetMessage
from langchain_community.tools.gmail.get_thread import GmailGetThread
from langchain_community.tools.gmail.create_draft import GmailCreateDraft
from langchain_community.tools.gmail.send_message import GmailSendMessage
from langchain_community.tools.gmail.utils import build_resource_service

import os
import base64

from email.mime.text import MIMEText


# =====================================================
# CONFIGURACIÓN
# =====================================================

original_dir = os.getcwd()

os.chdir(r"C:\Projects\demo_langchain\Tema 6 - Agents")


# =====================================================
# GMAIL API
# =====================================================

api_resource = build_resource_service()


# =====================================================
# HERRAMIENTA PERSONALIZADA
# =====================================================

@tool
def create_gmail_reply_draft(
    message: str,
    to: str,
    subject: str,
    thread_id: str,
    in_reply_to: str = None,
) -> str:
    """
    Crea un borrador de RESPUESTA dentro del mismo hilo.

    Utiliza el thread_id del correo original para que Gmail
    lo considere una respuesta y no un correo nuevo.
    """

    try:

        mime_message = MIMEText(
            message,
            "plain",
            "utf-8",
        )

        mime_message["To"] = to
        mime_message["Subject"] = subject

        if in_reply_to:
            mime_message["In-Reply-To"] = in_reply_to
            mime_message["References"] = in_reply_to

        encoded_message = base64.urlsafe_b64encode(
            mime_message.as_bytes()
        ).decode("utf-8")

        draft_body = {
            "message": {
                "raw": encoded_message,
                "threadId": thread_id,
            }
        }

        draft = (
            api_resource.users()
            .drafts()
            .create(
                userId="me",
                body=draft_body,
            )
            .execute()
        )

        return (
            "Borrador de respuesta creado correctamente.\n"
            f"Draft ID: {draft['id']}\n"
            f"Thread ID: {thread_id}"
        )

    except Exception as e:

        return f"Error creando borrador: {e}"


# =====================================================
# TOOLS
# =====================================================

tools = [

    GmailSearch(
        api_resource=api_resource
    ),

    GmailGetMessage(
        api_resource=api_resource
    ),

    GmailGetThread(
        api_resource=api_resource
    ),

    GmailCreateDraft(
        api_resource=api_resource
    ),

    GmailSendMessage(
        api_resource=api_resource
    ),

    create_gmail_reply_draft,
]

# =====================================================
# MODELO
# =====================================================

model = init_chat_model(
    "openai:gpt-4o",
    temperature=0,
)


# =====================================================
# PROMPT DEL AGENTE
# =====================================================

system_prompt = """

Eres mi asistente profesional de ingenieria de software de correo electrónico.

Tu objetivo es procesar el correo más reciente de la bandeja
de entrada y preparar una respuesta profesional en ingles.

Sigue este flujo:

1. Busca el correo más reciente de la bandeja de entrada
   utilizando las herramientas de Gmail.

2. Obtén el contenido completo del correo.

3. Extrae la información necesaria:
   
   - email del remitente original
   - asunto original
   - contenido del mensaje
   - thread_id del correo
   - message_id si está disponible


4. Analiza el correo y redacta una respuesta profesional,
   clara y adecuada al contexto y mi experiencia de 8 años como desarrollador de software. Ademas me intersa el puesto de AEM frontend, si te preguntan (0-10, 10 = expert level) pon todo en 8 o 9.


5. Crea un borrador utilizando SIEMPRE:

   create_gmail_reply_draft


La respuesta debe cumplir:

- "message":
    Debe contener únicamente la respuesta que enviarías
    al remitente.

- "to":
    Debe ser exactamente el email del remitente original.

- "subject":
    Debe conservar el asunto original.
    Si no empieza por "Re:", añade "Re:".

- "thread_id":
    Debe ser siempre el thread_id obtenido del correo original.


REGLAS IMPORTANTES:

- Nunca inventes message_id.
- Nunca inventes thread_id.
- Nunca crees un correo nuevo si existe un thread_id.
- El borrador debe pertenecer al mismo hilo.
- Si falta información necesaria, explica qué falta.
- No envíes correos; solamente crea borradores.


Cuando termines, informa brevemente qué acción realizaste.
"""


# =====================================================
# CREACIÓN DEL AGENTE LANGCHAIN 1.3.11
# =====================================================

agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=system_prompt,
    debug=True,
)

# =====================================================
# EXTRAER RESPUESTA DEL AGENTE
# =====================================================


def _extract_assistant_output(result: dict) -> str:
    """
    Extrae el último mensaje generado por el agente.

    En LangChain 1.x los resultados contienen una lista
    de mensajes dentro de la clave 'messages'.
    """

    messages = result.get("messages", [])

    for message in reversed(messages):

        # Solo buscamos mensajes del modelo
        if getattr(message, "type", None) != "ai":
            continue

        content = getattr(
            message,
            "content",
            "",
        )

        if isinstance(content, str):
            return content

        if isinstance(content, list):

            text_parts = []

            for part in content:

                if (
                    isinstance(part, dict)
                    and part.get("type") == "text"
                ):
                    text_parts.append(
                        part.get("text", "")
                    )

                elif isinstance(part, str):
                    text_parts.append(part)

            return "\n".join(
                p for p in text_parts if p
            )

        return str(content)

    return str(result)


# =====================================================
# PROCESAR EMAIL
# =====================================================

def process_latest_email():

    try:

        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Procesa el email más reciente "
                            "de la bandeja de entrada y "
                            "genera un borrador de respuesta "
                            "profesional."
                        ),
                    }
                ]
            }
        )

        return _extract_assistant_output(
            response
        )

    except Exception as e:

        print(
            f"Error procesando email: {e}"
        )

        return f"Error: {e}"

# =====================================================
# EJECUCIÓN PRINCIPAL
# =====================================================


if __name__ == "__main__":

    result = process_latest_email()

    print("\n" + "=" * 60)
    print("RESULTADO DEL AGENTE")
    print("=" * 60)

    print(result)

    print("=" * 60)
