from langchain.agents import create_agent
from langgraph_supervisor import create_supervisor
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Definir herramientas personalizadas
@tool
def buscar_web(query: str) -> str:
    """Buscar informacion en la web."""
    return f"Resultados de busqueda para: {query}"

@tool
def calcular(expresion: str) -> str:
    """Realizar calculos matematicos."""
    return f"Resultado: {eval(expresion)}"

# Crear agentes especializados
agente_investigacion = create_agent(
    model=model,
    tools=[buscar_web],
    prompt="Eres un especialista en investigacion web.",
    name="investigador"
)

agente_matematicas = create_agent(
    model=model,
    tools=[calcular],
    prompt="Eres un especialista en calculos matematicos.",
    name="matematico"
)

# Crear supervisor que coordina los agentes
supervisor_graph = create_supervisor(
    [agente_matematicas, agente_investigacion],
    model=model,
    prompt="Eres un supervisor que delega tareas a especialistas segun el tipo de consulta."
)

supervisor = supervisor_graph.compile()

# Uso del sistema multi-agente
response = supervisor.invoke({
    "messages": [{
        "role": "user",
        "content": "Busca informacion sobre las ultimas tendencias en inteligencia artificial generativa."
    }]
})

for msg in response['messages']:
    print(msg.content)