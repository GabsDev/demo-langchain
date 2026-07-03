# Configuración de modelos
EMBEDDING_MODEL = "text-embedding-3-large"
QUERY_MODEL = "gpt-4o-mini"
GENERATION_MODEL = "gpt-4o"

# Configuración del vector store
CHROMA_DB_PATH = "C:\\Projects\\demo_langchain\\Tema 3 - Cummunity - RAG\\chroma_db"

# Configuración del retriever
SEARCH_TYPE = "mmr"
MMR_DIVERSITY_LAMBDA = 0.7
MMR_FETCH_K = 20
SEARCH_K = 2

# Configuracion alternativa para retriever hibrido
ENABLE_HYBRID_SEARCH = True
SIMILARITY_THRESHOLD = 0.70