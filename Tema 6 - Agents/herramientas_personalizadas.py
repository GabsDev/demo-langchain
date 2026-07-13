from langchain_core.tools import tool

@tool("Herramienta acceso base de datos usuarios", return_direct=True)
def herramienta_personalizada(query: str) -> str:
    """Consulta la base de datos de usuarios de la empresa."""
    # Codigo que accede a la base de datos
    return f"Respuesta a la consulta: {query}"

output = herramienta_personalizada.run("Consulta de prueba")
print(output)

print(f"Nombre de la herramienta: {herramienta_personalizada.name}")
print(f"Descripcion de la herramienta: {herramienta_personalizada.description}")