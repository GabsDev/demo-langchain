# Spec de Deploy Gratis — Restaurante Bot

> Estado: borrador — roadmap de implementación para publicar el bot en hosting
> gratis y compartirlo con un cliente.
> Lenguaje de los artefactos: español (neutral/profesional). Código: inglés.

---

## 0. Decisión de arquitectura (verificada 2026)

**Serverless (Vercel / Cloudflare Workers) NO sirve para este bot.** Cuatro
bloqueadores de arquitectura chocan con serverless:

| Componente | Cómo funciona hoy | Problema en serverless |
|---|---|---|
| **Telegram** | Long-polling (proceso siempre vivo) | Vercel/CF congelan el proceso; solo webhook funciona |
| **SQLite** (`data/menu.db`) | Archivo en disco | Filesystem efímero — se borra en cada deploy |
| **ChromaDB** (`data/chroma/`) | Archivo en disco | Ídem: el índice RAG desaparece |
| **WebSocket `/ws`** (KDS) | Conexión persistente | Vercel no lo soporta bien; CF necesita Durable Objects |

**Decisión:** usar una VM siempre activa en el free tier. Opciones verificadas:

| Plataforma | ¿Sirve? | Detalles |
|---|---|---|
| **Oracle Cloud Always Free** | ✅ Recomendada | Gratis para SIEMPRE: 2 AMD micro VMs + hasta 4 ARM vCPUs / 24 GB RAM, ~200 GB disco persistente. Requiere tarjeta para verificar (sin cargo). Catch: capacidad ARM se agota en algunas regiones. |
| **Render free tier** | ⚠️ Con asteriscos | Sin tarjeta, git push. Duerme a los 15 min (cold start 30–60s); disco efímero → pedidos e índice se pierden en cada redeploy. Bueno para demo corta. |
| **Fly.io** | ❌ | Ya no tiene free tier real (solo trial 2h). |
| **Railway** | ❌ | Solo trial 30 días ($5 crédito). |
| **Vercel** | ❌ | ToS: solo proyectos personales; no para backends. |

**Costos reales:** hosting `$0` (Oracle Always Free); OpenAI API key
`~US$1–3/mes` a este volumen (RAG + LLM); dominio propio opcional
(`~US$10/año`) o subdominio gratis del túnel.

---

## 1. TODO — Autenticación en el dashboard KDS (PRIORIDAD ALTA, PREREQUISITO)

> Ya documentado en `produccion.md` §2. Es el PASO 0 del deploy: NO compartir
> la URL pública sin esto.

- Agregar HTTP Basic Auth (usuario + contraseña) a `/`, `/orders`, `/menu` y
  `/ws` (WebSocket: validar token en el handshake).
- Detrás de HTTPS/reverse proxy en producción (Cloudflare Tunnel provee TLS).
- Credenciales por variable de entorno (`KDS_USER` / `KDS_PASS`), nunca
  hardcodeadas; respetar la convención de `config.redact()` en logs.

**Archivos afectados:** `app/server.py` (middleware/guard de rutas),
`app/kds/ws.py` (handshake), `app/config.py` (nuevas variables), `app/kds/static`
(login si se elige token por header).

---

## 2. TODO — VM Oracle Cloud Always Free (PRIORIDAD ALTA)

- Crear cuenta en `cloud.oracle.com` (tarjeta para verificación, sin cargo).
- Provisionar una instancia ARM (`VM.Standard.A1.Flex`) en una región con
  capacidad disponible; alternativa segura: 2× AMD micro.
- Configurar SSH (llaves, no contraseña), firewall (solo 22 y 8000, o nada si
  se usa túnel), snapshot/boot volume < 200 GB.

**Entregable:** acceso SSH a una VM Linux lista para el proyecto.

---

## 3. TODO — Subir y correr el bot como servicio (PRIORIDAD ALTA)

- `git clone` del repo en la VM.
- `.venv` + `pip install -r requirements.txt` (Python 3.14 si la distro lo
  tiene; ajustar a 3.11–3.13 si no — verificar compatibilidad de
  `langchain_chroma`).
- Copiar `.env` (nunca commitearlo): `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`,
  `KDS_USER`, `KDS_PASS`, `HOST=0.0.0.0`, `PORT=8000`.
- **Servicio systemd** `restaurante-bot.service`:
  - `ExecStart=/ruta/.venv/bin/python run.py`
  - `Restart=always`, `RestartSec=5`
  - `WorkingDirectory` y `EnvironmentFile` apuntando al `.env`
  - Logs a `journalctl` (estructurados, sin secretos).
- Probar `curl localhost:8000/health` → 200.

**Entregable:** bot corriendo 24/7 que se reinicia solo ante crashes.

---

## 4. TODO — URL pública HTTPS (PRIORIDAD ALTA)

- **Recomendado:** Cloudflare Tunnel gratuito (sin tarjeta) → hostname propio
  (p. ej. `https://demo-restaurante.com`) con TLS automático.
  - `cloudflared tunnel login` + `cloudflared tunnel create` + config DNS.
  - Correr `cloudflared` como segundo servicio systemd.
- **Alternativa rápida:** ngrok (URL cambia en cada reinicio; solo para demo
  corta).

**Entregable:** URL HTTPS estable para el KDS y para el webhook de Telegram.

---

## 5. TODO — Telegram: mantener polling o migrar a webhook (PRIORIDAD MEDIA)

- Con VM siempre activa, el polling actual **funciona sin cambios**.
- Migrar a webhook es opcional y recomendable a futuro:
  `api.telegram.org/bot<TOKEN>/setWebhook?url=https://.../webhook` + endpoint
  en `app/server.py`; reutilizar la misma máquina de estados
  (`app/bot/order_flow.py`), solo cambia el transporte.

**Decisión al implementar:** polling para el primer deploy (cero cambios),
webhook como mejora posterior si el polling da problemas de estabilidad.

---

## 6. TODO — Compartir con el cliente (PRIORIDAD ALTA, FASE FINAL)

- Enviar al cliente:
  1. URL HTTPS del KDS + credenciales de auth (`KDS_USER`/`KDS_PASS`).
  2. Link del bot de Telegram (nombre de usuario del bot) para probar pedidos.
  3. Nota breve: el bot toma pedidos coloquiales; el KDS muestra pedidos en
     vivo y permite avanzar estados.
- Verificar en conjunto: pedido de prueba → aparece en KDS → cambiar estado →
  cliente recibe notificación en Telegram.

**Aceptación:** el cliente puede (a) pedir por Telegram, (b) ver el pedido en
el KDS en vivo, (c) avanzarlo sin ayuda técnica.

---

## 7. Futuro: migración a WhatsApp (ver README "Roadmap: migración a WhatsApp")

- Decisión confirmada: **Meta Cloud API directa** (no Twilio ni BSP).
- Cambio relevante para deploy: WhatsApp exige webhook HTTPS público (la VM +
  Cloudflare Tunnel ya lo proveen); reemplaza la necesidad de polling.
- Recordar el cambio de precios del 1-oct-2026 (los mensajes de servicio pasan
  a cobrarse).

---

## Notas de diseño para el deploy

- La VM ARM es la única vía free que conserva SQLite + ChromaDB + WebSocket sin
  refactor; NO rediseñar a serverless para un POC.
- Mantener la convención de secretos: booleans en logs, `config.redact()`, `.env`
  nunca en el repo.
- Backups mínimos antes de mostrar al cliente: copiar `data/menu.db` y
  `data/menu.md` (el índice Chroma se reconstruye con el botón del dashboard).
