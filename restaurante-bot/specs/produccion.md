# Spec de Producción — Restaurante Bot (POC → Producción)

> Estado: borrador — lista de TODOs pendientes para llevar la POC a producción.
> Lenguaje de los artefactos: español (neutral/profesional). Código: inglés.

---

## 1. TODO — Rebuild atómico del índice RAG (PRIORIDAD ALTA)

**Problema actual (verificado en `app/rag/indexer.py`):**

`build_index(refresh=True)` ejecuta `shutil.rmtree(config.CHROMA_DIR)` (línea 83)
**antes** de llamar a `Chroma.from_documents()` (líneas 93–98), que hace la
llamada a OpenAI para generar embeddings.

**Consecuencia:** si la llamada a OpenAI falla a mitad de camino (red, cuota,
timeout), el índice viejo ya fue eliminado → el RAG queda **vacío** hasta que
una reconstrucción tenga éxito.

**Solución propuesta (cuando vayamos a producción):**

1. Construir el índice en un directorio temporal (`data/chroma.tmp-<uuid>`).
2. Recién **después** de que `Chroma.from_documents()` tenga éxito, reemplazar
   el directorio viejo por el nuevo (rename atómico, o borrar el viejo solo en
   ese punto).
3. En caso de fallo: eliminar el temporal y **preservar el índice anterior**.
4. `POST /menu/rebuild-index` ya existe y queda intacto; solo cambia la
   implementación interna de `build_index`.

**Impacto:** sin este fix, un fallo transitorio de OpenAI puede dejar al bot
sin respuestas de menú hasta la próxima reconstrucción manual exitosa.

**Archivos afectados:** `app/rag/indexer.py`, eventualmente `app/server.py`
(endpoint `POST /menu/rebuild-index`).

---

## 2. TODO — Autenticación en el dashboard KDS (PRIORIDAD ALTA)

- Hoy cualquiera en la red puede abrir `http://host:8000` y avanzar pedidos.
- **Propuesto:** token/HTTP Basic Auth en `/`, `/orders`, `/menu` y `/ws`;
  en producción detrás de HTTPS/reverse proxy.

## 3. TODO — Estado de conversación en memoria (PRIORIDAD MEDIA)

- El estado del bot vive en un dict; un reinicio pierde conversaciones en curso.
- **Propuesto:** Redis o estado persistido por DB (`user_id` → sesión).

## 4. TODO — Proceso único → escalar (PRIORIDAD MEDIA)

- Server + bot comparten un event loop y un SQLite; no escala horizontal.
- **Propuesto:** separar procesos (bot worker + API), SQLite → PostgreSQL,
  broadcaster de WebSocket dedicado (Redis pub/sub) para N pantallas.

## 5. TODO — Parseo de pedidos no determinista (PRIORIDAD MEDIA)

- La extracción con GPT-4o-mini puede leer mal un ítem.
- **Propuesto:** agregar validación de ítems contra el menú canónico antes de
  guardar + confirmación obligatoria con el cliente (ya existe, reforzar).

## 6. TODO — Scraping frágil (PRIORIDAD BAJA)

- Cambios en la estructura del sitio rompen la extracción.
- **Propuesto:** tests de regresión por fuente + revisión manual del output.

## 7. TODO — Rebuild del índice tras cambios de menú (PRIORIDAD MEDIA)

- Editar el menú en el dashboard no reconstruye el RAG automáticamente (por
  diseño). El bot responde con datos viejos hasta el rebuild manual/botón.
- **Propuesto:** disparar rebuild automático post-edición (con el fix atómico
  del punto 1) o invalidar/stale del índice en las respuestas.

## 8. TODO — Pagos e historial administrativo (PRIORIDAD BAJA)

- No hay pagos ni página admin de pedidos pasados (el dashboard solo tiene
  Historial de completados, últimos 50).
- **Propuesto:** historial completo con filtros + exportación CSV.

---

## Notas de diseño para producción

- Costo LLM: `gpt-4o-mini` + `text-embedding-3-small` (~US$1–3/mes a volumen
  chico). Revisar si conviene cachear respuestas RAG frecuentes.
- No loguear secretos: `app/config.py` ya expone `has_openai_key` /
  `has_telegram_token` como booleanos — mantener esa convención.
- `data/menu.md` es la fuente de verdad del menú; el dashboard y el bot leen
  de ahí. Mantener la edición web como única vía de escritura en producción.
