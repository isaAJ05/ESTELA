/* Componentes de la página: cada lista de tarjetas se pinta desde sus datos
   con una sola plantilla, para que todas las tarjetas de un tipo sean iguales.
   Para cambiar un texto, edita DATOS; para cambiar el diseño, la plantilla. */
(() => {
  const DATOS = {
    pasos: [
      { titulo: 'Te ve', texto: 'Una sola cámara web te mira en vivo. Nada se graba.' },
      { titulo: 'Encuentra tu cuerpo', texto: 'Ubica 33 puntos de tu cuerpo: hombros, codos, caderas, rodillas…' },
      { titulo: 'Mide tu postura', texto: 'Calcula cuánto doblas cada articulación y cuánto separas brazos y piernas.' },
      { titulo: 'Te compara', texto: 'Pone tu repetición al lado de una bien hecha, aunque vayas a otro ritmo.' },
      { titulo: 'Decide qué decirte', texto: 'Elige el error más importante y si vale la pena decirlo ahora o mejor callar.' },
      { titulo: 'Te habla', texto: 'Una voz en español te da la corrección, en menos de medio segundo.' }
    ],

    resultados: [
      { cifra: '0,1', unidad: 's', texto: 'Lo que tarda la voz en corregirte desde que Estela nota el error. Antes de mejorarla tardaba casi 4 segundos.' },
      { cifra: '25', unidad: 'img/s', texto: 'Estela sigue el ritmo de la cámara sin saltarse imágenes: ubica tu cuerpo en unas dos centésimas de segundo.' },
      { cifra: '0', unidad: '%', texto: 'Correcciones sobre algo que la cámara no podía ver. Si no ve bien una parte de tu cuerpo, prefiere callar.' },
      { cifra: '91', unidad: '/100', texto: 'Puntuación de facilidad de uso que le dieron las personas que la probaron. Por encima de 85 se considera «excelente».' }
    ],

    datos: [
      { cifra: '4 de 5', texto: 'participantes sintieron que Estela habla lo justo: ni de más ni de menos.' },
      { cifra: '5 de 5', texto: 'se sintieron con mucha confianza al usarla, incluidas quienes casi nunca hacen ejercicio.' },
      { cifra: '4 de 5', texto: 'la recomendarían a alguien que empieza a entrenar en casa.' }
    ],

    novedades: [
      { titulo: 'Tu perfil y tu historial', texto: 'Guarda tus sesiones y tus rutinas con nombre para que veas cómo avanzas. Solo anota tu actividad, nunca imágenes ni medidas de tu cuerpo, y lo puedes borrar cuando quieras.' },
      { titulo: 'Háblale: «Estela, pausa»', texto: 'Pausa, sigue o cambia de ejercicio con la voz, sin acercarte al teclado. Si no entiende, te pide repetir antes que hacer algo que no pediste.', etiqueta: 'equipo completo' },
      { titulo: 'Una entrenadora que te resume', texto: 'Al terminar la rutina te cuenta cómo te fue, y puedes preguntarle «¿cómo voy?» en cualquier momento.', etiqueta: 'equipo completo' },
      { titulo: 'Frases con más variedad', texto: 'Una inteligencia artificial local dice las correcciones con otras palabras para no sonar repetitiva. Si falla o tarda, Estela usa sus frases de siempre.', etiqueta: 'equipo completo' }
    ],

    // picto: trazos del muñeco en un lienzo de 120×120 (cuerpo, guía punteada y articulaciones)
    ejercicios: [
      {
        nombre: 'Jumping jacks', vista: 'de frente',
        desc: 'Abre y cierra brazos y piernas a la vez, con un pequeño salto.',
        vigila: ['Brazos que no llegan arriba', 'Pies poco separados en la apertura', 'Codos doblados al abrir'],
        frase: 'Abre más los pies en cada salto, sin perder el control.',
        picto: {
          alt: 'Figura haciendo jumping jacks, de frente',
          cabeza: [60, 27, 8],
          cuerpo: 'M60 37V70M60 43L45 29L35 14M60 43L75 29L85 14M60 70L50 88L40 106M60 70L70 88L80 106',
          articulaciones: [[45, 29], [75, 29], [50, 88], [70, 88]]
        }
      },
      {
        nombre: 'Abducción de cadera', vista: 'de frente · por pierna',
        desc: 'De pie, eleva una pierna hacia el lado sin inclinar el tronco.',
        vigila: ['Tronco que se inclina al lado contrario', 'Cadera que sube en vez de quedar nivelada', 'Pierna que se separa poco'],
        frase: 'Lleva la pierna izquierda un poco más hacia el lado, con control.',
        picto: {
          alt: 'Figura de pie elevando una pierna hacia el lado, de frente',
          cabeza: [56, 22, 8],
          cuerpo: 'M56 32V67M56 39L49 54L47 69M56 39L63 54L65 69M56 67L55 86L54 106M56 67L73 81L90 93',
          guia: 'M56 67L60 86L62 106',
          articulaciones: [[49, 54], [63, 54], [55, 86], [73, 81]]
        }
      },
      {
        nombre: 'Plancha', vista: 'de perfil',
        desc: 'Sostén el cuerpo en línea recta, apoyado en antebrazos y puntas de los pies.',
        vigila: ['Cadera que se hunde bajo la línea', 'Hombros que se van por delante de los codos', 'Rodillas que se doblan'],
        frase: 'Sube las caderas y mantén el cuerpo recto.',
        picto: {
          alt: 'Figura en plancha sobre antebrazos, de perfil',
          cabeza: [24, 62, 7],
          cuerpo: 'M36 68L70 85L88 94L106 103M36 68L36 104L14 105',
          articulaciones: [[36, 104], [70, 85], [88, 94]]
        }
      },
      {
        nombre: 'Zancada atrás', vista: 'de perfil · por pierna',
        desc: 'Con una pierna atrás y los pies quietos, baja y sube con el tronco erguido.',
        vigila: ['Tronco que se inclina al bajar', 'Rodilla que no llega a flexionarse lo suficiente', 'Paso demasiado corto o demasiado largo'],
        frase: 'Baja más, flexiona bien la rodilla izquierda.',
        picto: {
          alt: 'Figura en zancada atrás, de perfil',
          cabeza: [56, 27, 8],
          cuerpo: 'M56 37V72M56 44L63 57L59 69M56 72L79 74L81 105M56 72L47 100L25 104',
          guia: 'M79 74V58M79 74H95',
          articulaciones: [[63, 57], [79, 74], [47, 100]]
        }
      }
    ]
  };

  /* ---------- plantillas ---------- */
  const ICONO_VOZ = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 010 7M19 5a10 10 0 010 14"/></svg>';

  const Paso = p => `<li class="paso"><span class="nodo"></span><h3>${p.titulo}</h3><p>${p.texto}</p></li>`;

  const Resultado = r => `
    <div class="numero"><span class="sello sello-medido">Medido</span><span class="cifra">${r.cifra}<small>${r.unidad}</small></span><p>${r.texto}</p></div>`;

  const Dato = d => `<p class="dato"><b>${d.cifra}</b> ${d.texto}</p>`;

  const Novedad = n => `
    <article class="tarjeta">
      <h3>${n.titulo}</h3><p>${n.texto}</p>${n.etiqueta ? `<span class="vista">${n.etiqueta}</span>` : ''}
    </article>`;

  const Picto = ({ alt, cabeza: [cx, cy, r], cuerpo, guia, articulaciones }) => `
    <svg class="ej-picto" viewBox="0 0 120 120" role="img" aria-label="${alt}">
      <line class="suelo" x1="14" y1="107" x2="106" y2="107"/>
      <circle cx="${cx}" cy="${cy}" r="${r}"/><path d="${cuerpo}"/>${guia ? `<path class="guia" d="${guia}"/>` : ''}
      <g class="art">${articulaciones.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2.6"/>`).join('')}</g>
    </svg>`;

  const Ejercicio = e => `
    <article class="tarjeta ejercicio">
      ${Picto(e.picto)}
      <div class="ej-cuerpo">
        <div class="ej-cabeza"><h3>${e.nombre}</h3><span class="vista">${e.vista}</span></div>
        <p class="ej-desc">${e.desc}</p>
        <ul class="vigila">${e.vigila.map(v => `<li>${v}</li>`).join('')}</ul>
        <p class="frase">${ICONO_VOZ}«${e.frase}»</p>
      </div>
    </article>`;

  /* ---------- montaje: <elemento data-componente="nombre"> ---------- */
  const PLANTILLAS = { pasos: Paso, resultados: Resultado, datos: Dato, novedades: Novedad, ejercicios: Ejercicio };
  // shortcut: innerHTML solo con los DATOS de este archivo; si algún día llegan de fuera, escapar el texto
  document.querySelectorAll('[data-componente]').forEach(el => {
    const nombre = el.dataset.componente;
    el.innerHTML = DATOS[nombre].map(PLANTILLAS[nombre]).join('');
  });
})();
