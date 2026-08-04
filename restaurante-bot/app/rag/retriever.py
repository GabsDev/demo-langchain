"""RAG retrieval chain: answers ONLY menu questions, deflects everything else.

System prompt (Spanish) instructs the model to restrict itself to the retrieved
menu context. Hard guard: if retrieval returns nothing relevant, the bot refuses
politely.
"""
from __future__ import annotations

import logging

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app import config
from app.rag import indexer

logger = logging.getLogger(__name__)

DEFLECTION = "Solo puedo ayudarte con el menú y los pedidos del restaurante 😊"

SYSTEM_PROMPT = (
    "Sos el asistente virtual de un restaurante. Solo podés responder preguntas "
    "sobre el MENÚ de este restaurante y sobre pedidos. "
    "Usá EXCLUSIVAMENTE el contexto del menú que se te entrega. "
    "No inventes platos, precios, horarios ni información que no aparezca en el "
    "contexto. "
    "Si la pregunta del cliente NO es sobre el menú, respondé con este mensaje "
    "exacto y nada más: "
    f'"{DEFLECTION}" '
    "Respondé en español, de forma cálida y breve."
)

# Distance threshold for text-embedding-3-small (cosine distance). Below this we
# consider the question off-topic and refuse instead of hallucinating.
DISTANCE_THRESHOLD = 0.85

# Broad menu/catalog words. When threshold-filtered retrieval is thin but the
# question matches one of these, we fall back to the section/catalog summary
# documents instead of deflecting.
CATALOG_KEYWORDS = (
    "menú", "menu", "carta", "bebida", "bebidas", "plato", "platos",
    "comida", "comidas", "opciones", "tienen", "tiene", "venden", "vende",
    "qué hay", "que hay", "qué tienen", "que tienen", "recomendar",
    "recomendaciones", "sugerencias", "postre", "postres", "entrada",
    "entradas", "oferta", "ofertas", "especial", "especiales",
)


def _vectorstore() -> Chroma:
    config.require_openai_key()
    if not indexer.collection_exists():
        raise RuntimeError(
            "The menu index is not built. Run `python scripts/rebuild_index.py` "
            "with OPENAI_API_KEY configured, then retry."
        )
    return Chroma(
        collection_name=indexer.COLLECTION_NAME,
        persist_directory=str(config.CHROMA_DIR),
        embedding_function=OpenAIEmbeddings(model=config.EMBEDDING_MODEL),
    )


def _llm() -> ChatOpenAI:
    config.require_openai_key()
    return ChatOpenAI(model=config.OPENAI_MODEL, temperature=0.2)


def _mentions_catalog(question: str) -> bool:
    """True when the question contains a word hinting at a general menu query."""
    lowered = question.lower()
    return any(keyword in lowered for keyword in CATALOG_KEYWORDS)


def _catalog_fallback(vectorstore: Chroma, question: str) -> list[Document]:
    """Retrieve the section/catalog summary docs for a broad menu question.

    No distance threshold is applied: the summaries are the canonical answer
    source for "what do you sell?" questions. Uses a metadata `$in` filter and
    falls back to two separate per-type queries if the driver rejects it.
    """
    try:
        return vectorstore.similarity_search(
            question,
            k=8,
            filter={"type": {"$in": ["section", "catalog"]}},
        )
    except Exception:
        logger.warning(
            "Chroma `$in` metadata filter unsupported; "
            "falling back to per-type queries"
        )
        section_docs = vectorstore.similarity_search(
            question, k=8, filter={"type": "section"}
        )
        catalog_docs = vectorstore.similarity_search(
            question, k=8, filter={"type": "catalog"}
        )
        return section_docs + catalog_docs


def answer_question(question: str) -> str:
    """Answer a customer question using the RAG chain; deflect if off-topic."""
    config.require_openai_key()
    logger.info("RAG question received (truncated): %.200s", question)
    vectorstore = _vectorstore()
    results = vectorstore.similarity_search_with_score(question, k=8)
    docs = [doc for doc, distance in results if distance < DISTANCE_THRESHOLD]
    if len(docs) < 2 and _mentions_catalog(question):
        logger.debug(
            "Thin retrieval for a catalog-style question; "
            "using section/catalog documents"
        )
        docs = _catalog_fallback(vectorstore, question)
    logger.debug(
        "Retrieval for question: %d raw result(s), %d used as context",
        len(results), len(docs),
    )
    if not docs:
        logger.warning("No relevant context for question, deflecting (off-topic)")
        return DEFLECTION

    context = "\n\n".join(doc.page_content for doc in docs)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            (
                "human",
                "Contexto del menú:\n{context}\n\nPregunta del cliente: {question}",
            ),
        ]
    )
    try:
        logger.info("Calling LLM (%s) for RAG answer", config.OPENAI_MODEL)
        chain = prompt | _llm() | StrOutputParser()
        answer = chain.invoke({"context": context, "question": question})
        logger.info("RAG LLM call finished: %d char(s) returned", len(answer))
        return answer
    except Exception:
        logger.exception("RAG LLM call failed")
        raise
