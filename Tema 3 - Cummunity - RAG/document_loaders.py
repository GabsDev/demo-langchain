from langchain_community.document_loaders import WebBaseLoader

loader = WebBaseLoader("https://techmind.ac/")

docs = loader.load()

print(docs)