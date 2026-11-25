(() => {
  const quieto = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const dprMax = Math.min(window.devicePixelRatio || 1, 2);

  /* ---------- cielo de fondo con estela que sigue al puntero ---------- */
  const cielo = document.getElementById('cielo');
  const c = cielo.getContext('2d');
  let W = 0, H = 0, estrellas = [], fugaz = null, rastro = [];
  function medirCielo() {
    W = innerWidth; H = innerHeight;
    cielo.width = W * dprMax; cielo.height = H * dprMax;
    c.setTransform(dprMax, 0, 0, dprMax, 0, 0);
    const n = Math.round(Math.min(220, W * H / 7000));
    estrellas = Array.from({ length: n }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      r: Math.random() * 1.2 + 0.25, f: Math.random() * Math.PI * 2,
      v: 0.4 + Math.random() * 1.4, dorada: Math.random() < 0.18
    }));
  }
  medirCielo();
  addEventListener('resize', medirCielo);
  // la estela no va pegada al puntero: un seguidor lo alcanza con suavidad
  let objetivo = null, seguidor = null;
  addEventListener('pointermove', e => {
    if (quieto) return;
    objetivo = { x: e.clientX, y: e.clientY };
    if (!seguidor) seguidor = { ...objetivo };
  }, { passive: true });

  function lanzarFugaz() {
    const x = Math.random() * W * 0.7 + W * 0.2, y = Math.random() * H * 0.35;
    fugaz = { x, y, vx: -(5 + Math.random() * 4), vy: 2.2 + Math.random() * 1.5, vida: 1, cola: [] };
  }
  let siguienteFugaz = 2500;
  function pintarCielo(t, dt) {
    c.clearRect(0, 0, W, H);
    for (const s of estrellas) {
      const a = quieto ? 0.6 : 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(t / 1000 * s.v + s.f));
      c.globalAlpha = a * 0.85;
      c.fillStyle = s.dorada ? '#ffd877' : '#d9d2ff';
      c.beginPath(); c.arc(s.x, s.y, s.r, 0, Math.PI * 2); c.fill();
    }
    c.globalAlpha = 1;
    if (quieto) return;
    siguienteFugaz -= dt;
    if (!fugaz && siguienteFugaz < 0) { lanzarFugaz(); siguienteFugaz = 5000 + Math.random() * 6000; }
    if (fugaz) {
      fugaz.cola.unshift({ x: fugaz.x, y: fugaz.y }); if (fugaz.cola.length > 26) fugaz.cola.pop();
      fugaz.x += fugaz.vx; fugaz.y += fugaz.vy; fugaz.vida -= 0.012;
      for (let i = 1; i < fugaz.cola.length; i++) {
        const k = 1 - i / fugaz.cola.length;
        c.strokeStyle = `rgba(255,${200 + 30 * k | 0},${120 + 120 * (1 - k) | 0},${k * fugaz.vida})`;
        c.lineWidth = 2.2 * k; c.lineCap = 'round';
        c.beginPath(); c.moveTo(fugaz.cola[i - 1].x, fugaz.cola[i - 1].y); c.lineTo(fugaz.cola[i].x, fugaz.cola[i].y); c.stroke();
      }
      c.fillStyle = `rgba(255,240,200,${fugaz.vida})`; c.beginPath(); c.arc(fugaz.x, fugaz.y, 1.8, 0, Math.PI * 2); c.fill();
      if (fugaz.vida <= 0 || fugaz.x < -50 || fugaz.y > H + 50) fugaz = null;
    }
    if (objetivo && seguidor) {
      const f = 1 - Math.exp(-dt / 140);
      const nx = seguidor.x + (objetivo.x - seguidor.x) * f, ny = seguidor.y + (objetivo.y - seguidor.y) * f;
      if (Math.hypot(nx - seguidor.x, ny - seguidor.y) > 0.4) rastro.push({ x: nx, y: ny, vida: 1 });
      seguidor.x = nx; seguidor.y = ny;
      if (rastro.length > 90) rastro.shift();
    }
    for (const p of rastro) p.vida -= dt / 1500;
    rastro = rastro.filter(p => p.vida > 0);
    for (let i = 1; i < rastro.length; i++) {
      const a = rastro[i - 1], b = rastro[i], k = Math.min(a.vida, b.vida);
      const mezcla = i / rastro.length;
      c.strokeStyle = `rgba(${169 + 86 * mezcla | 0},${157 + 44 * mezcla | 0},${255 - 178 * mezcla | 0},${k * 0.8})`;
      c.lineWidth = 0.4 + 2.2 * k * mezcla; c.lineCap = 'round';
      c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(b.x, b.y); c.stroke();
    }
    const cabeza = rastro[rastro.length - 1];
    if (cabeza) {
      const g = c.createRadialGradient(cabeza.x, cabeza.y, 0, cabeza.x, cabeza.y, 10);
      g.addColorStop(0, `rgba(255,214,120,${cabeza.vida * 0.9})`); g.addColorStop(1, 'rgba(255,214,120,0)');
      c.fillStyle = g; c.beginPath(); c.arc(cabeza.x, cabeza.y, 10, 0, Math.PI * 2); c.fill();
    }
  }

  /* ---------- escenario: figura que hace jumping jacks contra la guía ---------- */
  const esc = document.getElementById('escena');
  const e = esc.getContext('2d');
  const repEl = document.getElementById('rep');
  const angTu = document.getElementById('ang-tu');
  const angRef = document.getElementById('ang-ref');
  const burbuja = document.getElementById('burbuja');
  const bTipo = document.getElementById('burbuja-tipo');
  const bFrase = document.getElementById('burbuja-frase');
  let EW = 0, EH = 0;
  function medirEscena() {
    const r = esc.getBoundingClientRect();
    EW = r.width; EH = r.height;
    esc.width = EW * dprMax; esc.height = EH * dprMax;
    e.setTransform(dprMax, 0, 0, dprMax, 0, 0);
  }
  medirEscena();
  addEventListener('resize', medirEscena);

  const PERIODO = 1500;
  // amplitud de brazos y piernas de cada repetición (1 = como la guía)
  const amplitudes = [
    [0.97, 1], [1, 0.98], [0.64, 0.95], [0.68, 0.9], [0.96, 0.97],
    [1, 0.98], [0.98, 0.62], [1, 1], [0.99, 0.98], [1, 1]
  ];
  // lo que se dice en cada repetición, en su punto más alto
  const guion = {
    2: { tipo: 'Corrección · brazos', frase: 'Sube un poco más los brazos, hasta donde te resulte cómodo.', ref: false },
    6: { tipo: 'Corrección · pies', frase: 'Abre un poco más los pies, con control.', ref: false },
    9: { tipo: 'Refuerzo', frase: 'Vas muy bien, sigue así.', ref: true }
  };
  const rad = g => g * Math.PI / 180;
  const lerp = (a, b, t) => a + (b - a) * t;

  function postura(p, ab, ap) {
    const brazo = lerp(14, 165, p * ab);
    const pierna = lerp(3, 19, p * ap);
    return { brazo, pierna, salto: 0.07 * Math.sin(Math.PI * p) };
  }

  function figura(cx, suelo, s, pos, color, alfa, resaltarBrazos, resaltarPies) {
    const lp = rad(pos.pierna), lb = rad(pos.brazo);
    const caderaY = suelo - s * Math.cos(lp) - pos.salto * s;
    const hombroY = caderaY - 1.22 * s;
    const pts = {};
    for (const lado of [-1, 1]) {
      const cad = [cx + lado * 0.12 * s, caderaY];
      const rod = [cad[0] + lado * Math.sin(lp) * 0.5 * s, cad[1] + Math.cos(lp) * 0.5 * s];
      const pie = [rod[0] + lado * Math.sin(lp) * 0.5 * s, rod[1] + Math.cos(lp) * 0.5 * s];
      const hom = [cx + lado * 0.25 * s, hombroY];
      const codo = [hom[0] + lado * Math.sin(lb) * 0.38 * s, hom[1] + Math.cos(lb) * 0.38 * s];
      const lb2 = lb + rad(8);
      const mano = [codo[0] + lado * Math.sin(lb2) * 0.36 * s, codo[1] + Math.cos(lb2) * 0.36 * s];
      pts[lado] = { cad, rod, pie, hom, codo, mano };
    }
    const cuello = [cx, hombroY - 0.08 * s], cabeza = [cx, hombroY - 0.33 * s];
    e.save();
    e.globalAlpha = alfa; e.lineCap = 'round'; e.lineJoin = 'round';
    e.lineWidth = Math.max(3, 0.075 * s);
    const tramo = (a, b, col) => { e.strokeStyle = col; e.beginPath(); e.moveTo(a[0], a[1]); e.lineTo(b[0], b[1]); e.stroke(); };
    const colBrazo = resaltarBrazos ? '#f4a340' : color;
    const colPierna = resaltarPies ? '#f4a340' : color;
    tramo(pts[-1].hom, pts[1].hom, color);
    tramo(pts[-1].cad, pts[1].cad, color);
    tramo(cuello, [cx, caderaY], color);
    for (const lado of [-1, 1]) {
      const q = pts[lado];
      tramo(q.hom, q.codo, colBrazo); tramo(q.codo, q.mano, colBrazo);
      tramo(q.cad, q.rod, colPierna); tramo(q.rod, q.pie, colPierna);
    }
    e.lineWidth = Math.max(2.5, 0.06 * s);
    e.strokeStyle = color; e.beginPath(); e.arc(cabeza[0], cabeza[1], 0.17 * s, 0, Math.PI * 2); e.stroke();
    if (alfa > 0.6) {
      e.fillStyle = '#fff8e6';
      for (const lado of [-1, 1]) for (const k of ['hom', 'codo', 'mano', 'cad', 'rod', 'pie']) {
        const v = pts[lado][k]; e.beginPath(); e.arc(v[0], v[1], Math.max(2, 0.03 * s), 0, Math.PI * 2); e.fill();
      }
    }
    e.restore();
  }

  let burbujaRep = -1, ocultarEn = 0;
  function decir(item, t) {
    bTipo.textContent = item.tipo; bFrase.textContent = item.frase;
    burbuja.classList.toggle('refuerzo', item.ref);
    burbuja.classList.remove('callada');
    ocultarEn = t + 2600;
  }

  function pintarEscena(t) {
    e.clearRect(0, 0, EW, EH);
    const ciclo = t / PERIODO, n = Math.floor(ciclo), rep = n % amplitudes.length, fase = ciclo - n;
    const p = (1 - Math.cos(2 * Math.PI * fase)) / 2;
    const [ab, ap] = amplitudes[rep];
    const s = EH * 0.27, cx = EW / 2, suelo = EH * 0.78;

    // sombra en el suelo
    const g = e.createRadialGradient(cx, suelo + 4, 0, cx, suelo + 4, s * 0.9);
    g.addColorStop(0, 'rgba(128,107,255,.35)'); g.addColorStop(1, 'rgba(128,107,255,0)');
    e.fillStyle = g; e.beginPath(); e.ellipse(cx, suelo + 4, s * 0.9, s * 0.12, 0, 0, Math.PI * 2); e.fill();

    const ref = postura(p, 1, 1), tu = postura(p, ab, ap);
    const enPico = p > 0.55;
    figura(cx, suelo, s, ref, '#a99dff', 0.38, false, false);
    figura(cx, suelo, s, tu, '#ffc94d', 1, ab < 0.8 && enPico, ap < 0.8 && enPico);

    repEl.textContent = `Rep ${rep + 1} / ${amplitudes.length}`;
    angTu.textContent = `${Math.round(tu.brazo)}°`;
    angRef.textContent = `${Math.round(ref.brazo)}°`;
    angTu.style.color = (ab < 0.8 && enPico) ? '#f4a340' : '';

    if (guion[rep] && fase > 0.5 && burbujaRep !== n) { burbujaRep = n; decir(guion[rep], t); }
    if (ocultarEn && t > ocultarEn) { burbuja.classList.add('callada'); ocultarEn = 0; }
  }

  if (quieto) {
    pintarCielo(0, 0);
    // fotograma fijo: repetición 3 en su punto más alto, con la corrección visible
    const t = PERIODO * 2.5;
    pintarEscena(t);
    burbuja.classList.remove('callada');
    return;
  }
  let antes = performance.now(), visible = true;
  document.addEventListener('visibilitychange', () => { visible = !document.hidden; antes = performance.now(); });
  // arranca en la repetición 3 para que la primera corrección llegue enseguida
  const inicio = performance.now() - PERIODO * 2.1;
  function bucle(ahora) {
    const dt = Math.min(64, ahora - antes); antes = ahora;
    if (visible) { pintarCielo(ahora, dt); pintarEscena(ahora - inicio); }
    requestAnimationFrame(bucle);
  }
  requestAnimationFrame(bucle);
})();
