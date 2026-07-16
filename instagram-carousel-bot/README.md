# Instagram Carousel Bot 📱

Bot que recibe ideas por WhatsApp, genera carruseles de Instagram con IA (GPT-4o-mini + Gemini Pro), y te permite previsualizar y publicar desde una UI web.

## Arquitectura

`
WhatsApp (Twilio) → Flask Webhook → LangGraph Agent → OpenAI GPT-4o-mini
                                                          ↓
                                                  Gemini Pro (imágenes)
                                                          ↓
                                                  Streamlit UI ← preview
                                                          ↓
                                                  Instagram Graph API
`

## Requisitos

- Python 3.11+
- Cuenta de OpenAI (API Key)
- Cuenta de Google Cloud (+ crédito gratis para Gemini Pro)
- Cuenta de Twilio (crédito gratis .50)
- Cuenta de Facebook Developer (para Instagram API)
- ngrok (para exponer webhook local)

## Configuración paso a paso

### 1. OpenAI API Key

1. Ve a https://platform.openai.com/api-keys
2. Crea una API Key
3. Cópiala al .env como OPENAI_API_KEY=sk-...

### 2. Google Gemini (Nano Banana Pro)

1. Ve a https://aistudio.google.com → Inicia sesión con tu cuenta Google
2. Click en **"Create API Key"** → **"Create API key in new project"**
3. Google crea un proyecto en Google Cloud automáticamente
4. **IMPORTANTE: Habilitar billing** (necesario aunque tengas crédito gratis):
   - Ve a https://console.cloud.google.com/billing
   - Click **"Create billing account"**
   - Ingresa tus datos de pago (no te cobrarán hasta que agotes los )
   - Linkea el billing account al proyecto que creó AI Studio
5. Los  de crédito gratis cubren ~2,200 imágenes a .134 c/u
6. Cópiala al .env como GEMINI_API_KEY=AIza...

### 3. Twilio (WhatsApp Sandbox)

1. Ve a https://twilio.com → Crea cuenta (recibes .50 crédito)
2. En el dashboard:
   - Anota **Account SID** y **Auth Token**
3. Ve a **Messaging → Try it Out → Send a WhatsApp message**
4. En la pestaña **Sandbox** verás:
   - Número del sandbox: +14155238886
   - Código de activación (ej: join cheap-gloves)
5. **En tu WhatsApp**: Envía el código al número del sandbox para activarlo
6. En .env:
   - TWILIO_ACCOUNT_SID=AC...
   - TWILIO_AUTH_TOKEN=...
   - TWILIO_SANDBOX_NUMBER=+14155238886
   - YOWN_WHATSAPP_NUMBER=+521... (tu número con código de país)

### 4. Instagram Graph API

1. Ve a https://developers.facebook.com → **Create App**
   - Tipo: **Business**
2. Ve a **Dashboard → Add Product → Instagram Graph API → Set Up**
3. En **Configuration**:
   - Conecta tu cuenta de Instagram profesional (creador o negocio)
4. Genera un **User Access Token** con estos permisos:
   - instagram_basic
   - instagram_content_publish
   - pages_show_list
5. Obtén tu **Instagram User ID**:
   - GET https://graph.facebook.com/v25.0/me/accounts?access_token=TOKEN
   - Busca la página conectada a Instagram
   - GET https://graph.facebook.com/v25.0/{page-id}?fields=instagram_business_account&access_token=TOKEN
6. En .env:
   - INSTAGRAM_ACCESS_TOKEN=EA...
   - INSTAGRAM_USER_ID=1784...

### 5. ngrok

1. Ve a https://ngrok.com → Crea cuenta
2. Descarga e instala ngrok
3. Conecta tu cuenta: 
grok config add-authtoken TU_TOKEN
4. Para exponer el webhook: 
grok http 5000
5. Copia la URL https://...ngrok.io

### 6. Configurar webhook en Twilio

1. En Twilio Console → Messaging → WhatsApp Sandbox → Sandbox Settings
2. En **WHEN A MESSAGE COMES IN**: pega https://tu-ngrok.ngrok.io/webhook
3. Method: **HTTP Post**
4. **Save**

## Instalación

`ash
# Clonar e instalar
cd instagram-carousel-bot
pip install -e .

# Configurar variables de entorno
copy .env.example .env
# Editar .env con tus credenciales

# Iniciar Flask (webhook)
python -m bot.main

# En otra terminal: iniciar ngrok
ngrok http 5000

# En otra terminal: iniciar Streamlit UI
streamlit run ui/app.py
`

## Uso

1. Envía un tema por WhatsApp al número del sandbox de Twilio
2. El bot responde: *"Generando carrusel..."*
3. Abre http://localhost:8501 (Streamlit)
4. Ingresa tu número de WhatsApp en la barra lateral
5. Ve el progreso de generación
6. Cuando esté listo: previsualiza los slides
7. Click **Publicar en Instagram** o **Rechazar**

## Límites

- **Instagram**: 50 posts/24h, max 10 imágenes por carrusel
- **Gemini Pro**: ~10 imágenes/minuto en Tier 1
- **OpenAI GPT-4o-mini**: ~500 requests/minuto

## Notas

- Las imágenes generadas se guardan temporalmente en 	emp/ y se sirven desde Flask
- No se requiere base de datos; el estado vive en memoria
- Es una **prueba de concepto** — no usar en producción sin mejoras de seguridad
