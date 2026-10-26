"""Lógica del chatbot GastroBott: Groq interpreta y la FastAPI ejecuta.

Se usa desde la terminal. Más adelante Gradio podrá llamar interpretar()
y ejecutar() sin cambiar la lógica del negocio.

Antes de probar, enciende la FastAPI en otra terminal:
    uvicorn main:app --reload --port 8011
"""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_BASE = os.getenv("CHATBOT_API_URL", "http://127.0.0.1:8011").rstrip("/")
RUTAS = {
    "menu": "/menu",
    "disponibilidad": "/disponibilidad",
    "pedidos": "/pedidos",
}
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELOS_URL = "https://api.groq.com/openai/v1/models"
MODELOS_PREFERIDOS = (
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3-32b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
)
NO_SON_DE_CHAT = ("whisper", "guard", "tts", "orpheus", "playai", "compound", "safeguard")
ACCIONES = {"menu", "disponibilidad", "crear", "consultar", "cancelar", "fuera_de_alcance"}
CAMPOS = ("accion", "cliente", "tipo_entrega", "direccion", "items", "codigo")
TIPOS_ENTREGA = ("domicilio", "recoger")
REQUERIDOS = {
    "crear": ("cliente", "tipo_entrega", "items"),
    "consultar": ("codigo",),
    "cancelar": ("codigo",),
}
INSTRUCCIONES = """
Identifica qué quiere hacer la persona con el restaurante GastroBott.
Devuelve únicamente un objeto JSON con estas claves:
accion, cliente, tipo_entrega, direccion, items, codigo.
Acciones posibles: menu, disponibilidad, crear, consultar, cancelar,
fuera_de_alcance.
tipo_entrega es "domicilio" o "recoger". items es una lista de objetos
como {"id": "P1", "cantidad": 2}; usa solo los id del menú. codigo es el
código de un pedido existente, por ejemplo GB-A1B2C3.
Si un dato no aparece en la pregunta, usa una cadena vacía (lista vacía en
items); no lo inventes. No digas que hiciste un pedido: solo identifica la
intención.
"""


def peticion_json(url, metodo="GET", datos=None, headers=None):
    cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8") if datos is not None else None
    encabezados = {"User-Agent": "Mozilla/5.0 (GastroBott)"}
    if cuerpo is not None:
        encabezados["Content-Type"] = "application/json"
    encabezados.update(headers or {})
    solicitud = Request(url, data=cuerpo, headers=encabezados, method=metodo)
    with urlopen(solicitud, timeout=30) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def texto_menu():
    """Pide el menú a la FastAPI para que Groq conozca los id de los productos."""
    try:
        datos = peticion_json(API_BASE + RUTAS["menu"])
        return "\n".join(
            f"{p['id']}: {p['nombre']} (${p['precio']})" for p in datos["menu"]
        )
    except (HTTPError, URLError, TimeoutError, KeyError, TypeError, ValueError):
        return ""


def normalizar_plan(plan):
    """Valida la acción y deja todos los campos con el tipo esperado."""
    if not isinstance(plan, dict) or plan.get("accion") not in ACCIONES:
        raise ValueError("Groq no devolvió una acción válida")
    limpio = {
        campo: str(plan.get(campo) or "").strip()
        for campo in CAMPOS
        if campo != "items"
    }
    lista = plan.get("items")
    items = []
    if isinstance(lista, list):
        for item in lista:
            if isinstance(item, dict) and item.get("id"):
                try:
                    cantidad = int(item.get("cantidad") or 1)
                except (TypeError, ValueError):
                    cantidad = 0
                items.append({"id": str(item["id"]).strip().upper(), "cantidad": cantidad})
    limpio["items"] = items
    return limpio


def interpretar(pregunta, clave, modelo):
    instrucciones = INSTRUCCIONES + "\nMenú (id: nombre):\n" + texto_menu()
    payload = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": instrucciones},
            {"role": "user", "content": pregunta},
        ],
        "stream": False,
    }
    respuesta = peticion_json(
        GROQ_URL, "POST", payload,
        {"Authorization": f"Bearer {clave}"},
    )
    texto = respuesta["choices"][0]["message"]["content"]
    return normalizar_plan(json.loads(texto))


def datos_faltantes(plan):
    faltan = [campo for campo in REQUERIDOS.get(plan["accion"], ()) if not plan.get(campo)]
    if plan["accion"] == "crear":
        if plan["tipo_entrega"] and plan["tipo_entrega"] not in TIPOS_ENTREGA:
            faltan.append("tipo_entrega (domicilio o recoger)")
        elif plan["tipo_entrega"] == "domicilio" and not plan["direccion"]:
            faltan.append("direccion")
    return faltan


def resumen_plan(plan):
    if plan["accion"] == "crear":
        productos = ", ".join(f"{i['cantidad']}x {i['id']}" for i in plan["items"])
        texto = f"cliente={plan['cliente']}, entrega={plan['tipo_entrega']}, productos={productos}"
        if plan["tipo_entrega"] == "domicilio":
            texto += f", direccion={plan['direccion']}"
        return texto
    return f"codigo={plan['codigo']}"


def ejecutar(plan, confirmar=False, api_base=API_BASE):
    accion = plan["accion"]
    if accion not in ACCIONES:
        raise ValueError("Acción no permitida")
    if accion == "fuera_de_alcance":
        return {
            "tipo": "mensaje",
            "mensaje": "Puedo ayudar con el menú, la disponibilidad y los pedidos.",
        }

    faltan = datos_faltantes(plan)
    if faltan:
        return {"tipo": "faltan_datos", "mensaje": "Necesito: " + ", ".join(faltan), "plan": plan}

    if accion in {"crear", "cancelar"} and not confirmar:
        verbo = "registrar el pedido" if accion == "crear" else "cancelar el pedido"
        return {
            "tipo": "confirmacion",
            "mensaje": f"Voy a {verbo}: {resumen_plan(plan)}. ¿Confirmas?",
            "plan": plan,
        }

    base = api_base.rstrip("/")
    pedidos = RUTAS["pedidos"]
    if accion == "menu":
        datos = peticion_json(base + RUTAS["menu"])
    elif accion == "disponibilidad":
        datos = peticion_json(base + RUTAS["disponibilidad"])
    elif accion == "crear":
        cuerpo = {
            "cliente": plan["cliente"],
            "tipo_entrega": plan["tipo_entrega"],
            "direccion": plan["direccion"] or None,
            "items": plan["items"],
            "confirmado": True,
        }
        datos = peticion_json(base + pedidos, "POST", cuerpo)
    elif accion == "consultar":
        datos = peticion_json(base + pedidos + "/" + quote(plan["codigo"], safe=""))
    else:
        datos = peticion_json(base + pedidos + "/" + quote(plan["codigo"], safe=""), "DELETE")
    return {"tipo": "resultado", "accion": accion, "datos": datos}


def detalle_http(error):
    """Devuelve el mensaje de error que envía FastAPI o Groq al rechazar una petición."""
    try:
        texto = error.read().decode("utf-8", errors="replace")
    except AttributeError:
        return ""
    try:
        datos = json.loads(texto)
        if isinstance(datos, dict):
            if "detail" in datos:
                return str(datos["detail"])
            if isinstance(datos.get("error"), dict):
                return str(datos["error"].get("message", ""))
    except ValueError:
        pass
    return texto[:300]


def leer_clave():
    """Busca la key en groq_key.txt (misma carpeta), luego en GROQ_API_KEY y al final la pide."""
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "groq_key.txt")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8-sig") as archivo:
            clave = archivo.read().strip()
        if clave:
            return clave
    clave = os.getenv("GROQ_API_KEY", "").strip()
    return clave or input("API key de Groq (pégala y presiona Enter): ").strip()


def elegir_modelo(clave):
    """Pregunta a Groq qué modelos tiene habilitados esta key y elige uno de chat."""
    datos = peticion_json(GROQ_MODELOS_URL, headers={"Authorization": f"Bearer {clave}"})
    ids = [m["id"] for m in datos.get("data", []) if m.get("active", True)]
    print("Modelos disponibles con tu key:", ", ".join(ids) or "ninguno")
    for modelo in MODELOS_PREFERIDOS:
        if modelo in ids:
            return modelo
    de_chat = [i for i in ids if not any(x in i for x in NO_SON_DE_CHAT)]
    if de_chat:
        return de_chat[0]
    raise ValueError("Tu key no tiene modelos de chat habilitados")


def preparar():
    """Devuelve (clave, modelo) listos para usar, o None si algo falla."""
    clave = leer_clave()
    if not clave:
        print("Necesito la API key de Groq.")
        return None
    try:
        modelo = elegir_modelo(clave)
    except HTTPError as error:
        print(f"Groq rechazó la key (HTTP {error.code}). {detalle_http(error)}".strip())
        return None
    except (URLError, TimeoutError):
        print("No pude conectar con Groq. Revisa tu internet.")
        return None
    except (ValueError, KeyError, TypeError) as error:
        print(f"No pude elegir un modelo: {error}")
        return None
    print(f"Modelo elegido: {modelo}")
    return clave, modelo


def main():
    datos = preparar()
    if datos is None:
        return
    clave, modelo = datos
    print("Escribe una solicitud. Para terminar, escribe SALIR.")
    while True:
        pregunta = input("\nTú: ").strip()
        if pregunta.casefold() == "salir":
            break
        if not pregunta:
            continue
        try:
            plan = interpretar(pregunta, clave, modelo)
            print("Plan:", json.dumps(plan, ensure_ascii=False))
            resultado = ejecutar(plan)
            print("Chatbot:", resultado.get("mensaje") or json.dumps(resultado["datos"], ensure_ascii=False, indent=2))
            if resultado["tipo"] == "confirmacion" and input("Confirmar (s/n): ").strip().casefold() == "s":
                resultado = ejecutar(plan, confirmar=True)
                print("FastAPI:", json.dumps(resultado["datos"], ensure_ascii=False, indent=2))
        except HTTPError as error:
            print(f"Error HTTP {error.code}. {detalle_http(error)}".strip())
        except (URLError, TimeoutError):
            print("No pude conectar con Groq o con la FastAPI. Revisa ambos servicios.")
        except (ValueError, KeyError, IndexError, TypeError):
            print("No pude interpretar la respuesta. Revisa el formato JSON y los datos solicitados.")


if __name__ == "__main__":
    main()
