/* visor: los botones que llevan a #demo centran el video en pantalla y lo inician */
(() => {
  const v = document.getElementById('visor');
  document.querySelectorAll('a[href="#demo"]').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    v.parentElement.scrollIntoView({ block: 'center' }); // el scroll suave lo da el CSS (y se apaga con reduced-motion)
    v.play().catch(() => {});
  }));
})();
