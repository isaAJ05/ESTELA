"""Decisiones de la revisión de las 242 variantes del 14B (Claude, 2026-11-20, a pedido de Paula).
Mismo criterio que las del 70B (`../variantes_70b/decidir.py`): «ok» si pide lo mismo que la
frase actual, es una orden clara y suena natural; ante la duda, «descartar». Además, por el
estilo del 14B (frases más largas): descartar si pasa de 12 palabras, si son dos oraciones o si
en gravedad alta pide «un poco» o «ligeramente»."""
import csv, re, sys

T = "«tronco derecho» se entiende como «recto»"
PIERNA = "lo que se alarga es el paso, no la pierna"
TECNICA = "suena técnica o rebuscada"
DESCARTAR = {
    "Alienta a tus brazos a subir más en el ejercicio.": "suena raro",
    "Aumenta la apertura de los pies, con control.": TECNICA,
    "Aumenta la apertura de los pies, controlado.": TECNICA,
    "Extiende los pies un poco más, controlado.": "los pies no se extienden: se separan",
    "Estira los pies hacia los lados, mantén la postura.": "los pies no se estiran: se separan",
    "Alza las piernas del suelo, realiza un salto completo.": "«alza las piernas» no es saltar",
    "Estás abriendo sin saltar, eleva las piernas del suelo.": "«eleva las piernas» no pide saltar con claridad",
    "Al abrir las piernas, asegúrate de saltar y no tocar el suelo.": "«no tocar el suelo» no tiene sentido al aterrizar",
    "Estira los codos un poco más, mantén la flexión natural.": "se contradice",
    "Haz más extensión en los codos, sin forzar.": TECNICA,
    "Aumenta el estiramiento de los codos, no los dobles demasiado.": TECNICA,
    "Estira más los codos, mantén la flexión mínima.": "se contradice",
    "Abre completamente los codos, sin cerrarlos.": "contradice «sin bloquearlos»",
    "Estira los codos aún más, manténlos en extensión completa.": "contradice «sin bloquearlos»",
    "Asegúrate de estirar los codos al máximo, sin doblarlos.": "contradice «sin bloquearlos»",
    "Extiende los codos lo suficiente, evitando cualquier flexión.": "contradice «sin bloquearlos»",
    "Mantén el tronco derecho más recto, no te inclines hacia la derecha.": T,
    "Corrige la inclinación del tronco derecho, manténlo vertical.": T,
    "Evita inclinar el tronco derecho, manténlo centrado.": T,
    "Mantén el tronco derecho recto, no inclinado hacia la derecha.": T,
    "Haz que el tronco se mantenga vertical, no hacia la derecha.": "suena raro",
    "Mantén el tronco recto, no hacia la izquierda.": "le falta el verbo",
    "No gires el tronco hacia la izquierda durante el movimiento.": "el error es inclinarse, no girar",
    "No elevas la cadera izquierda, bájala.": "error de gramática («elevas»)",
    "Mantén la cadera izquierda baja, no la estés elevando.": "suena raro",
    "Baja la cadera derecha, no la elevés.": "error de gramática («elevés»)",
    "La cadera derecha debe estar más baja.": "no es una orden",
    "Extiende más la pierna izquierda hacia el exterior.": TECNICA,
    "Aumenta la abducción de la pierna izquierda, mantén el equilibrio.": TECNICA,
    "Dirige la pierna derecha hacia el lateral, con precisión.": "«con precisión» sobra",
    "Aumenta la apertura de la pierna derecha, sin forzar.": TECNICA,
    "Aumenta la apertura de la pierna derecha hacia el lateral, permanece firme.": TECNICA,
    "Aumenta la apertura de la pierna derecha, sin perder estabilidad.": TECNICA,
    "Eleva las caderas hacia arriba.": "redundante",
    "Mantén las caderas elevadas, no bajas.": "mal escrita",
    "Desciende ligeramente las caderas.": TECNICA,
    "Asegura que la cabeza esté en línea con el cuerpo.": "error de gramática («asegura que»)",
    "Posiciona la cabeza de manera que esté alineada con el cuerpo.": TECNICA,
    "Alinea la cabeza, ni inclinada hacia adelante ni atrás.": "suena raro",
    "Atrás con los hombros, mantén la alineación vertical sobre el suelo.": "suena raro",
    "Haz retroceder los hombros, alinea sobre el punto de apoyo.": TECNICA,
    "Posiciona los hombros atrás, en línea con el punto de apoyo.": TECNICA,
    "Sitúa los hombros hacia atrás, sobre el suelo.": "suena raro",
    "Haz retroceder los hombros, en línea con el punto de apoyo.": TECNICA,
    "Dirige los hombros hacia la dirección de la cara.": "suena raro",
    "Sitúa los hombros en frente del apoyo, sin retrasarlos.": "suena raro",
    "Asegura que los hombros estén adelantados sobre el apoyo.": "error de gramática («asegura que»)",
    "Posiciona los hombros correctamente, hacia delante sobre el apoyo.": TECNICA,
    "Mantén el codo izquierdo en una posición recta.": "«recta» contradice 90°",
    "Posiciona el codo derecho formando un ángulo recto.": TECNICA,
    "Asegura que el codo derecho esté alineado a 90 grados.": "error de gramática («asegura que»)",
    "Posiciona el codo derecho formando un ángulo de 90 grados.": TECNICA,
    "Mantén el codo derecho en una posición de 90 grados sin desviaciones.": TECNICA,
    "Asegura que el codo derecho esté en un ángulo de noventa grados.": "error de gramática («asegura que»)",
    "Haz más fuerza para estirar la rodilla izquierda.": "no se trata de fuerza",
    "Haz más fuerza para estirar la rodilla derecha.": "no se trata de fuerza",
    "Haz más fuerza en la rodilla derecha para que se estire.": "no se trata de fuerza",
    "Aumenta el estiramiento de la rodilla izquierda.": TECNICA,
    "Aumenta el estiramiento de la rodilla derecha.": TECNICA,
    "Tensa la rodilla derecha, no la dobles.": "«tensa» no es lo pedido",
    "Rectifica la postura del tronco.": TECNICA,
    "Haz que el tronco se alinee correctamente.": "vaga",
    "Mantén el tronco recto, no lo inclines demasiado hacia adelante.": "el error puede ser hacia atrás también",
    "No inclinas el tronco hacia delante, tenlo vertical.": "error de gramática («inclinas»)",
    "No inclinas el tronco, deja que esté en posición neutral.": "error de gramática («inclinas»)",
    "Corrige la postura: el tronco debe estar bien alineado, no inclinado.": "larga y no es una orden directa",
    "Baja más la rodilla izquierda, asegurando suficiente profundidad.": TECNICA,
    "Baja más la rodilla izquierda, flexionando con mayor amplitud.": TECNICA,
    "Baja más la rodilla derecha, flexionando con mayor amplitud.": TECNICA,
    "Baja más la rodilla derecha, profundiza el movimiento con control.": TECNICA,
    "Baja más la rodilla izquierda hasta lograr la profundidad correcta.": TECNICA,
    "Baja más, flexionando la rodilla derecha con control y profundidad suficiente.": TECNICA,
    "Flexiona más la rodilla derecha, profundizando el movimiento con control.": TECNICA,
    "Baja con un paso más corto, para mejorar la técnica.": "califica la técnica",
    "Haz más corto el paso al descender, para evitar errores.": "suena a regaño",
    "Haz más corto el paso al descender, para mejorar la técnica.": "califica la técnica",
    "Ajusta la longitud del paso para mantener control.": "vaga",
    "No dejes que la pierna se extienda demasiado al avanzar.": "la zancada es hacia atrás, no avanza",
}

ruta, salida = sys.argv[1], sys.argv[2]
filas = list(csv.DictReader(open(ruta, encoding="utf-8")))
for f in filas:
    v = f["variante"].strip()
    palabras = len(re.findall(r"\w+", v))
    if v in DESCARTAR:
        motivo = DESCARTAR[v]
    elif re.search(r"\b(aumenta la flexi[oó]n|profundidad)\b", v, re.I):
        motivo = TECNICA
    elif re.search(r"\b(alarga|estira|extiende|extensi[oó]n)\b.*\bpierna\b", v, re.I) and f["error_id"] == "paso_corto":
        motivo = PIERNA
    elif re.search(r"\.\s+\S", v):
        motivo = "son dos oraciones"
    elif palabras > 12:
        motivo = f"larga ({palabras} palabras)"
    elif f["severidad"] == "alta" and re.search(r"\b(un poco|ligeramente)\b", v, re.I):
        motivo = "pide «un poco» para un error de gravedad alta"
    else:
        motivo = ""
    f["decision"], f["notas"] = ("descartar", motivo) if motivo else ("ok", "")
with open(salida, "w", encoding="utf-8", newline="") as s:
    w = csv.DictWriter(s, fieldnames=list(filas[0].keys()))
    w.writeheader(); w.writerows(filas)
ok = sum(f["decision"] == "ok" for f in filas)
print(f"{len(filas)} filas: {ok} ok, {len(filas) - ok} descartar")
print("descartes que no están en la hoja:", sorted(set(DESCARTAR) - {f['variante'].strip() for f in filas}))
