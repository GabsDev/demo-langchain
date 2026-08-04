# Propuesta Comercial — Bot de Pedidos con IA para Restaurantes (Costa Rica)

> **Su cliente pide por chat como le habla a un humano. Usted ve el pedido en tiempo real en la cocina.**
> Sin apps que instalar, sin comisiones por plataforma, sin fricción. Pagos con SINPE Móvil.

---

## 1. El problema

- El cliente tiene que llamar por teléfono (líneas ocupadas, se pierden pedidos, se entiende mal el nombre del plato).
- Las apps de delivery cobran comisiones del 20–30% por cada pedido.
- El personal anota pedidos a mano y el equipo en cocina pierde tiempo descifrando la letra.
- Actualizar el menú (precios, platos del día, agotados) requiere reimprimir cartas y avisar por redes.

## 2. La solución

Un **bot de mensajería con inteligencia artificial** que toma pedidos en lenguaje natural las 24 horas, y un **panel web en tiempo real (KDS)** para la cocina y la caja.

El cliente escribe como le habla a un mesero: *"un casado de pollo y un fresco de mora"*, *"agregame un chifrijo"*, *"cambie la empanada por un tamal"*. La IA entiende, arma el pedido, lo confirma con el total en colones y lo envía directo a la cocina. Al entregar, el cliente puede pagar con **SINPE Móvil**.

---

## 3. Beneficios clave

| Beneficio | Detalle |
|---|---|
| **Sin comisiones** | El pedido llega directo del cliente al restaurante. Usted conserva el 100% de la venta. |
| **Pagos con SINPE Móvil** | El cliente paga en el momento de la entrega con SINPE, sin efectivo ni tarjeta. |
| **Atención 24/7** | El bot toma pedidos incluso fuera del horario de atención. |
| **Menos errores** | El pedido llega escrito y legible a la cocina, con precios verificados contra el menú. |
| **Menos carga telefónica** | El personal se enfoca en atender clientes presentes en lugar de contestar el teléfono. |
| **Menú siempre al día** | Cambios de precios y platos se actualizan en segundos, sin reimprimir. |
| **Costo operativo mínimo** | Menos de ₡500 al mes en servicios de IA para un restaurante pequeño. |
| **Sin infraestructura propia** | No necesita servidores ni personal técnico; el sistema ya viene montado. |

---

## 4. Funcionalidades

### 4.1 Para el cliente — pedidos por chat

- **Pedido en lenguaje natural**: el cliente escribe "un casado de pescado y una horchata" y la IA lo convierte en pedido contra el menú real.
- **Entendimiento de intenciones**: la IA distingue si quiere pedir, preguntar por el menú o solo saludar.
- **Consultas inteligentes al menú (IA con RAG)**: el cliente pregunta *"¿qué tienen sin gluten?"*, *"¿cuánto cuesta el chifrijo?"* y recibe respuesta con datos reales del menú.
- **Envío de la carta en PDF**: el bot comparte el menú completo en un clic.
- **Saludo contextual**: responde buenos días/tardes/noches según la hora y continúa la conversación.
- **Modificación coloquial del pedido**: *"agregame una coca"*, *"sáqueme el gallo pinto"*, *"cambie la milanesa por el asado"* — actualiza el pedido en curso sin empezar de cero.
- **Delivery o retiro local**: el cliente elige si se lo llevan o lo recoge.
- **Datos de entrega**: para delivery, solicita teléfono de contacto y la dirección o señas del lugar.
- **Pago con SINPE Móvil**: al confirmar, el cliente puede indicar que pagará con SINPE (o transferencia) al recibir el pedido.
- **Confirmación con total**: muestra el resumen con precios en colones y botones de confirmar/cancelar antes de enviar a cocina.
- **Sin fricción**: no requiere instalar apps ni crear cuentas.

### 4.2 Para el restaurante — panel de cocina (KDS)

- **Pedidos en tiempo real**: cada pedido entra al instante en el panel con alerta sonora para el primer pedido nuevo.
- **Aviso visual de pedidos nuevos**: la tarjeta del pedido pendiente parpadea con distintivo "¡NUEVO!" hasta que pasa a preparación.
- **Gestión de estados en un clic**: Pendiente → En preparación → Listo → Entregado.
- **Método de pago visible**: el panel muestra si el cliente pagará con SINPE, efectivo o transferencia.
- **Varias pantallas sincronizadas**: cocina y caja ven el mismo panel en vivo.
- **Historial completo con búsqueda**: consulta pedidos por fecha, texto o estado; limpieza por día.
- **Administración del menú desde el panel**: alta, edición y baja de platos sin tocar código.
- **Carga del menú por PDF**: suba la carta existente y la IA extrae los ítems para publicarlos (con validación antes de activar).
- **Reindexación inteligente**: un botón actualiza las respuestas de la IA cuando cambia el menú.

### 4.3 Técnico / confiabilidad

- **Un solo proceso**: servidor web + bot integrados, fácil de poner en marcha.
- **Persistencia local**: pedidos e historial guardados en base de datos propia.
- **Respuesta ante fallas**: si el servicio de IA no está disponible, el bot continúa tomando pedidos básicos con palabras clave.
- **Seguridad**: las claves de API nunca se exponen en los registros.
- **Multi-idioma para el cliente**: español coloquial y natural.

---

## 5. Cómo funciona (flujo típico)

```
Cliente en Telegram        IA (GPT-4o-mini + menú RAG)        Cocina (panel KDS)
──────────────────         ─────────────────────────          ─────────────────
"buenas, ¿qué tienen?"  →  Respuesta con el menú real
"un casado y un fresco" →  Pedido parseado contra el menú
"agregame un chifrijo"  →  Pedido actualizado
"pago con SINPE"        →  Método de pago registrado
[Confirmar] ₡6,800      →  Pedido enviado                  →  ¡NUEVO! tarjeta parpadeante
                                                           →  [En preparación] [Listo] [Entregado]
                                                           →  Pago: SINPE Móvil
```

---

## 6. Estructura de precios propuesta

### 6.1 Implementación única (setup)

| Concepto | Precio sugerido |
|---|---|
| **Instalación + configuración** (VM en la nube, bot, panel KDS, menú del restaurante, capacitación al equipo) | **₡99,000** (~US$190) |
| **Demo en vivo previa** | Gratis |

> Rango de mercado LATAM 2026 para este setup: US$140–1,000+ (SuperPyme Chile desde ~US$140;
> desarrollo propio en México US$2,000–4,400). El precio de introducción entra por debajo del
> mercado para los primeros clientes; clientes que quieran **el código completo a medida**
> (desarrollo propio, no suscripción) se cotizan por separado desde **US$1,000+**, que es el
> modelo de venta que se ve en el mercado para bots custom.

### 6.2 Suscripción mensual — precios de introducción (primeros 6 meses)

| Plan | Ideal para | Incluye | Precio intro (6 meses) | Precio regular |
|---|---|---|---|---|
| **Básico** | Restaurantes pequeños | Bot de pedidos, panel KDS, menú manual | **₡19,900/mes** (~US$40) | ₡29,900/mes (~US$60) |
| **Pro** | Restaurantes medianos | Todo lo del Básico + consultas IA al menú (RAG), carga de menú por PDF, historial y búsqueda | **₡35,000/mes** (~US$70) | ₡45,000/mes (~US$90) |
| **Premium** | Cadenas y alta demanda | Todo lo del Pro + personalización, múltiples paneles, soporte prioritario y ajustes a medida | **₡59,000/mes** (~US$118) | ₡75,000/mes (~US$150) |

> Costos de IA incluidos en el plan (menos de ₡500/mes en consumo para un restaurante pequeño).
> Precios sujetos a cambios según tipo de cambio. Después de los primeros 6 meses aplica el
> precio regular.

### 6.3 De dónde salen estos números (referencias de mercado 2026)

Los precios de introducción se calibraron contra ofertas reales de LATAM
(fuentes consultadas: agosto 2026):

- **SaaS para restaurantes en México** (Kosmo): planes de MXN $4,497 a $24,997/mes (~US$250–1,400).
  → https://kosmo.com.mx/blog/bots-restaurante-whatsapp-mexico-reservaciones-pedidos
- **Bot WhatsApp para pymes en Chile** (SuperPyme): desde CLP $14,990/mes (~US$16); implementación
  avanzada desde CLP $129,990 (~US$140); plan "a medida" desde CLP $149,990/mes (~US$160).
  → https://superpyme.cl/precios-bot-whatsapp
- **Plataformas LATAM** (AsisteClick, Whaticket, B2Chat): US$16–300/mes según volumen y agentes.
  → https://asisteclick.com/blog/chatbot-whatsapp-precio-empresas/
- **Colombia**: chatbots de WhatsApp ~US$60–65/mes para pymes.
  → https://waichat.co/blog/cuanto-cuesta-chatbot-whatsapp-colombia
- **Desarrollo propio en México**: setup US$2,000–4,400 + mantenimiento US$250–750/mes.
  → https://kosmo.com.mx/blog/bots-restaurante-whatsapp-mexico-reservaciones-pedidos
- **Rango general SMB** (Quickchat, Botifyo, AIFlow): US$9–150/mes.
  → https://quickchat.ai/post/how-much-does-chatbot-cost · https://botifyo.com/blog/whatsapp-chatbot-cost-comparison

> Verificar precios antes de cada cotización: los planes de los proveedores cambian. Estas
> fuentes son públicas y estables; las tarifas de Meta (si se integra WhatsApp) se consultan en
> https://developers.facebook.com/docs/whatsapp/pricing.

Estrategia: el plan Básico de introducción (~US$40/mes) queda **por debajo** del promedio del
mercado para ganar los primeros clientes; el setup de ₡99,000 captura el valor de la
implementación; y el desarrollo a medida desde US$1,000+ cubre a quien quiere quedarse con el
sistema completo.

### 6.4 Diferencia entre planes: qué compra cada uno

Técnicamente hay **un solo sistema con interruptores** (feature flags) por cliente: los planes
no son bots distintos, son configuraciones distintas del mismo bot. Esto permite actualizar de
plan sin migrar de sistema.

| Funcionalidad | Básico | Pro | Premium |
|---|---|---|---|
| Pedidos por opciones numeradas (1/2/3) | ✅ | ✅ | ✅ |
| Pedidos en lenguaje natural con IA ("quiero un casado y un fresco") | ❌ | ✅ | ✅ |
| Consultas IA al menú con RAG ("¿qué tienen sin gluten?") | ❌ | ✅ | ✅ |
| Carga de menú por PDF con limpieza IA | ❌ | ✅ | ✅ |
| Historial completo con búsqueda | ❌ | ✅ | ✅ |
| Personalización del panel (logo, colores) | ❌ | ❌ | ✅ |
| Pantallas simultáneas | 1 | 1 | Hasta 3 |
| Sucursales | 1 | 1 | Hasta 3 |
| Ajustes menores incluidos (textos, botones, platos) | — | — | Hasta 2/mes |
| Horas de desarrollo personalizado incluidas | — | — | Hasta 2 h/mes |
| Soporte | Estándar | Estándar | Prioritario (< 24 h) |
| Costo de IA (OpenAI) | $0 | ~US$1–3/mes | Incluido |

**Básico vs Pro — la diferencia real:** el Básico es un bot de pedidos sólido por opciones, sin
costo de IA; el Pro suma el entendimiento de lenguaje natural y las consultas al menú. El Básico
NO es un bot incompleto: es la puerta de entrada; el Pro es donde se nota la inteligencia.

**Límite del Premium:** todo lo que es *configuración* (logo, textos, platos, pantallas) está
incluido; todo lo que es *funcionalidad nueva* (integración con POS, pagos, otro canal) se
cotiza aparte. El exceso de horas personalizadas se factura por hora (~₡15,000–20,000/h) o como
mini-proyecto.

---

## 7. Plan de crecimiento (roadmap)

Funcionalidades planificadas para las siguientes versiones:

- **SINPE Móvil integrado**: el cliente recibe un PIN de solicitud de cobro o un código QR para pagar en el momento de la confirmación.
- **Notificaciones de estado al cliente** ("su pedido está en preparación", "listo para recoger").
- **Multi-sucursal**: un mismo sistema administrando varios locales.
- **Integración con WhatsApp Business**.
- **Ventas y métricas**: reporte mensual de pedidos, platos más vendidos e ingresos.
- **Despliegue en la nube** con dominio propio del restaurante.

---

## 8. Preguntas frecuentes

**¿Qué necesita el cliente para pedir?**
Solo Telegram (gratis) o el canal de mensajería habilitado. Sin apps ni registros.

**¿Cómo se cobra?**
Al entregar, el cliente paga con SINPE Móvil (transferencia a la cuenta del restaurante), efectivo o tarjeta. El panel muestra el método de pago elegido.

**¿Qué necesita el restaurante?**
Una computadora o tablet con navegador para el panel de cocina, y el bot configurado.

**¿Es difícil actualizar el menú?**
No. Se edita desde el panel, se sube un PDF o se actualiza con un clic; el bot y la IA usan automáticamente la versión vigente.

**¿Qué pasa si no hay internet o falla la IA?**
El panel sigue funcionando con los pedidos ya recibidos, y el bot mantiene un modo de respaldo por palabras clave.

**¿Puedo probarlo antes de contratar?**
Sí, ofrecemos una demostración en vivo con un menú de ejemplo tico (casados, chifrijos, gallos).

**¿Por qué mensualidad y no un pago único de $1,000+ como otros bots?**
Porque son modelos distintos. La mensualidad es un servicio (hosting + IA + soporte + mejoras
incluidas), con barrera de entrada baja. El pago único de $1,000+ corresponde a desarrollo a
medida con entrega del código completo; eso se cotiza por separado cuando el cliente quiere
quedarse con el sistema. Ambos modelos se ofrecen; la mensualidad es la vía más accesible para
un restaurante pequeño.

---

## 9. Contacto

[Su nombre / empresa]
[Teléfono / WhatsApp — +506 ...]
[Correo]
[Sitio web]
