"""Shared LLM helper to clean/structurize raw menu text into canonical markdown.

Works for both PDF extraction and scraped web text. If no OPENAI_API_KEY is
available it returns the raw text untouched (graceful degradation).
"""
from __future__ import annotations

import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app import config

logger = logging.getLogger(__name__)

CLEANUP_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Sos un asistente que estructura menús de restaurantes. A partir del "
            "texto crudo del menú, producí SOLO markdown canónico en español con "
            "este formato exacto:\n\n"
            "# Nombre del restaurante\n\n"
            "## Nombre de la sección (por ejemplo Entradas, Platos Fuertes, "
            "Bebidas, Postres)\n\n"
            "### Nombre del plato\n\n"
            "- Precio: ₡1234\n"
            "- Descripción: breve descripción\n"
            "- Tags: palabra1, palabra2\n\n"
            "Reglas:\n"
            "- No inventes platos ni precios que no estén en el texto.\n"
            "- Si no hay precio, poné ₡0.\n"
            "- No agregues explicaciones ni texto fuera del markdown.\n",
        ),
        ("human", "Texto crudo del menú:\n\n{raw_text}"),
    ]
)


def clean_with_llm(raw_text: str) -> tuple[str, bool]:
    """Return (markdown, used_llm). used_llm is False when no key is present."""
    if not config.has_openai_key():
        logger.info("OPENAI_API_KEY missing: returning raw menu text without LLM cleanup")
        return raw_text, False
    logger.info("LLM cleanup call started (%d char(s) of raw text)", len(raw_text))
    llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0)
    chain = CLEANUP_PROMPT | llm | StrOutputParser()
    try:
        result = chain.invoke({"raw_text": raw_text})
        logger.info("LLM cleanup call finished (%d char(s) returned)", len(result))
        return result.strip(), True
    except Exception:
        logger.exception("LLM cleanup failed, returning raw text")
        return raw_text, False
