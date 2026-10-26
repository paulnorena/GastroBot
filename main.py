"""
GastroBott · API de pedidos (domicilio / recoger)
Ejecutar con: uvicorn main:app --reload --port 8011
Documentación interactiva en: http://127.0.0.1:8011/docs
"""

import json
import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).parent
NEGOCIO_PATH = BASE_DIR / "negocio.json"
PEDIDOS_PATH = BASE_DIR / "pedidos.json"

app = FastAPI(title="GastroBott API")
ZONA_HORARIA = ZoneInfo("America/Bogota")
DIAS_ES = {
    0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
    4: "viernes", 5: "sabado", 6: "domingo",
}


def cargar_negocio() -> dict:
    with open(NEGOCIO_PATH, encoding="utf-8") as f:
        return json.load(f)


def cargar_pedidos() -> list[dict]:
    if not PEDIDOS_PATH.exists():
        return []
    with open(PEDIDOS_PATH, encoding="utf-8") as f:
        return json.load(f)


def guardar_pedidos(pedidos: list[dict]) -> None:
    with open(PEDIDOS_PATH, "w", encoding="utf-8") as f:
        json.dump(pedidos, f, ensure_ascii=False, indent=2)


class ItemPedido(BaseModel):
    id: str
    cantidad: int = Field(gt=0)


class NuevoPedido(BaseModel):
    cliente: str
    tipo_entrega: Literal["domicilio", "recoger"]
    direccion: str | None = None
    items: list[ItemPedido]
    confirmado: bool


@app.get("/menu")
def obtener_menu():
    negocio = cargar_negocio()
    return {"nombre": negocio["nombre"], "menu": negocio["menu"]}


@app.get("/disponibilidad")
def consultar_disponibilidad():
    negocio = cargar_negocio()
    ahora = datetime.now(ZONA_HORARIA)
    horario = negocio["horario"]
    dias_abiertos = {str(d).strip().casefold() for d in horario.get("dias", [])}
    apertura = time.fromisoformat(horario["apertura"])
    cierre = time.fromisoformat(horario["cierre"])
    hora_actual = ahora.time().replace(second=0, microsecond=0)
    dia_actual = DIAS_ES[ahora.weekday()]

    if apertura <= cierre:
        abierto = dia_actual in dias_abiertos and apertura <= hora_actual <= cierre
    else:
        # Si el horario cruza medianoche, la franja posterior a medianoche
        # corresponde al día en que abrió el negocio.
        dia_anterior = DIAS_ES[(ahora.weekday() - 1) % 7]
        abierto = (
            (dia_actual in dias_abiertos and hora_actual >= apertura)
            or (dia_anterior in dias_abiertos and hora_actual <= cierre)
        )

    return {
        "abierto": abierto,
        "dia_hoy": dia_actual,
        "horario_hoy": f"{horario['apertura']}-{horario['cierre']}",
        "tiempo_estimado_domicilio_min": negocio["domicilio"]["tiempo_estimado_min"],
        "tiempo_estimado_recoger_min": negocio["recoger"]["tiempo_estimado_min"],
    }


def _calcular_total(negocio: dict, items: list[ItemPedido], tipo_entrega: str) -> tuple[float, list[dict], float]:
    catalogo = {p["id"]: p for p in negocio["menu"]}
    detalle = []
    subtotal_productos = 0
    for item in items:
        producto = catalogo.get(item.id)
        if producto is None:
            raise HTTPException(status_code=422, detail=f"El producto '{item.id}' no existe en el menú.")
        subtotal = producto["precio"] * item.cantidad
        subtotal_productos += subtotal
        detalle.append({**producto, "cantidad": item.cantidad, "subtotal": subtotal})
    total = subtotal_productos
    if tipo_entrega == "domicilio":
        total += negocio["domicilio"]["costo"]
    return total, detalle, subtotal_productos


@app.post("/pedidos")
def crear_pedido(pedido: NuevoPedido):
    negocio = cargar_negocio()

    if not pedido.cliente.strip():
        raise HTTPException(status_code=422, detail="El nombre del cliente es obligatorio.")
    if not pedido.items:
        raise HTTPException(status_code=422, detail="El pedido debe incluir al menos un producto.")
    if not pedido.confirmado:
        raise HTTPException(status_code=422, detail="El pedido requiere confirmación explícita.")
    if pedido.tipo_entrega == "domicilio" and not (pedido.direccion and pedido.direccion.strip()):
        raise HTTPException(status_code=422, detail="Falta la dirección para el domicilio.")

    total, detalle, subtotal_productos = _calcular_total(negocio, pedido.items, pedido.tipo_entrega)

    # El mínimo se calcula sobre los productos; el costo de domicilio se suma después.
    if pedido.tipo_entrega == "domicilio" and subtotal_productos < 20000:
        raise HTTPException(status_code=409, detail="El subtotal de productos no alcanza el mínimo de $20.000 para domicilio.")

    # Revalidación: se vuelve a comprobar disponibilidad justo antes de guardar
    disponibilidad = consultar_disponibilidad()
    if not disponibilidad["abierto"]:
        raise HTTPException(status_code=409, detail="GastroBott está cerrado en este momento.")

    codigo = f"GB-{uuid.uuid4().hex[:6].upper()}"
    registro = {
        "codigo": codigo,
        "cliente": pedido.cliente,
        "tipo_entrega": pedido.tipo_entrega,
        "direccion": pedido.direccion,
        "items": detalle,
        "total": total,
        "estado": "confirmado",
        "creado_en": datetime.now(ZONA_HORARIA).isoformat(timespec="seconds"),
        "cancelado_en": None,
    }

    pedidos = cargar_pedidos()
    pedidos.append(registro)
    guardar_pedidos(pedidos)

    return registro


@app.get("/pedidos/{codigo}")
def consultar_pedido(codigo: str):
    pedidos = cargar_pedidos()
    for p in pedidos:
        if p["codigo"] == codigo:
            return p
    raise HTTPException(status_code=404, detail="No existe un pedido con ese código.")


@app.delete("/pedidos/{codigo}")
def cancelar_pedido(codigo: str):
    pedidos = cargar_pedidos()
    for p in pedidos:
        if p["codigo"] == codigo:
            if p["estado"] == "cancelado":
                raise HTTPException(status_code=409, detail="El pedido ya estaba cancelado.")
            p["estado"] = "cancelado"
            p["cancelado_en"] = datetime.now(ZONA_HORARIA).isoformat(timespec="seconds")
            guardar_pedidos(pedidos)
            return p
    raise HTTPException(status_code=404, detail="No existe un pedido con ese código.")
