# Las 5 conversaciones · GastroBott

## 1. Información
**Objetivo:** responder con datos reales del negocio (contexto), sin inventar nada.

- Usuario: "¿Cuánto cuesta la pizza pepperoni?"
- Esperado: el bot responde $36.000, tomado del menú (`negocio.json`), y
  ofrece continuar con un pedido.
- Usuario: "¿Hacen domicilio a Suba?"
- Esperado: el bot indica que Suba no está en las zonas cubiertas
  (Centro, Norte, Chapinero) y no inventa cobertura.

## 2. Reserva/pedido completo
**Objetivo:** selección → confirmación → resultado verificable vía API.

- Usuario: "Quiero un domicilio. Una pizza margarita y una gaseosa."
- Bot pide dirección y confirma resumen con total (incluye costo de domicilio).
- Usuario responde **CONFIRMAR**.
- Esperado: `POST /pedidos` devuelve un código `GB-XXXXXX`; el bot lo comunica
  y el usuario puede consultarlo con `GET /pedidos/{codigo}`.

## 3. Datos incompletos o corregidos
**Objetivo:** aclaración y actualización del estado.

- Usuario: "Quiero pedir para recoger." (sin productos)
- Bot pregunta qué productos desea.
- Usuario: "Una hamburguesa doble carne." luego "Mejor cámbiala por la clásica."
- Esperado: el resumen final refleja solo la hamburguesa clásica; el estado
  anterior (doble carne) queda invalidado antes de pedir confirmación.

## 4. Interrupción y retorno
**Objetivo:** responder una duda intermedia sin perder el pedido en curso.

- Usuario: "Quiero una pizza margarita para recoger." → "Antes, ¿tienen bebidas sin azúcar?"
- Bot responde la duda usando el menú (limonada natural, sin conservar
  precisión sobre azúcar si no está en los datos: debe decir que no tiene
  esa información confirmada).
- Usuario: "Listo, sigamos con mi pedido."
- Esperado: el bot retoma el pedido de la pizza margarita sin pedir de nuevo
  el tipo de entrega.

## 5. Límites y recuperación
**Objetivo:** fuera de dominio y falla de una consulta.

- Usuario: "Explícame cómo hacer una pizza casera."
- Esperado: el bot indica que solo puede ayudar con el menú y pedidos de
  GastroBott.
- Simular una falla de la API de disponibilidad (ej. servidor caído).
- Esperado: el bot comunica que no pudo verificar el estado del servicio y
  propone reintentar, sin decir que no hay disponibilidad ni inventar éxito.
