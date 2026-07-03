from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import ChatOpenAI

# 1. Cargar el documento PDF
loader = PyPDFLoader("C:\\Projects\\demo_langchain\\Tema 3 - Cummunity - RAG\\quijote.pdf")
pages = loader.load()

# 2. Combinar todas las páginas en un texto único
full_text = ""
for page in pages:
    full_text += page.page_content + "\n"

# 3. Pasar el texto al LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
response = llm.invoke(f"Haz un resumen de los puntos mas importantes del siguiente documento: {full_text}")

print(response)