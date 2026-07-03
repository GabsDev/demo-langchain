from langchain_community.document_loaders import GoogleDriveLoader

credentials_path = "C:\\Projects\\demo_langchain\\Tema 3 - Cummunity - RAG\\credentials.json"
token_path = "C:\\Projects\\demo_langchain\\Tema 3 - Cummunity - RAG\\token.json"

loader = GoogleDriveLoader(
    folder_id="1bzvAwlAnwzlhtn9Z1jluf7w9c9M5uDQR",
    credentials_path=credentials_path,
    token_path=token_path,
    recursive=True
)

documents = loader.load()

print(f"Metadatos: {documents[0].metadata}")
print(f"Contenido: {documents[0].page_content}")