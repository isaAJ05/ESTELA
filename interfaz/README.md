# Interfaz de escritorio de ESTELA

Pantallas de la sesión: inicio, sesión en vivo (cámara con el esqueleto, contador, avisos, indicaciones habladas, pausa) y resumen. React + TypeScript compilado con Vite. `python -m estela` abre `dist/` en una ventana nativa con pywebview (WKWebView en macOS).

La interfaz **no decide nada**: muestra lo que manda Python. Qué error hubo, cuándo hablar, cuándo pausar o cuándo pasar de ejercicio lo decide el backend.

## Uso

```bash
cd interfaz
npm install            # una vez
npm run dev            # en el navegador, con el backend simulado (sin cámara ni Python)
npm run build          # compila dist/, que es lo que abre python -m estela
npm run typecheck
```

`dist/` está versionado, así que para correr la aplicación no hace falta Node. Solo hay que recompilar y subir `dist/` cuando se cambia algo de `src/`.

Para trabajar el diseño en el navegador:
- `npm run dev` usa el simulador (`src/bridge/simulado.ts`).
- Con el build, se usa `dist/index.html?simulado`.

Parámetros del simulador:
- `?velocidad=4` acelera el tiempo.
- `?escena=resumen` o `?escena=error` empieza en esa pantalla.

## Cómo se conecta con Python

```
Python                                         Interfaz
estela/ui/orquestador.py  (hilo de la sesión)
   └─ último EstadoFrame + último frame
estela/ui/ventana.py:Api  ◄── window.pywebview.api ──  src/bridge/pywebview.ts
estela/ui/contrato.py     ── JSON ──────────────────►  src/bridge/tipos.ts
```

- **Contrato.** `estela/ui/contrato.py` traduce el estado de la sesión a JSON y `src/bridge/tipos.ts` lo describe. Si un nombre cambia en un lado, hay que cambiarlo en el otro.
- **Long polling.** La interfaz pide `estado(desde)` y Python responde cuando hay una versión más nueva. El hilo de la sesión nunca espera a la interfaz. Si la interfaz va más lenta, se salta estados en vez de acumular retraso.
- **Frame de vídeo.** Viaja como JPEG de 640 px en base64, generado en memoria. No se guarda en ningún lado.
- **Rendimiento.** `src/estado/almacen.ts` evita re-renderizar React a 30 Hz:
  - cada componente lee solo su parte con `useEstado(selector)`;
  - el lienzo (`VistaCamara`) dibuja fuera de React con `requestAnimationFrame`.

## Funciones que el backend todavía no tiene

Algunas partes de la interfaz ya están hechas pero ocultas, porque dependen de algo que el backend aún no tiene:

| Capacidad | Qué muestra |
|---|---|
| `nivel` | selector de nivel en el inicio |
| `correctasConError` | correctas y con error |
| `guia` | movimiento de referencia animado |
| `resumenTexto` | resumen en lenguaje natural |
| `motivoSilencio` | motivo de silencio en la capa de depuración |
| `pausaManual` | botón y tecla de pausa |

Cada una se activa en `CAPACIDADES` de `estela/ui/contrato.py`. Ahí está también la tabla con el campo que debe mandar el backend y la tarea correspondiente.

Para activar una:
1. Implementarla en el backend.
2. Mandar el campo con el nombre indicado.
3. Ponerla en `True`.

En la interfaz no hay que tocar nada. Para buscar en el código dónde se usa una capacidad: `useCapacidad('<nombre>')`.

## Cómo añadir o quitar algo

| Quiero… | Dónde |
|---|---|
| Activar una función que el backend ya tiene | `CAPACIDADES` en `estela/ui/contrato.py` (ver la tabla de arriba) |
| Un dato nuevo por frame (p. ej. un contador) | campo en `EstadoFrame` → `estado_a_dict` en `contrato.py` → `EstadoSesion` en `src/bridge/tipos.ts` → leerlo con `useEstado` donde se muestre |
| Un dato nuevo del resumen | `Sesion.resumen()` → `resumen_a_dict` → `Resumen` en `tipos.ts` → `pantallas/Resumen.tsx` |
| Un comando nuevo (p. ej. pausar) | método en `Orquestador` (se aplica en el hilo de la sesión vía `_aplicar_comandos`) → `Api` en `estela/ui/ventana.py` → `Bridge` en `tipos.ts`, `pywebview.ts` y `simulado.ts` |
| Una fase o pantalla nueva (p. ej. colocación) | constante y transición en `Orquestador` → `Fase` en `tipos.ts` → un `case` en `App.tsx` y un archivo en `pantallas/` |
| Un ejercicio nuevo | solo su skill y la rutina (como siempre). La interfaz lo muestra con su nombre y orientación; si no tiene figura propia, sale la figura neutra «de pie» (`componentes/Figura.tsx`) |
| Quitar una función de la vista | ponerla en `False` en `CAPACIDADES`, o quitar el componente de su pantalla |

Antes de subir: `pytest`, `npm run typecheck` y `npm run build`.

## Tamaño de ventana

Todos los tamaños están en `rem` y la raíz crece con la ventana (`estilos/base.css`). Así la interfaz se ve proporcionada de 960×600 (el mínimo de la ventana) a 2560×1440: en una pantalla grande todo crece para leerse desde 3 m. Por debajo de 1100 px de ancho, los botones de la sesión muestran solo el ícono. Para medidas nuevas, usar `rem` y no `px`, salvo en bordes de 1–2 px.

## Teclas

| Tecla | Acción |
|---|---|
| `N` | siguiente ejercicio |
| `R` | reiniciar el ejercicio |
| `Esc` | terminar (pide confirmación) |
| `D` | en la sesión: FPS, latencia por etapa, fase y orientación. En el resumen: panel técnico con abstenciones del motor y latencia p50/p95 |

## Estructura

```
src/
  bridge/       contrato (tipos.ts), conexión con pywebview y simulador
  estado/       almacén del último estado
  pantallas/    Inicio, Sesion, Resumen
  componentes/  figura de cada ejercicio, contador, temporizador, lienzo de la cámara
  estilos/      tokens.css (colores, radios, espaciado), base.css y pantallas.css
```

Los colores salen de `estilos/tokens.css`. Los componentes no usan valores sueltos.
