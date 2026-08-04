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

| Plan | Ideal para | Incluye | Precio sugerido |
|---|---|---|---|
| **Básico** | Restaurantes pequeños | Bot de pedidos, panel KDS, menú manual | ₡25,000/mes (~$50) |
| **Pro** | Restaurantes medianos | Todo lo del Básico + consultas IA al menú (RAG), carga de menú por PDF, historial y búsqueda | ₡40,000/mes (~$80) |
| **Premium** | Cadenas y alta demanda | Todo lo del Pro + personalización, múltiples paneles, soporte prioritario y ajustes a medida | ₡65,000/mes (~$130) |

> Costos de IA incluidos en el plan (menos de ₡500/mes en consumo para un restaurante pequeño). Instalación inicial única: a convenir. Precios sujetos a cambios según tipo de cambio.

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

---

## 9. Contacto

[Su nombre / empresa]
[Teléfono / WhatsApp — +506 ...]
[Correo]
[Sitio web]
