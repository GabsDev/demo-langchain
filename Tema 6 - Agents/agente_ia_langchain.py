from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_community.tools.gmail.search import GmailSearch
from langchain_community.tools.gmail.get_message import GmailGetMessage
from langchain_community.tools.gmail.get_thread import GmailGetThread
from langchain_community.tools.gmail.create_draft import GmailCreateDraft
from langchain_community.tools.gmail.send_message import GmailSendMessage
from langchain_community.tools.gmail.utils import build_resource_service
import os
 

# Configurar el directorio de trabajo
original_dir = os.getcwd()
os.chdir(r"C:\Projects\demo_langchain\Tema 6 - Agents")

# Configurar las herramientas de Gmail directamente sin usar GmailToolkit
api_resource = build_resource_service()
tools = [
    GmailSearch(api_resource=api_resource),
    GmailGetMessage(api_resource=api_resource),
    GmailGetThread(api_resource=api_resource),
    GmailCreateDraft(api_resource=api_resource),
    GmailSendMessage(api_resource=api_resource),
]
 
# Configurar modelo del agente que soporte tool calling
model = init_chat_model("openai:gpt-4o", temperature=0)
 
# Prompt de agente que define su comportamiento
system_prompt = """Eres un asistente de email profesional. Para procesar emails sigue EXACTAMENTE estos pasos:
 
    1. PRIMERO: Usa 'search_gmail' con query 'in:inbox' y max_results=1 para obtener solo el mensaje más reciente en la bandeja de entrada.
    
    2. SEGUNDO: De la lista obtenida, identifica el message_id del email más reciente (el primer resultado).
    
    3. TERCERO: Usa 'get_gmail_message' con el message_id real obtenido en el paso anterior para obtener el contenido completo.
    
    4. CUARTO: Analiza el email y EXTRAE esta información crítica:
       - Thread ID (busca "Thread ID:" en el contenido)
       - Remitente original (busca "From:" y extrae el email)
       - Asunto original (busca "Subject:")
       - Contenido principal del mensaje
    
    5. QUINTO: Genera una respuesta profesional y apropiada en español.
    
    6. SEXTO: Usa 'create_gmail_draft' para crear un borrador de RESPUESTA (no email nuevo) con:
       - "message": tu respuesta generada
       - "subject": "Re: [asunto original]" (si no empieza ya con "Re:")
       - "to": email del remitente original
       - "thread_id": el Thread ID extraído del paso 4 (MUY IMPORTANTE para que sea una respuesta)
 
    CRÍTICO PARA RESPUESTAS:
    - SIEMPRE incluye "thread_id" en create_gmail_draft para que sea una respuesta, no un email nuevo
    - El "to" debe ser el email del remitente original
    - El "subject" debe empezar con "Re:" si no lo tiene ya
 
    IMPORTANTE: 
    - NUNCA uses message_id hardcodeados como '1' o '2' 
    - SIEMPRE obtén los IDs reales de los mensajes primero
    - Sin thread_id, el borrador será un email nuevo, no una respuesta
    - Si no encuentras thread_id, informa el problema pero intenta crear el borrador igual
    
    Si encuentras errores, explica qué información falta y por qué."""
 
# Crear agente con verbose y configuración de iteraciones
agent = create_agent(
    model=model, 
    tools=tools, 
    system_prompt=system_prompt,
    debug=True  # Activar verbose para ver pasos del agente
)
 
 
def _extract_assistant_output(result: dict) -> str:
    messages = result.get("messages", [])
    for message in reversed(messages):
        msg_type = getattr(message, "type", None)
        if msg_type != "ai":
            continue
 
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif isinstance(part, str):
                    text_parts.append(part)
            return "\n".join(part for part in text_parts if part)
        return str(content)
 
    return str(result)
 
def process_latest_email():
    try:
        # max_iterations=10 limita el número de iteraciones para evitar bucles infinitos
        response = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Procesa el email más reciente en la bandeja de entrada y genera un borrador de respuesta profesional.",
                    }
                ]
            },
            config={"max_iterations": 10}  # Limitar iteraciones para evitar loops
        )
        return _extract_assistant_output(response)
    except Exception as e:
        print(f"Error al procesar email: {str(e)}")
        return f"Error {str(e)}"
    
# Ejecutar
if __name__ == "__main__":
    result = process_latest_email()
    print("\n" + "="*50)
    print("RESULTADO:")
    print("="*50)
    print(result)