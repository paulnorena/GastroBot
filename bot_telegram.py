"""Canal de Telegram de GastroBott. Colocar junto a chatbot_memoria.py y consulta_llm.py."""

import asyncio
import json
import logging
import os
from getpass import getpass
from urllib.error import HTTPError, URLError

from telegram import Update
from telegram.error import InvalidToken, NetworkError, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from chatbot_memoria import nuevo_historial, procesar_turno
from consulta_llm import detalle_http, preparar, resumen_plan

BIENVENIDA = (
    "Hola, soy GastroBott, el asistente del restaurante. "
    "Puedo mostrarte el menú, informarte la disponibilidad y consultar el estado de un pedido. "
    "Escribe /help para ver ejemplos."
)
AYUDA = (
    "/start: mostrar la bienvenida.\n"
    "/help: ver esta ayuda.\n"
    "/reset: reiniciar esta conversación.\n\n"
    "Prueba:\n"
    "• ¿Qué hay en el menú?\n"
    "• ¿Hay disponibilidad hoy?\n"
    "• Consulta mi pedido GB-A1B2C3\n\n"
    "En esta versión crear o cancelar pedidos queda sin ejecutar: "
    "esas operaciones se habilitarán con confirmación en la siguiente sesión."
)


async def enviar_texto(mensaje, texto):
    for inicio in range(0, len(texto), 4000):
        await mensaje.reply_text(texto[inicio:inicio + 4000])


async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message is not None:
        context.chat_data.setdefault("historial", nuevo_historial())
        await enviar_texto(update.effective_message, BIENVENIDA)


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message is not None:
        await enviar_texto(update.effective_message, AYUDA)


async def reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message is not None:
        context.chat_data["historial"] = nuevo_historial()
        await enviar_texto(
            update.effective_message,
            "Conversación reiniciada. Dime qué deseas consultar. Los pedidos del restaurante se conservan.",
        )


def formatear_datos(datos, nivel=0):
    """Presenta cualquier respuesta de la FastAPI como texto legible."""
    sangria = "  " * nivel
    if isinstance(datos, dict):
        lineas = []
        for clave, valor in datos.items():
            if isinstance(valor, (dict, list)):
                lineas.append(f"{sangria}{clave}:")
                lineas.append(formatear_datos(valor, nivel + 1))
            else:
                lineas.append(f"{sangria}{clave}: {valor}")
        return "\n".join(lineas)
    if isinstance(datos, list):
        return "\n".join(
            f"{sangria}• " + formatear_datos(i, nivel + 1).lstrip() if isinstance(i, (dict, list))
            else f"{sangria}• {i}"
            for i in datos
        )
    return f"{sangria}{datos}"


def formatear_resultado(resultado, plan):
    if resultado.get("tipo") == "confirmacion":
        return (
            "Entendí esta solicitud: " + resumen_plan(plan) + ".\n"
            "Esta versión de Telegram solo atiende consultas. "
            "La operación no se ejecutó y aquí todavía no hay un comando para confirmarla."
        )
    if resultado.get("mensaje"):
        return str(resultado["mensaje"])
    datos = resultado.get("datos")
    if plan["accion"] == "menu" and isinstance(datos, dict) and isinstance(datos.get("menu"), list):
        lineas = ["Menú de GastroBott:"]
        for producto in datos["menu"]:
            lineas.append(f"• {producto['id']}: {producto['nombre']} — ${producto['precio']}")
        return "\n".join(lineas)
    return formatear_datos(datos)


async def recibir_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = update.effective_message
    if mensaje is None or not mensaje.text or not mensaje.text.strip():
        return
    clave = context.bot_data.get("clave_modelo", "")
    modelo = context.bot_data.get("modelo", "")
    if not clave or not modelo:
        await enviar_texto(mensaje, "Falta configurar la API key o el modelo de Groq en el servidor del bot.")
        return
    historial = context.chat_data.get("historial")
    if historial is None:
        historial = nuevo_historial()
    try:
        resultado, actualizado, plan = await asyncio.to_thread(
            procesar_turno, mensaje.text.strip(), historial, clave, modelo
        )
        texto = formatear_resultado(resultado, plan)
    except HTTPError as error:
        detalle = detalle_http(error)
        await enviar_texto(mensaje, "El servicio rechazó la consulta." + (f" {detalle}" if detalle else ""))
        return
    except (URLError, TimeoutError):
        await enviar_texto(mensaje, "No pude completar la conexión con Groq o con la FastAPI. Intenta más tarde.")
        return
    except (ValueError, KeyError, IndexError, TypeError):
        await enviar_texto(mensaje, "La respuesta del servicio no tiene el formato esperado.")
        return
    if resultado.get("tipo") == "confirmacion":
        # El historial no debe dar a entender que el pedido quedó pendiente de confirmar.
        actualizado[-1]["content"] = json.dumps(
            {"plan": plan, "respuesta": "Operación no ejecutada: Telegram solo atiende consultas."},
            ensure_ascii=False,
        )
    context.chat_data["historial"] = actualizado
    await enviar_texto(mensaje, texto)


async def comando_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await enviar_texto(update.effective_message, "No conozco ese comando. Usa /start, /help o /reset.")


async def otro_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await enviar_texto(update.effective_message, "Por ahora recibo consultas escritas. Envíame un mensaje de texto.")


async def informar_error(update, context):
    # Registramos la clase del error sin imprimir credenciales ni URL del bot.
    logging.error("Error del bot: %s", type(context.error).__name__)


def registrar_handlers(aplicacion):
    privado = filters.ChatType.PRIVATE
    aplicacion.add_handler(CommandHandler("start", iniciar, filters=privado))
    aplicacion.add_handler(CommandHandler("help", ayuda, filters=privado))
    aplicacion.add_handler(CommandHandler("reset", reiniciar, filters=privado))
    aplicacion.add_handler(
        MessageHandler(privado & filters.TEXT & ~filters.COMMAND, recibir_texto)
    )
    aplicacion.add_handler(MessageHandler(privado & filters.COMMAND, comando_desconocido))
    aplicacion.add_handler(MessageHandler(privado & ~filters.TEXT, otro_mensaje))
    aplicacion.add_error_handler(informar_error)


def main():
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or getpass("Token de BotFather (oculto): ").strip()
    if not token:
        print("Necesito el token de Telegram para iniciar.")
        return
    # Misma configuración de Groq que consulta_llm.py: groq_key.txt, GROQ_API_KEY o entrada manual.
    datos = preparar()
    clave, modelo = datos if datos else ("", "")
    modelo = os.getenv("GROQ_MODEL", "").strip() or modelo
    try:
        aplicacion = Application.builder().token(token).build()
        aplicacion.bot_data["clave_modelo"] = clave
        aplicacion.bot_data["modelo"] = modelo
        registrar_handlers(aplicacion)
        if not clave or not modelo:
            print("Los comandos funcionarán. Configura la API key de Groq para las consultas.")
        print("Bot en ejecución. Abre su conversación en Telegram. Para detenerlo: Ctrl+C.")
        aplicacion.run_polling(allowed_updates=["message"])
    except InvalidToken:
        print("Token inválido. Comprueba la credencial entregada por BotFather.")
    except NetworkError:
        print("No fue posible iniciar la conexión con Telegram. Revisa Internet e inténtalo otra vez.")
    except TelegramError as error:
        print(f"Telegram no completó el inicio: {type(error).__name__}.")


if __name__ == "__main__":
    main()
