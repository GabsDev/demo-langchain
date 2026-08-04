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
- **Ver también:** decisión §10 (empezar con SQLite; migrar a PostgreSQL al
  separar procesos).

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

## 9. DECISIÓN — Ambientes: local + producción (sin staging) (ESTADO: aprobado)

> Decisión de arquitectura tomada para los primeros clientes. Aplica hasta que
> se cumpla UNA de las condiciones de revisión abajo.

**Decisión:** NO montar dev/staging/prod. Se usa **local** (desarrollo) +
**producción**, más disciplina operativa barata.

**Por qué:**

- Montar staging es infraestructura que no paga ningún cliente inicial. El
  proyecto corre en un solo proceso en una VM gratuita (Oracle Always Free);
  más ambientes = más mantenimiento, no más ventas.
- La pregunta correcta no es "¿cuántos ambientes?" sino "¿cuál es mi peor
  falla y cómo me recupero rápido?". Para un bot de comida: tocar datos reales
  de clientes reales (pedidos, teléfonos, direcciones) durante una prueba.

**Disciplina operativa que REEMPLAZA staging (obligatoria):**

1. **Backup antes de cada deploy**: copiar el SQLite de `data/` antes de
   actualizar. Restaurar en ~30 s si algo falla.
2. **Bot de prueba con token propio**: token de desarrollo (bot de Telegram
   personal) para smoke tests. NUNCA probar con el número del cliente.
3. **Rollback en minutos**: deploy = pull + reiniciar servicio. Taguear cada
   versión (`v1`, `v2`...) y poder revertir al tag anterior.
4. **Smoke test de 60 s post-deploy**: "hola" al bot de prueba, un pedido de
   ejemplo, verificar que llegue al KDS.
5. **Feature flags para lo riesgoso**: kill-switch por funcionalidad
   (desactivar IA si falla, activar WhatsApp solo para este cliente) sin
   re-deploy. Reutilizar el mecanismo de planes Básico/Pro/Premium.

**WhatsApp — el "ambiente de prueba" es del proveedor, no propio:**

- Meta Cloud API ya incluye un **número de teléfono de prueba (sandbox)** con
  lista de hasta 5 números permitidos. No hay que levantar infraestructura
  propia para probar el flujo WhatsApp.
- Probar SIEMPRE con el sandbox de Meta antes de activar el número real del
  restaurante (los mensajes a clientes reales no se desenvían).
- Ejemplo: sandbox = página de prueba de una impresora; staging propio =
  comprar una segunda impresora. Con WhatsApp basta la primera.

**Condiciones para REVISAR esta decisión (cualquiera dispara la revisión):**

- Integración con WhatsApp (el sandbox de Meta es el "staging" en ese punto).
- 5+ clientes con configuraciones distintas.
- Un contrato que pida SLA/garantía de disponibilidad explícita.

---

## 10. DECISIÓN — Base de datos: empezar con SQLite (ESTADO: aprobado)

> Aplica hasta que se cumpla UNA de las señales de migración abajo. La
> migración futura es a **PostgreSQL**, no a MariaDB.

**Decisión:** arrancar con **SQLite** (ya en uso en `app/orders/store.py`).
No migrar a MariaDB/PostgreSQL ahora.

**Por qué:**

- Bajo volumen y un solo proceso: decenas de pedidos/día, un solo servidor,
  bot + API comparten event loop. SQLite maneja millones de filas y escrituras
  concurrentes moderadas; estamos usando una fracción mínima de su capacidad.
- Cero infraestructura extra: backup = copiar el archivo de `data/`, sin
  servicio de DB que monitorear en la VM gratuita, sin consumo extra de RAM.
- MariaDB no aporta nada en este camino; PostgreSQL ya está en el roadmap.

**Señales para MIGRAR a PostgreSQL (cualquiera dispara la migración):**

1. **Múltiples procesos/instancias** (TODO #4 de este spec: separar bot worker
   + API + N pantallas KDS). SQLite con locks entre procesos se vuelve
   doloroso.
2. **Multi-sucursal real**: varios restaurantes escribiendo con reportes
   cruzados.
3. **Features que SQLite no tiene**: roles/usuario concurrentes, replicación,
   backup en caliente punto-en-tiempo.
4. **Volumen alto sostenido**: miles de pedidos/día.

**Cómo mantener la migración barata:** `app/orders/store.py` es la única capa
de acceso a datos. Cuando migremos, se cambia el backend del store (a
PostgreSQL) sin tocar el resto del bot. No acoplar SQL a otras capas.

---

## Notas de diseño para producción

- Costo LLM: `gpt-4o-mini` + `text-embedding-3-small` (~US$1–3/mes a volumen
  chico). Revisar si conviene cachear respuestas RAG frecuentes.
- No loguear secretos: `app/config.py` ya expone `has_openai_key` /
  `has_telegram_token` como booleanos — mantener esa convención.
- `data/menu.md` es la fuente de verdad del menú; el dashboard y el bot leen
  de ahí. Mantener la edición web como única vía de escritura en producción.
