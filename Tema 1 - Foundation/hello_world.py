from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

pregunta = "¿En qué año llegó el ser humano a la Luna por primera vez?"
print("Pregunta: ", pregunta)

respueta = llm.invoke(pregunta)
print("Respuesta del modelo: ", respueta.content)