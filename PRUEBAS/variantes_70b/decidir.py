"""Decisiones de la revisión de las 245 variantes del 70B (Claude, 2026-11-20, a pedido de Paula:
«haz los cambios que recomienda aquí, apruébalos e impleméntalos»). Criterio de la guía de la
tanda: «ok» si pide lo mismo que la frase actual, es una orden clara y suena natural; ante la
duda, «descartar». Escribe la hoja con `decision` y `notas` llenas."""
import csv, sys

DESCARTAR = {
    # cambia el sentido o es ambigua
    "Levanta el brazo": "singular: el error es de los dos brazos",
    "Sube el brazo más arriba": "singular: el error es de los dos brazos",
    "Sube más el brazo": "singular: el error es de los dos brazos",
    "Abre los pies completamente": "pide el máximo, no «un poco más»",
    "Levanta las piernas": "no pide saltar",
    "Salta con las piernas": "suena raro",
    "Impulsa las piernas hacia arriba": "no pide saltar con claridad",
    "Levanta las piernas del suelo": "no pide saltar con claridad",
    "Estira completamente los codos": "contradice «sin bloquearlos»",
    "Corrige el tronco derecho": "«tronco derecho» se entiende como «recto»",
    "Mantén el tronco derecho": "«tronco derecho» se entiende como «recto»",
    "Endereza el tronco derecho": "«tronco derecho» se entiende como «recto»",
    "Endereza el tronco izquierdo": "«tronco izquierdo» no tiene sentido",
    "Corrige el tronco izquierdo": "«tronco izquierdo» no tiene sentido",
    "No inclines hacia la izquierda": "le falta qué no inclinar",
    "La cadera izquierda baja": "no es una orden",
    "La cadera derecha la bajas": "no es una orden",
    "La cadera derecha debe estar más baja": "no es una orden",
    "Desplaza la pierna izquierda hacia afuera": "suena rebuscado",
    "Amplía la apertura de la pierna izquierda": "suena rebuscado",
    "Amplia la separación de la pierna izquierda": "suena rebuscado y sin tilde",
    "Abre más hacia fuera con la pierna derecha": "suena raro",
    "Inclina la cadera hacia abajo": "«inclinar» no es lo pedido",
    "Desciende la cadera": "suena rebuscado",
    "Baja la cadera inmediatamente": "tono brusco",
    "Ajusta la cabeza alineándola": "suena raro",
    "Coloca la cabeza alineada": "suena raro",
    "Avanza con los hombros": "suena raro",
    "Endereza el codo izquierdo a noventa grados": "«enderezar» contradice 90°",
    "Coloca el codo izquierdo en posición recta": "«recta» contradice 90°",
    "Coloca el codo derecho en posición recta": "«recta» contradice 90°",
    "Corrige el codo izquierdo a posición de 90 grados": "suena raro",
    "Ajusta el codo derecho a posición correcta": "vago: no dice 90°",
    "Rectifica el codo derecho a 90 grados": "suena rebuscado",
    "Alinea el codo derecho a noventa": "suena raro",
    "Alarga la rodilla izquierda más": "la rodilla no se alarga",
    "Rodilla derecha estirada más": "no es una orden y suena raro",
    "Rodilla izquierda estirada": "no es una orden",
    "Rodilla izquierda estirada, sin flexión": "no es una orden",
    "Rodilla derecha estirada por completo": "no es una orden",
    "La rodilla derecha está demasiado flexionada, estírala": "larga; describe el error",
    "Ajusta el tronco": "vago",
    "Enderezalo ligeramente tronco": "mal escrita",
    "Rectifica el tronco": "suena rebuscado",
    "Endereza el tronco completamente": "pide el máximo",
    "Ajusta el tronco para que esté recto": "vaga",
    "Aumenta la flexión de la rodilla izquierda": "suena técnico",
    "Aumenta la flexión de la rodilla derecha": "suena técnico",
    "Profundiza más con la rodilla izquierda": "suena raro",
    "Profundiza más con la rodilla derecha": "suena raro",
    "Profundiza con la rodilla izquierda": "suena raro",
    "Profundiza con la rodilla derecha": "suena raro",
    "Profundiza más en la flexión de la rodilla derecha": "larga y técnica",
    "Rodilla izquierda, flexiona más": "le habla a la rodilla",
    "Rodilla derecha, flexiona un poco más": "le habla a la rodilla",
    "Flexiona más fuerte la rodilla izquierda": "«fuerte» no es lo pedido",
    "Flexiona la rodilla derecha más abajo": "suena raro",
    "Baja la rodilla derecha más": "suena raro",
    # el paso es lo que se alarga o acorta, no la pierna
    "Alarga la pierna": "lo que se alarga es el paso", "Pierna más larga": "lo que se alarga es el paso",
    "Alarga tu pierna": "lo que se alarga es el paso", "Extiende más tu pierna": "lo que se alarga es el paso",
    "Alarga la pierna para una zancada más larga": "lo que se alarga es el paso",
    "Alarga la pierna en la zancada": "lo que se alarga es el paso", "Extiende más la pierna": "lo que se alarga es el paso",
    "Alarga un poco la pierna": "lo que se alarga es el paso", "Estira la pierna": "lo que se alarga es el paso",
    "Alarga más la pierna": "lo que se alarga es el paso", "Alarga tu pierna en cada paso": "lo que se alarga es el paso",
    "Acorta la pierna en el paso": "lo que se acorta es el paso", "Acorta tu pierna al dar el paso": "lo que se acorta es el paso",
    "Acorta tu pierna": "lo que se acorta es el paso", "Reduce la longitud de tu pierna": "lo que se acorta es el paso",
    "Acorta un poco la pierna": "lo que se acorta es el paso", "Acorta la pierna en cada zancada": "lo que se acorta es el paso",
    "Acorta la zancada con tu pierna": "suena raro", "Pierna, acorta el paso": "le habla a la pierna",
    "Acorta con la pierna": "suena raro",
    "Mueve el hombro hacia delante": "singular: el error es de los dos hombros",
    "Lleva el hombro hacia adelante": "singular: el error es de los dos hombros",
    "Tira el hombro hacia delante": "singular: el error es de los dos hombros",
}

ruta, salida = sys.argv[1], sys.argv[2]
filas = list(csv.DictReader(open(ruta, encoding="utf-8")))
for f in filas:
    v = f["variante"].strip()
    if v in DESCARTAR:
        f["decision"], f["notas"] = "descartar", DESCARTAR[v]
    elif f["severidad"] == "alta" and "un poco" in v.lower():
        f["decision"], f["notas"] = "descartar", "pide «un poco» para un error de gravedad alta"
    else:
        f["decision"] = "ok"
with open(salida, "w", encoding="utf-8", newline="") as s:
    w = csv.DictWriter(s, fieldnames=list(filas[0].keys()))
    w.writeheader(); w.writerows(filas)
ok = sum(f["decision"] == "ok" for f in filas)
print(f"{len(filas)} filas: {ok} ok, {len(filas) - ok} descartar")
usadas = {f["variante"].strip() for f in filas}
print("descartes que no están en la hoja:", sorted(set(DESCARTAR) - usadas))
