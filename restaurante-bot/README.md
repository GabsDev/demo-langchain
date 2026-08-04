# Restaurante Bot — POC

Prueba de concepto: un bot de Telegram que toma pedidos de un restaurante en
español coloquial (o mediante opciones numeradas), respaldado por un sistema RAG
sobre un menú canónico, con pedidos enviados en tiempo real por WebSocket a un
dashboard tipo Kitchen Display System (KDS).

**Stack (la opción más económica):** GPT-4o-mini (LLM) + text-embedding-3-small
(embeddings) + ChromaDB (vector store local persistente) + LangChain +
python-telegram-bot + FastAPI/uvicorn + SQLite (stdlib).

---

## Qué hace

- **Bot de Telegram** (polling, sin webhook): opciones rápidas con `/start`,
  pedidos por texto libre ("hola, quiero una milanesa napolitana y una coca"),
  elección delivery/pickup, confirmación con el total y número de pedido para el
  cliente.
- **RAG**: el bot responde SOLO preguntas sobre el menú canónico; cualquier tema
  fuera de eso recibe un rechazo cortés.
- **Carga del menú** (3 vías → `data/menu.md` canónico):
  1. Manual: `app/menu/manual.py` (alta/edición/baja programática).
  2. PDF: `python scripts/ingest_pdf.py menu.pdf` (o desde el tab Menú del
     dashboard KDS con "Subir PDF del menú", que reemplaza todo el menú).
  3. Scraping web: `python scripts/scrape_menu.py https://...`.
- **Pedidos** en SQLite; cada pedido nuevo se transmite por WebSocket.
- **Dashboard KDS** en `http://localhost:8000/`: números grandes, tarjetas con
  gradiente por estado (Pendiente → En preparación → Completada), botones para
  avanzar el estado, sincronización en vivo entre varias pantallas abiertas,
  beep + pulso al recibir un pedido nuevo.

## Estimación de costos (restaurante chico)

| Servicio | Precio | Estimación mensual |
|---|---|---|
| GPT-4o-mini entrada | $0.15 / 1M tokens | ~500 preguntas del menú + ~300 pedidos/mes ≈ 2–3M tokens → **~$0.45** |
| GPT-4o-mini salida | $0.60 / 1M tokens | ~0.4M tokens de salida → **~$0.25** |
| text-embedding-3-small | $0.02 / 1M tokens | Indexación + ~300 consultas/mes → **< $0.01** |
| ChromaDB + SQLite + FastAPI | local | $0 |
| Telegram Bot API | gratis | $0 |

**Total aproximado: menos de $1/mes** para un restaurante chico (~50 pedidos +
~500 preguntas del menú/día sigue siendo de un dígito de dólares). El costo
dominante es la salida del chat; se mantiene mínimo a este volumen.

## Configuración (Windows, pwsh)

```powershell
cd C:\Projects\demo_langchain\restaurante-bot

# 1) Entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Dependencias
python -m pip install -r requirements.txt

# 3) Secretos — copiar la plantilla, nunca commitear el archivo real
Copy-Item .env.example .env
#   OPENAI_API_KEY  -> https://platform.openai.com/api-keys
#   TELEGRAM_BOT_TOKEN -> https://t.me/BotFather  (crear un bot, copiar el token)

# 4) Cargar el menú demo
python scripts/seed_menu.py

# 5) Construir el índice RAG (necesita OPENAI_API_KEY)
python scripts/rebuild_index.py

# 6) Ejecutar servidor + bot juntos
python run.py
```

Después abrí `http://localhost:8000/` para el KDS y escribile a tu bot en
Telegram. Los cambios de estado en el dashboard notifican al cliente por chat.

### Sin claves

Todo lo siguiente funciona sin `OPENAI_API_KEY`:

```powershell
python scripts/seed_menu.py
python -c "from app.menu.canonical import load_menu; m = load_menu('data/menu.md'); print(len(m.items))"
python run.py          # el servidor arranca en :8000; /health responde 200
```

La construcción del índice RAG y las llamadas al LLM devuelven un error claro
informando que falta la clave. ¿El bot también corre sin token? No — el bot
necesita `TELEGRAM_BOT_TOKEN` para hablar con Telegram; sin él solo corre el
servidor KDS.

### Otros scripts

```powershell
python scripts/ingest_pdf.py ruta\al\menu.pdf        # PDF -> data/menu.md
python scripts/scrape_menu.py https://ejemplo.com/menu  # URL -> data/menu.md
```

Sin `OPENAI_API_KEY` estos igual extraen/scrapean el texto crudo (sin limpieza
del LLM), así que hay que revisar la salida manualmente.

### Menús PDF de ejemplo (para probar el reemplazo por bot)

```powershell
python scripts/generate_sample_pdfs.py
```

Genera dos menús de muestra en `sample_menus/` (`menu_argentino.pdf` de
"El Gauchito" y `menu_mexicano.pdf` de "La Taquería"). Subí cualquiera de los
dos al bot de Telegram como documento PDF para probar el flujo de "reemplazar
todo el menú": el bot lo extrae, muestra un resumen (secciones/ítems) y pide
confirmación antes de sobrescribir `data/menu.md`.

El mismo reemplazo también se puede hacer desde el dashboard KDS: entrá al tab
**Menú**, elegí el PDF con "Subir PDF del menú" y confirmá el reemplazo; el
servidor guarda `data/menu.md` y reconstruye el índice RAG si hay clave
configurada.

## Actualizar el menú y el índice RAG

Después de cambiar o subir un menú distinto **no hace falta borrar ninguna
carpeta**. El rebuild del índice hace un reemplazo completo por API de Chroma:
borra los documentos viejos de la colección `menu` y agrega los nuevos, sin
tocar archivos en disco (funciona incluso con el server corriendo en Windows).

Dos botones en el tab **Menú** del KDS:

- **"Actualizar menú"** — recarga la lista de ítems Y reconstruye el índice RAG
  automáticamente (necesita `OPENAI_API_KEY`; si falta, muestra el error pero
  igual recarga la lista).
- **"Reconstruir índice RAG"** — reconstruye solo el índice, sin recargar la
  lista.

**Importante — nunca borrar `data/` completa.** Dentro de `data/` conviven
archivos que no se regeneran solos:

| Archivo | Qué es | ¿Se borra? |
|---|---|---|
| `data/menu.md` | Fuente de verdad del menú | NO |
| `data/menu.db` | Pedidos (SQLite) | NO — borrarlo borra el historial de pedidos |
| `data/menu.pdf` | PDF del menú | NO |
| `data/chroma/` | Índice RAG | Solo en caso extremo (ver abajo) |

El único caso en que conviene borrar `data/chroma/` es un índice corrupto o un
partir-de-cero absoluto. En ese caso: (1) parar primero los servers (`run.py`) —
en Windows los archivos de Chroma quedan bloqueados —, (2) borrar solo
`data/chroma/`, (3) reconstruir con `python scripts/rebuild_index.py`.

## Logging

Todo el flujo (config, menú, RAG, pedidos, WebSocket, HTTP y bot de Telegram)
escribe logs estructurados con timestamp, nivel, logger y mensaje.

**Nivel de log** — se configura con `LOG_LEVEL` en `.env` (o variable de
entorno):

```powershell
LOG_LEVEL=DEBUG    # máximo detalle: payloads, counts de retrieval, etc.
LOG_LEVEL=INFO     # por defecto: eventos de ciclo de vida
LOG_LEVEL=WARNING  # solo avisos y errores
```

**Qué se loguea por componente:**

- `app/config.py` — rutas, modelos, host/port y presencia de claves como
  booleanos (`has_openai_key=True/False`).
- `app/server.py` — cada request HTTP (método, path, status, ms), creación y
  cambio de estado de pedidos, conexión/desconexión WebSocket.
- `app/kds/ws.py` — conexiones (con total), broadcasts (tipo, order_id, nº de
  clientes).
- `app/orders/store.py` — init de la BD, creación de pedido (id, nº, items,
  total, entrega), transiciones de estado (`pending -> preparing`), counts.
- `app/rag/` — build del índice, pregunta truncada, docs recuperados, deflexión
  off-topic, llamadas al LLM.
- `app/bot/` — cada update de Telegram (update_id, usuario, texto truncado,
  callback), transiciones de la conversación, pedido creado y notificación al
  cliente.

**Garantía de no-secretos:** nunca se loguean `OPENAI_API_KEY`,
`TELEGRAM_BOT_TOKEN`, el contenido de `.env` ni headers de Authorization. Las
claves se reportan solo como booleanos; si algún helper necesita loguear un
secreto lo enmascara con `config.redact()`.

## Arquitectura

```
┌───────────────────────────┐   ┌──────────────────────────────────────────────────────────┐
│  Telegram (cliente)       │   │               FastAPI — un solo proceso (run.py)          │
│  · mensajes coloquiales   │   │                                                          │
│  · pedidos 1/2/3          │   │  ┌────────────────┐    ┌──────────────┐   ┌────────────┐  │
│  · subida de menú PDF ────┼──►│  │  bot/          │───►│  orders/     │──►│  SQLite    │  │
│  respuestas ◄─────────────┼───┤  │  telegram_bot  │    │  store.py    │   │  menu.db   │  │
└───────────────────────────┘   │  │  order_flow    │    └──────┬───────┘   └────────────┘  │
                                │  └───────┬────────┘           │ broadcast                 │
                                │          │ parse con LLM      │ order.created/updated     │
                                │          ▼                    ▼                           │
                                │  ┌───────────────┐    ┌───────────────┐                   │
                                │  │  rag/         │    │  kds/ws.py    │  WebSocket /ws    │
                                │  │  retriever    │    │  (manager)    │◄──────┐           │
                                │  │  indexer ─────┼───►│  (N pantallas)│       │           │
                                │  └───────┬───────┘    └──────┬────────┘       │           │
                                │          │                    │               │           │
┌───────────────────────────┐   │          │                    ▼               │           │
│  Dashboard web (empleados)│◄──┼──────────┼──────────┐  ┌──────────────┐       │  REST +   │
│  3 vistas:                │   │          │          │  │  server.py   │───────┘  WS      │
│  · Pedidos (live, blink)  │   │          │          │  │  (FastAPI)   │   /orders* /menu* │
│  · Historial (búsqueda)   │   │          │          │  └──────┬───────┘   /orders/history │
│  · Menú (CRUD + RAG)      │   │          │          │         │           /orders/clear-day│
└───────────────────────────┘   │          │          │         │                           │
                                │          │          │         │                           │
                                │          ▼          │         ▼                           │
                                │  ┌──────────────────┼──────────────┐                      │
                                │  │  menu/  canonical│ menu.md      │                      │
                                │  │  (fuente de      │ ◄─ PDF /     │                      │
                                │  │   verdad)        │    scraping /│                      │
                                │  └──────────────────┼──────────────┘                      │
                                │                     │  RAG index (ChromaDB)               │
                                └─────────────────────┼────────────────────────────────────┘
                                                      ▼
```

- `app/config.py` — configuración por entorno (`OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, nombres de modelos).
- `app/menu/` — modelo/parser de menú canónico, cargador de PDF, scraper, editor manual.
- `app/rag/` — indexador ChromaDB + cadena de recuperación con rechazo de temas fuera de menú.
- `app/orders/` — modelos Pydantic + store SQLite (flujo de estados, pedidos desde).
- `app/kds/` — gestor de conexiones WebSocket + archivos estáticos del dashboard.
- `app/bot/` — handlers de Telegram + máquina de estados de conversación.
- `app/server.py` — app FastAPI — `/`, `/health`, `/orders`, `/orders/history?date&q&status&limit`, `/orders/{id}/status`, `/orders/clear-day`, `/menu*` (CRUD + rebuild-index), WebSocket `/ws`.
- `scripts/` — seed, ingestión de PDF, scraping, reconstrucción del índice.
- `run.py` — levanta uvicorn + polling de Telegram juntos.
- `specs/` — todos los specs del proyecto (producción, decisiones, etc.); ver
  [`specs/README.md`](specs/README.md) para el índice y la convención.

## Roadmap: migración a WhatsApp

**Decisión (confirmada): Meta Cloud API directa** (no Twilio ni BSP). Twilio pasa las
tarifas de Meta + cobra `$0.005` por mensaje (entrante y saliente) + `$1–3/mes`
por número; los BSP (360dialog, Wati, Messaggio) cobran plataforma mensual y
markup. Para un proyecto integrado a mano con volumen chico, Cloud API directa
es la opción de menor costo: plataforma `$0`, pagás solo la tarifa de Meta.

**Precios clave (rate card 2026):**

- **Hoy (hasta sept 2026):** las conversaciones de servicio (el cliente escribe
  y respondés dentro de 24h) son **gratis e ilimitadas** → `$0/mes`.
- **Desde 1-oct-2026:** Meta cobra también los mensajes de servicio (~tarifa
  utility por mercado).
- **Costa Rica:** utility ~`$0.0085/mensaje`, marketing ~`$0.0114+`. Con
  ~300–500 interacciones/mes → ~`$10–30/mes` después de oct-2026.

```
FASE 0 — Decisión (hoy)
  [x] Confirmar: Meta Cloud API directa (no Twilio, no BSP) — HECHO

FASE 1 — Setup Meta (1–3 días, $0)
  [ ] Crear Facebook Business Manager
  [ ] Crear app en developers.facebook.com
  [ ] Obtener WABA + número de prueba (gratis, mensajear ~5 números)
  [ ] Verificar webhook: necesitás HTTPS público (ngrok/cloudflared en dev)

FASE 2 — Código (abstraer transporte)
  [ ] Extraer capa de transporte: hoy telegram_bot.py está acoplado a
      python-telegram-bot; separar la máquina de estados (order_flow,
      RAG, store, KDS) de la plataforma
  [ ] Adapter WhatsApp: endpoint POST /whatsapp/webhook (FastAPI ya
      levanta server, solo sumás una ruta)
  [ ] Mapear chat_id → wa_id (número de teléfono)
  [ ] Reemplazar botones inline de Telegram por interactive buttons de
      WhatsApp (funcionan dentro de la ventana de 24h)
  [ ] Subida de menú PDF: en Telegram llega el archivo; en WhatsApp hay
      que descargar media vía API (media id → GET)

FASE 3 — Producción CR (3–7 días)
  [ ] Número dedicado + nombre de negocio aprobado por Meta
  [ ] Verificación con cédula jurídica (para subir de tier y superar
      límites de mensajería)
  [ ] Templates UTILITY aprobados (confirmación de pedido, estado) en
      español CR — obligatorios para mensajes business-initiated
  [ ] Deploy con HTTPS estable (no ngrok en prod)

FASE 4 — Costos
  [ ] Aprovechar la ventana de 24h al máximo (todo dentro = gratuito
      hasta sept 2026)
  [ ] Medir mensajes/mes → proyectar bill post-oct-2026
```

**Advertencia:** no usar scrapers ni automatización de WhatsApp Web — Meta
banea el número y viola los TOS. Solo Cloud API oficial.

## Riesgos / no listo para producción

- **Estado de conversación en memoria** — el estado del bot vive en un dict; un
  reinicio del bot pierde las conversaciones en curso. Para producción se
  necesita Redis o estado respaldado por BD.
- **KDS sin autenticación** — cualquiera en la red puede abrir el dashboard y
  avanzar pedidos. Agregar un token/auth básica HTTP antes de desplegar.
- **Proceso único** — servidor + bot comparten un event loop y un archivo
  SQLite; está bien para la POC, no para escalar horizontalmente.
- **El parseo del LLM no es determinista** — la extracción del pedido puede
  leer mal algún ítem de vez en cuando; siempre confirmar el pedido completo
  con el cliente antes de guardarlo.
- **El scraping web es frágil** — cambios en la estructura del sitio rompen la
  extracción; la limpieza del LLM ayuda pero requiere revisión manual.
- **El recall del RAG es tan bueno como el índice** — el botón "Actualizar menú"
  reconstruye el índice automáticamente; no hace falta borrar `data/chroma` en
  el flujo normal.
- **Sin pagos / historial de pedidos UI** — los pedidos se guardan pero no hay
  página de administración para pedidos pasados.

## Deploy gratis: cómo compartir el bot con un cliente (roadmap)

**Resumen:** para este bot, serverless (Vercel/Cloudflare) NO sirve. El bot
tiene 4 bloqueadores de arquitectura que chocan con serverless:

| Componente | Cómo funciona hoy | Problema en serverless |
|---|---|---|
| **Telegram** | Long-polling (proceso siempre vivo) | Vercel/CF congelan el proceso; solo webhook funciona |
| **SQLite** (`data/menu.db`) | Archivo en disco | Filesystem efímero — se borra en cada deploy |
| **ChromaDB** (`data/chroma/`) | Archivo en disco | Ídem: el índice RAG desaparece |
| **WebSocket `/ws`** (KDS) | Conexión persistente | Vercel no lo soporta bien; CF necesita Durable Objects |

**Conclusión:** el único hosting gratis que corre el bot SIN cambios es una VM
siempre activa. Vercel Hobby además está limitado por ToS a proyectos
personales (no backends).

### Opciones free tier verificadas (2026)

| Plataforma | ¿Sirve? | Detalles |
|---|---|---|
| **Oracle Cloud Always Free** | ✅ Recomendada | Gratis para SIEMPRE: 2 AMD micro VMs + hasta 4 ARM vCPUs / 24 GB RAM, ~200 GB disco persistente. Requiere tarjeta para verificar (sin cargo). Catch: capacidad ARM se agota en algunas regiones. |
| **Render free tier** | ⚠️ Con asteriscos | Sin tarjeta, git push. Duerme a los 15 min (cold start 30–60s); disco efímero → pedidos e índice se pierden en cada redeploy. Bueno para demo corta. |
| **Fly.io** | ❌ | Ya no tiene free tier real (solo trial 2h). |
| **Railway** | ❌ | Solo trial 30 días ($5 crédito). |
| **Vercel** | ❌ | ToS: solo proyectos personales; no para backends. |

### Roadmap de deploy recomendado (todo gratuito)

```
PASO 0 — Seguridad ANTES de compartir (obligatorio)
  [ ] Agregar auth básica HTTP al dashboard KDS (usuario + contraseña,
      ~15 min con FastAPI). Sin esto, cualquiera con la URL puede
      avanzar/borrar pedidos.
  [ ] Proteger también los endpoints REST sensibles (/orders*).

PASO 1 — Oracle Cloud Always Free (20 min)
  [ ] Crear cuenta en cloud.oracle.com (tarjeta para verificar, sin cargo)
  [ ] Crear una VM ARM (VM.Standard.A1.Flex) en una región con capacidad
  [ ] Configurar SSH, firewall (abrir puerto 8000 o usar túnel)

PASO 2 — Subir y correr el bot en la VM
  [ ] git clone del repo en la VM
  [ ] python -m venv .venv && pip install -r requirements.txt
  [ ] Copiar .env con OPENAI_API_KEY y TELEGRAM_BOT_TOKEN
  [ ] Crear servicio systemd para que el bot corra 24/7 y se reinicie solo
      (Unit: restaurante-bot.service → ExecStart=.venv/bin/python run.py)

PASO 3 — URL pública linda (HTTPS)
  [ ] Cloudflare Tunnel gratuito (sin tarjeta) → https://demo-restaurante.com
  [ ] Alternativa: ngrok para demo rápida (URL cambia en cada reinicio)

PASO 4 — Compartir con el cliente
  [ ] Mandar la URL del KDS + credenciales de auth al cliente
  [ ] Mandar el link del bot de Telegram para que pruebe pedidos
  [ ] Explicar: bot toma pedidos, KDS muestra los pedidos en vivo

PASO 5 — Costos reales
  [ ] Hosting: $0 (Oracle Always Free)
  [ ] OpenAI API key: ~$1/mes a este volumen (RAG + LLM)
  [ ] Dominio propio: opcional (~$10/año) o usar subdominio de tunel gratis
```

**Nota:** la alternativa serverless (migrar a webhook + Postgres + vector DB
externa + SSE/Durable Objects) es viable pero son semanas de rework para un POC
— no vale la pena salvo que el cliente pida escalar de verdad.
