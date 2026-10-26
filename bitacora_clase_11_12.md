---
tipo: bitacora-clase
curso: Electiva 2
periodo: EAM-2026II
equipo: Noreña_Tapiero
corte: Tercer corte
semana: [Semana]
clase: 11-12
fecha: 2026-10-26
estado: en-progreso
tags:
  - chatbots
  - bitacora
  - telegram
---

# Bitácora — Clase 11 y 12

## 1. Datos de la sesión

| Campo | Registro |
| -------- | -------- |
| Tema | Telegram como canal del chatbot |
| Objetivo | Que una persona use el bot de GastroBott desde Telegram, con comandos iniciales y consultas reales del negocio (menú, disponibilidad y pedidos) |
| Proyecto | Gastrobot |
| Repositorio | [Electiva-2 en GitHub](https://github.com/paulnorena/Electiva-2.git) |
| Ubicación del proyecto | La carpeta completa del proyecto, incluida esta bitácora, ya se encuentra en el repositorio de GitHub indicado. |
| Inicio | 10:00 |
| Cierre | 11:00 |

## 2. Participación y responsabilidades

| Integrante | Asistió | Rol de la clase | Responsabilidad asumida | Aporte verificable |
| ---------- | :-----: | --------------- | ----------------------- | ------------------ |
| Jean Paul Noreña | Sí | Realizó todo el trabajo de la clase | Realizó todas las actividades de la sesión | `bot_telegram.py` |
| Jean Pool Tapiero | No | No participó | Ninguna | — |

## 3. Reto aplicado al proyecto

### Funcionalidad trabajada

| Campo | Registro |
| ----- | -------- |
| Nombre del chatbot | Gastrobot |
| Dominio | Poolsfood |
| Problema | Los clientes se quejan de que no pueden ordenar su pedido de manera eficiente |
| Usuario objetivo | Clientes |
| Objetivo | Que los clientes consulten el restaurante desde Telegram, sin depender de la terminal |
| Capacidades (3-5) | Mostrar el menú, informar la disponibilidad, consultar pedidos, mantener el contexto de la conversación por chat, reiniciar la conversación con `/reset` |
| Sí puede / No puede | Sí puede responder `/start`, `/help` y `/reset`, consultar menú, disponibilidad y pedidos, y completar una consulta en otro mensaje del mismo chat. No ejecuta crear ni cancelar pedidos: informa que la operación quedó sin ejecutar y no acepta un «sí» como confirmación. |
| Patrón adaptado | INFORMAR-CONVERSAR-RECORDAR-CONSULTAR DISPONIBILIDAD-CONSULTAR (canal Telegram) |
| Proceso (pasos) | Telegram recibe el mensaje → `recibir_texto()` → `procesar_turno()` (Groq interpreta, la FastAPI ejecuta) → `formatear_resultado()` → `reply_text()` |

### Criterios de aceptación

- [ ] `bot_telegram.py` está en la carpeta del proyecto, junto a `chatbot_memoria.py` y `consulta_llm.py`.
- [x] `python-telegram-bot>=22,<23`
- [ ] El bot fue creado con @BotFather y responde `/start`, `/help` y `/reset`.
- [ ] Una consulta de menú desde Telegram coincide con los datos actuales de la FastAPI.
- [ ] Una consulta incompleta se completa en otro mensaje usando el historial del chat.
- [ ] Después de `/reset`, el contexto anterior ya no completa la solicitud.
- [ ] Un comando inexistente orienta hacia `/start`, `/help` y `/reset`; una foto pide un mensaje de texto.
- [ ] Con la FastAPI apagada, el bot informa el fallo de conexión sin inventar resultados.
- [ ] El adaptador nunca llama a `ejecutar(..., confirmar=True)`.
- [ ] La entrega no contiene el token de Telegram ni la clave de Groq.

### Archivos o componentes modificados

- `bot_telegram.py`: archivo nuevo. Adaptado a GastroBott (`BIENVENIDA`, `AYUDA`, `formatear_resultado()` para menú y pedidos) y conectado a `consulta_llm.preparar()` para reutilizar `groq_key.txt` y la elección automática del modelo.
- `chatbot_memoria.py` y `consulta_llm.py`: se reutilizan `nuevo_historial()`, `procesar_turno()`, `preparar()`, `resumen_plan()` y `detalle_http()`; no se afirma que hayan sido probados en vivo durante esta revisión.
- `main.py`: se corrigió la validación de días y horario usando hora local de Colombia, el mínimo de domicilio se calcula sobre el subtotal de productos y se rechazan pedidos vacíos o sin nombre.
- `prompt_sistema.md` y el prompt exportado en `GastroBot Chatflow.json`: se alinearon con el menú de `negocio.json`.
- `requirements.txt`, `README.md` y `.gitignore`: añadidos para facilitar instalación, ejecución y protección de credenciales.
- Dependencias del proyecto: se agregó `python-telegram-bot>=22,<23`.

## 4. Decisiones técnicas

| Decisión | Razón | Alternativa descartada |
| -------- | ----- | ---------------------- |
| Telegram solo atiende consultas en esta versión | La confirmación de pedidos desde Telegram se desarrolla en la siguiente sesión; evita registrar o cancelar por una mala interpretación | Aceptar «sí» como confirmación |
| Reutilizar `procesar_turno()` sin cambiar la lógica del negocio | Telegram es solo un canal nuevo; Groq interpreta y la FastAPI ejecuta igual que en la terminal | Reescribir la lógica dentro del bot |
| Historial en `context.chat_data` | Cada chat conserva su propia conversación y `/reset` solo borra la memoria de ese chat, no los pedidos | Un historial global compartido por todos los usuarios |
| Long polling con `run_polling()` | El computador del bot abre la conexión con Telegram; la FastAPI puede seguir en `127.0.0.1` | Webhook, que exige una URL pública |
| `asyncio.to_thread()` para llamar a `procesar_turno()` | La función es síncrona y no debe bloquear el bucle de eventos del bot | Llamarla directamente dentro de la función `async` |
| Responder solo en chats privados | Evita que el bot reaccione en grupos | Atender cualquier tipo de chat |
| Tras un resultado de confirmación, el historial registra «operación no ejecutada» | Evita que el modelo crea que hay un pedido pendiente de confirmar | Dejar el mensaje «¿Confirmas?» en el historial |

## 5. Problemas y soluciones

| Problema encontrado | Causa identificada | Solución aplicada | ¿Cómo se verificó? |
| ------------------- | ------------------ | ----------------- | ------------------ |
| El prompt tenía platos distintos al menú de la API | `prompt_sistema.md` no coincidía con `negocio.json` | Se alinearon nombres, IDs y precios con `negocio.json` | Comparación estática de archivos; falta probar respuestas en vivo de Groq |
| La disponibilidad ignoraba los días configurados | La función comparaba solo las horas y no usaba `horario.dias` | Se agregó validación de día y zona horaria `America/Bogota` | Compilación de Python; falta probar `/disponibilidad` con el servidor activo |
| El mínimo de domicilio incluía el costo de envío | Se comparaba el total con el umbral | Ahora se valida el subtotal de productos antes del envío | Compilación de Python; falta probar los casos límite en la API |
| No había lista de dependencias ni guía de ejecución | Faltaban `requirements.txt` y `README.md` | Se agregaron ambos archivos y un `.gitignore` para claves locales | Revisión de los archivos generados |

## 6. Evidencias

| Tipo | Descripción | Enlace o ruta |
| ---- | ----------- | ------------- |
| Enlace | Nombre público del bot | [@nombre_del_bot] |
| Captura | `/start` y `/help` | [pendiente de agregar] |
| Captura | Consulta del menú en Telegram contrastada con la FastAPI (`/docs`) | [pendiente de agregar] |
| Captura | Consulta continuada en otro mensaje del mismo chat | [pendiente de agregar] |
| Captura | `/reset` y luego solo el dato que faltaba | [pendiente de agregar] |
| Captura | Comando inexistente y foto | [pendiente de agregar] |
| Captura | FastAPI apagada: mensaje de fallo de conexión | [pendiente de agregar] |
| Código | `recibir_texto()` recibe la pregunta, llama a `procesar_turno()` y responde con `reply_text()` | `bot_telegram.py` |
| Repositorio | Carpeta del proyecto y bitácora de las clases 11 y 12 | [https://github.com/paulnorena/Electiva-2.git](https://github.com/paulnorena/Electiva-2.git) |

## 7. Uso de inteligencia artificial

> [!important] Registrar la IA no reemplaza la explicación técnica. El equipo debe verificar, adaptar y comprender cualquier resultado utilizado.

| Herramienta | Objetivo o pregunta | Qué se utilizó | Cómo se verificó | Qué se modificó |
|---|---|---|---|---|
| ChatGPT | Revisar el ZIP, detectar diferencias entre menú, API y documentación, y proponer correcciones | Cambios en `main.py`, `prompt_sistema.md`, `GastroBot Chatflow.json`, `requirements.txt`, `README.md` y `.gitignore` | Compilación sintáctica y comprobaciones locales; las pruebas en Telegram/Groq aún deben ejecutarse | Revisar los cambios, instalar dependencias y completar las evidencias reales antes de entregar |

## 8. Defensa técnica y retroalimentación

| Campo | Registro |
|---|---|
| Integrante que defendió | [Nombre] |
| Pregunta recibida | [Pregunta] |
| Respuesta resumida | [Respuesta] |
| Retroalimentación docente | [Observación] |
| Mejora acordada | [Acción concreta] |

## 9. Aprendizajes

- **Concepto comprendido:** Telegram solo cambia el canal. `recibir_texto()` recibe el mensaje, `procesar_turno()` (de `chatbot_memoria.py`) hace que Groq interprete y la FastAPI ejecute, y `reply_text()` entrega la respuesta. El historial vive en `context.chat_data`, por eso `/reset` no borra los pedidos.
- **Algo que aún genera duda:** [Duda pendiente]
- **Qué haríamos diferente:** [Reflexión del equipo]

## 10. Revisión antes de entregar

- [ ] Todos los integrantes registraron un aporte verificable.
- [ ] Los enlaces y rutas de evidencia funcionan.
- [ ] Los criterios de aceptación están actualizados.
- [ ] El uso de IA fue declarado y verificado.
- [ ] El equipo puede explicar las decisiones registradas.
- [ ] El token de Telegram y la clave de Groq no aparecen en el repositorio ni en las capturas.
