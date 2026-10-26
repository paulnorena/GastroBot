"""Clase 07: historial de conversación sobre la lógica de la clase 06 (GastroBott).

Coloca este archivo junto a consulta_llm.py. Más adelante Gradio podrá usar
nuevo_historial() y procesar_turno() sin copiar la lógica del negocio.

Antes de probar, enciende la FastAPI en otra terminal:
    uvicorn main:app --reload --port 8011
"""

import json
from datetime import date
from urllib.error import HTTPError, URLError

from consulta_llm import (
    GROQ_URL,
    detalle_http,
    ejecutar,
    normalizar_plan,
    peticion_json,
    preparar,
    texto_menu,
)

INSTRUCCIONES = """
Eres el intérprete de solicitudes del restaurante GastroBott. Devuelve
únicamente un objeto JSON con las claves accion, cliente, tipo_entrega,
direccion, items y codigo.
Acciones: menu, disponibilidad, crear, consultar, cancelar, fuera_de_alcance.
tipo_entrega es "domicilio" o "recoger". items es una lista de objetos como
{"id": "P1", "cantidad": 2}; usa solo los id del menú. codigo es el código de
un pedido existente, por ejemplo GB-A1B2C3.
Ten en cuenta los mensajes anteriores para completar un pedido que la
persona haya iniciado en otro turno. Si un dato no aparece en toda la
conversación, déjalo como cadena vacía (lista vacía en items). No inventes
datos ni afirmes que ya se registró un pedido.
"""


def nuevo_historial():
    hoy = date.today().isoformat()
    sistema = INSTRUCCIONES + f"\nFecha actual: {hoy}.\nMenú (id: nombre):\n" + texto_menu()
    return [{"role": "system", "content": sistema}]


def interpretar_turno(pregunta, historial, clave, modelo):
    mensajes = historial + [{"role": "user", "content": pregunta}]
    payload = {"model": modelo, "messages": mensajes, "stream": False}
    respuesta = peticion_json(
        GROQ_URL, "POST", payload, {"Authorization": f"Bearer {clave}"}
    )
    plan = normalizar_plan(json.loads(respuesta["choices"][0]["message"]["content"]))
    return plan, mensajes


def procesar_turno(pregunta, historial, clave, modelo):
    plan, mensajes = interpretar_turno(pregunta, historial, clave, modelo)
    resultado = ejecutar(plan)
    resumen = {"plan": plan, "respuesta": resultado.get("mensaje", resultado.get("datos"))}
    actualizado = mensajes + [
        {"role": "assistant", "content": json.dumps(resumen, ensure_ascii=False)}
    ]
    return resultado, actualizado, plan


def main():
    datos = preparar()
    if datos is None:
        return
    clave, modelo = datos
    historial = nuevo_historial()
    print("Escribe tu solicitud. REINICIAR borra el historial; SALIR termina.")
    while True:
        pregunta = input("\nTú: ").strip()
        if pregunta.casefold() == "salir":
            break
        if pregunta.casefold() == "reiniciar":
            historial = nuevo_historial()
            print("Conversación reiniciada. Queda solo el mensaje system.")
            continue
        if not pregunta:
            continue
        try:
            resultado, actualizado, plan = procesar_turno(
                pregunta, historial, clave, modelo
            )
            historial = actualizado
            print("Plan:", json.dumps(plan, ensure_ascii=False))
            print("Chatbot:", resultado.get("mensaje") or
                  json.dumps(resultado["datos"], ensure_ascii=False, indent=2))
            if resultado["tipo"] == "confirmacion":
                if input("Confirmar (s/n): ").strip().casefold() == "s":
                    final = ejecutar(plan, confirmar=True)
                    historial[-1]["content"] = json.dumps(
                        {"plan": plan, "respuesta": final["datos"]}, ensure_ascii=False
                    )
                    print("FastAPI:", json.dumps(final["datos"], ensure_ascii=False, indent=2))
                else:
                    historial[-1]["content"] = json.dumps(
                        {"plan": plan, "respuesta": "La operación no fue confirmada."},
                        ensure_ascii=False,
                    )
            print(f"Mensajes en el historial: {len(historial)}")
        except HTTPError as error:
            print(f"Error HTTP {error.code}. {detalle_http(error)}".strip())
        except (URLError, TimeoutError):
            print("No pude conectar con Groq o con la FastAPI.")
        except (ValueError, KeyError, IndexError, TypeError):
            print("No pude interpretar la respuesta. Revisa el JSON recibido.")


if __name__ == "__main__":
    main()
