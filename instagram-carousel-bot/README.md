# Instagram Carousel Bot

**Proof of Concept** — Bot que recibe ideas por WhatsApp, genera carruseles de Instagram con IA, y los publica con un clic.

![Python](https://img.shields.io/badge/Python-3.14-blue)
![LangChain](https://img.shields.io/badge/LangChain-0.3-green)
![GPT-4o-mini](https://img.shields.io/badge/GPT--4o--mini-OpenAI-orange)
![Gemini](https://img.shields.io/badge/Gemini_3.1_Flash_AI-Google-blue)
![Instagram API](https://img.shields.io/badge/Instagram_Graph_API-v25.0-E4405F)
![Streamlit](https://img.shields.io/badge/Streamlit-1.42-FF4B4B)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## Tech Stack

| Capa | Tecnología | Propósito |
|---|---|---|
| **Agent Framework** | LangChain + LangGraph | Orquestación del agente con React agent |
| **LLM** | GPT-4o-mini | Generación de estructura del carrusel (título, slides, captions, CTA) |
| **Image Gen** | Gemini 3.1 Flash Lite (`gemini-3.1-flash-lite-image`) | Generación de imágenes por slide (~$0.067/imagen) |
| **Messaging** | Twilio WhatsApp Sandbox | Recepción de ideas del usuario |
| **Publishing** | Instagram Graph API v25.0 | Publicación de carruseles (soporta Instagram Login y Facebook Login) |
| **Image Hosting** | ImgBB | Hosting público de imágenes para que Meta pueda descargarlas |
| **Web Server** | Flask | Webhook de Twilio + API REST + servir imágenes |
| **UI** | Streamlit | Previsualización de slides + botón de publicar |
| **Tunneling** | ngrok (free) | Exponer webhook local a Twilio |

---

## Arquitectura

### Generation Flow

```
WhatsApp ──→ Twilio Sandbox
                    │
                    ▼
             Flask Webhook (/webhook)
                    │
                    ▼
         ┌─ LangGraph Agent ──────────────┐
         │    (generate_carousel)          │
         │                                 │
         │  GPT-4o-mini ──→ estructura JSON│
         │       │                         │
         │  Gemini Flash Lite ──→ 2 imágenes│
         │       │                         │
         │  ImgBB ──→ URLs públicas        │
         │       │                         │
         └───────┬─────────────────────────┘
                 │
          Session (memoria)
                 │
                 ▼
      Flask API (/latest-session)
                 │
                 ▼
        Streamlit UI (localhost:8501)
```

### Publish Flow

```
Streamlit UI ──click "Publicar"──→ Flask (/publish)
                                        │
                              (detecta token IGAA o EAA)
                                        │
                              graph.instagram.com o graph.facebook.com
                                        │
                              ┌── POST /{user}/media (imagen 1)
                              │── POST /{user}/media (imagen 2)
                              │── POST /{user}/media (CAROUSEL container)
                              └── POST /{user}/media_publish
                                        │
                                   Instagram Feed ✅
```

---

## Requisitos

- Python 3.11+
- Cuenta de OpenAI (API Key)
- Cuenta de Google Cloud (+ billing habilitado para Gemini)
- Cuenta de Twilio (crédito gratis $0.50)
- Cuenta de Facebook Developer (para Instagram API)
- Cuenta de ImgBB (gratis, para subir imágenes)
- ngrok (para exponer webhook local)

---

## Configuración paso a paso

### 1. OpenAI API Key

1. Ve a https://platform.openai.com/api-keys
2. Crea una API Key
3. Agrega a `.env`: `OPENAI_API_KEY=sk-...`

### 2. Google Gemini Flash Lite

1. Ve a https://aistudio.google.com → Inicia sesión
2. Click en **"Create API Key"** → **"Create API key in new project"**
3. Google crea un proyecto en Google Cloud automáticamente
4. **Habilitar billing:**
   - Ve a https://console.cloud.google.com/billing
   - Click **"Create billing account"**
   - Ingresa datos de pago (crédito gratis $300 cubre ~4,400 imágenes)
   - Linkea el billing account al proyecto de AI Studio
5. Agrega a `.env`: `GEMINI_API_KEY=AIza...`

### 3. Twilio (WhatsApp Sandbox)

1. Ve a https://twilio.com → Crea cuenta ($0.50 crédito gratis)
2. En el dashboard: anota **Account SID** y **Auth Token**
3. Ve a **Messaging → Try it Out → Send a WhatsApp message**
4. En **Sandbox** verás: número del sandbox y código de activación
5. **En tu WhatsApp**: envía el código al número del sandbox (ej: `join cheap-gloves`)
6. En `.env`:
   - `TWILIO_ACCOUNT_SID=AC...`
   - `TWILIO_AUTH_TOKEN=...`
   - `TWILIO_SANDBOX_NUMBER=+14155238886`
   - `YOWN_WHATSAPP_NUMBER=+506...` (tu número con código de país)

### 4. Instagram Graph API

Este bot soporta **los dos flujos de autenticación de Meta**:

#### Opción A: Instagram Login (recomendado — más simple, sin Facebook Page)

1. Ve a https://developers.facebook.com → **Create App** → Tipo: **Business**
2. Agrega **Instagram Graph API** → **Set Up**
3. Configura **Business Login for Instagram**
4. Genera un token con permisos: `instagram_business_basic`, `instagram_business_content_publish`
5. El token empieza con `IGAA...` y se usa contra `graph.instagram.com`
6. En `.env`:
   - `INSTAGRAM_ACCESS_TOKEN=IGAAYQ7RKy...`
   - *(INSTAGRAM_USER_ID es opcional — se resuelve automáticamente)*

#### Opción B: Facebook Login (requiere Facebook Page)

1. Conecta tu cuenta de Instagram profesional a una Facebook Page
2. Genera un **User Access Token** con permisos: `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`
3. Obtén tu **Instagram User ID**:
   - `GET graph.facebook.com/v25.0/me/accounts?access_token=TOKEN`
   - Busca la página conectada → obtén el `instagram_business_account.id`
4. En `.env`:
   - `INSTAGRAM_ACCESS_TOKEN=EAA...`
   - `INSTAGRAM_USER_ID=1784...`

### 5. ImgBB (hosting de imágenes)

1. Ve a https://api.imgbb.com/ → Regístrate gratis
2. Copia tu API Key
3. En `.env`: `IMGBB_API_KEY=9e15a9c001ff0d35187147a0a75b07dc`

### 6. ngrok

1. Ve a https://ngrok.com → Crea cuenta
2. Descarga e instala ngrok
3. Conecta tu cuenta: `ngrok config add-authtoken TU_TOKEN`
4. Para exponer el webhook: `ngrok http 5000`
5. Copia la URL `https://XXXX.ngrok-free.app`
6. En `.env`: `SERVER_PUBLIC_URL=https://XXXX.ngrok-free.app`

### 7. Configurar webhook en Twilio

1. Twilio Console → Messaging → WhatsApp Sandbox → **Sandbox Settings**
2. **WHEN A MESSAGE COMES IN**: pega `https://tu-ngrok.ngrok-free.app/webhook`
3. Method: **HTTP Post**
4. **Save**

---

## Instalación y ejecución

```bash
# Clonar e instalar
cd instagram-carousel-bot
pip install -e .

# Configurar variables de entorno (editar con tus credenciales)
copy .env.example .env

# Iniciar Flask (servidor principal + webhook)
python -m bot.main

# En otra terminal: iniciar ngrok
ngrok http 5000

# En otra terminal: iniciar Streamlit UI
streamlit run ui/app.py
```

### Archivo `.env.example`

```
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_SANDBOX_NUMBER=+14155238886
YOWN_WHATSAPP_NUMBER=+506...
INSTAGRAM_ACCESS_TOKEN=IGAA...
INSTAGRAM_USER_ID=            # Opcional (se resuelve automático para IGAA)
IMGBB_API_KEY=...
SERVER_PUBLIC_URL=https://XXXX.ngrok-free.app
FLASK_PORT=5000               # Opcional, default 5000
FLASK_SECRET_KEY=dev-secret   # Opcional, solo para sesiones
```

---

## Variables de Entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | API Key de OpenAI para GPT-4o-mini |
| `GEMINI_API_KEY` | ✅ | API Key de Google AI Studio para Gemini |
| `TWILIO_ACCOUNT_SID` | ✅ | SID de cuenta Twilio |
| `TWILIO_AUTH_TOKEN` | ✅ | Auth Token de Twilio |
| `TWILIO_SANDBOX_NUMBER` | ✅ | Número sandbox de Twilio (+14155238886) |
| `YOWN_WHATSAPP_NUMBER` | ✅ | Tu número de WhatsApp (+506...) |
| `INSTAGRAM_ACCESS_TOKEN` | Para publish | Token IGAA o EAA |
| `INSTAGRAM_USER_ID` | Para EAA tokens | ID de cuenta profesional de Instagram |
| `IMGBB_API_KEY` | Para publish | API Key de ImgBB para hosting de imágenes |
| `SERVER_PUBLIC_URL` | Para publish | URL pública de ngrok |
| `FLASK_PORT` | ❌ | Puerto del servidor Flask (default 5000) |
| `FLASK_SECRET_KEY` | ❌ | Secret key de Flask (default dev) |

---

## Uso

1. **Envía un tema** por WhatsApp al número sandbox de Twilio (ej: "Tips de productividad para developers")
2. **El bot responde**: confirma que comenzó la generación
3. **Abre** http://localhost:8501 (Streamlit UI)
4. **Ingresa tu número** de WhatsApp en la barra lateral (para asociar la sesión)
5. **El progreso se actualiza** automáticamente cada 3 segundos
6. **Previsualiza** los slides con título, imagen y caption
7. **Click "Publicar en Instagram"** — el carrusel se publica en tu feed
8. **O "Rechazar"** para generar otro

---

## Estructura del Proyecto

```
instagram-carousel-bot/
├── bot/
│   ├── __init__.py
│   ├── chain.py           # LangGraph agent + tools (generate_image, send_whatsapp)
│   ├── config.py           # Env vars + Instagram flow detection (IGAA vs EAA)
│   ├── main.py             # Flask server: webhook, publish, debug endpoints
│   ├── scheduler.py        # ThreadPoolExecutor for async message processing
│   ├── sessions.py         # In-memory session store (thread-safe dict)
│   └── utils.py            # structlog logging + tenacity retry decorator
├── ui/
│   ├── __init__.py
│   └── app.py              # Streamlit: auto-refresh, preview, publish button
├── mcp_servers/            # Legacy MCP servers (no longer used)
│   ├── __init__.py
│   ├── banana_pro_server.py
│   ├── instagram_server.py
│   └── whatsapp_server.py
├── temp/                   # Generated images (gitignored)
├── .env.example            # Template de variables de entorno
├── pyproject.toml          # Dependencias y metadatos del proyecto
└── README.md
```

---

## Límites (POC)

| Recurso | Límite | Notas |
|---|---|---|
| Imágenes/día | 5 | Configurable en `config.py` (`IMAGE_MAX_PER_DAY`) |
| Imágenes/carrusel | 2 | Forzado por prompt (carruseles de prueba ideales) |
| Usuarios | 1 | Single-user (filtro de número deshabilitado) |
| Estado | En memoria | Se pierde al reiniciar Flask |
| ngrok URL | Cambia en cada reinicio | Actualizar `SERVER_PUBLIC_URL` en `.env` |
| Publicaciones/24h | 50 (límite de Instagram) | Controlado en código |
| Tamaño imagen | Máx 1080px lado más largo | Redimensionado automáticamente en `chain.py` |

---

## Notas

- Las imágenes generadas por Gemini se convierten a JPEG RGB (máx 1080px), se suben a ImgBB, y se sirven desde ahí para que Meta pueda descargarlas sin depender de ngrok
- El bot detecta automáticamente si usas Instagram Login (token IGAA → `graph.instagram.com`) o Facebook Login (token EAA → `graph.facebook.com`)
- Es una **prueba de concepto** — no usar en producción sin: base de datos persistente, autenticación multi-usuario, manejo de errores robusto, y logging centralizado
- Los costos estimados por carrusel: ~$0.0003 (GPT-4o-mini) + ~$0.13 (2 imágenes Gemini) = ~$0.13 por publicación

---

## Roadmap / Ideas Futuras

- [ ] Base de datos persistente (SQLite → PostgreSQL)
- [ ] Multi-usuario con autenticación
- [ ] Programación de publicaciones (scheduler)
- [ ] Más de 2 slides por carrusel
- [ ] Soporte para Reels
- [ ] Análisis de engagement post-publicación
- [ ] Más modelos de imagen (DALL-E 3, Stable Diffusion)
