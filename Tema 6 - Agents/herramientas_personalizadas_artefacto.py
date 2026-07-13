from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from operator import attrgetter
from typing import Tuple

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

@tool("user_db_tool", response_format="content_and_artifact")
def herramienta_personalizada(query: str) -> Tuple[str, int]:
    """Consulta la base de datos de usuarios de la empresa y devuelve el resultado de la consulta."""
    return f"Respuesta a la consulta: {query}", 10

llm_with_tools = llm.bind_tools([herramienta_personalizada])

chain = llm_with_tools | attrgetter("tool_calls") | herramienta_personalizada.map()

response = chain.invoke("Genera un resumen de la informacion sobre el usuario UX341234 que se encuentra en nuestra base de datos.")

print(response)