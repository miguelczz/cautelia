// Dejar quieta la pagina mientras una ventana modal esta abierta.
//
// `showModal()` deja inerte lo de atras para el foco y el raton, pero **no** para el
// desplazamiento: la rueda sobre el fondo oscurecido movia la pagina de detras
// (visto el 2026-10-08 con el panel de documentos). Se esconde el desbordamiento del
// documento mientras la ventana esta abierta y se devuelve como estaba al cerrar.
//
// Si la pagina tenia barra de desplazamiento se reserva su hueco: sin eso, al
// desaparecer la barra todo el contenido saltaria unos pixeles hacia un lado.

/** Bloquea el desplazamiento del documento; devuelve como deshacerlo. */
export function lockPageScroll(): () => void {
  const raiz = document.documentElement;
  const antes = { overflow: raiz.style.overflow, gutter: raiz.style.scrollbarGutter };
  const teniaBarra = window.innerWidth > raiz.clientWidth;
  raiz.style.overflow = "hidden";
  if (teniaBarra) {
    raiz.style.scrollbarGutter = "stable";
  }
  return () => {
    raiz.style.overflow = antes.overflow;
    raiz.style.scrollbarGutter = antes.gutter;
  };
}
