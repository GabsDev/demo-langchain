from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate


chat = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)


# SE DEFINE LA PLANTILLA  con la clase PromptTemplate  en donde:
# input_variables = Se ponen en una lista las variables que van a ser utilizadas
# template = Se pone el prompt con las variables a sustituir en {}
plantilla = PromptTemplate(
    input_variables=["nombre"],
    template="Saluda al usuario con su nombre. \nNombre del usuario: {nombre}\nAsistente:"
)


# IMPLEMENTACION DE CADENAS CON |
chain = plantilla | chat
resultado = chain.invoke({"nombre":"Gabriel"})
print(resultado.content)