// Las clases con las que una pantalla se asienta en la ventana, compartidas por el
// inicio, la guia y los esqueletos que las anuncian: con las mismas clases, el paso
// del esqueleto al contenido no mueve nada.
//
// En un computador con espacio (`roomy`: 64 rem de ancho y 42 rem de alto) la
// pantalla cabe en una sola vista: el titulo, los espacios y el relleno se calculan
// sobre la altura de la ventana (`dvh`), con un tope arriba --lo que se ve en una
// pantalla grande-- y un piso abajo --lo que aun se lee en la mas baja--, y el
// contenido se centra entre la barra y el pie (plan-estilos-2026-10.md, seccion 1).
// Fuera de `roomy` fluye y se desplaza como siempre.

/** El contenedor de una pantalla de una sola vista. */
export const PAGE_CONTENT =
  "mx-auto flex w-full max-w-content flex-col gap-10 px-4 py-12 tablet:px-8 tablet:py-16 roomy:my-auto roomy:gap-[clamp(0.75rem,2.6dvh,2.5rem)] roomy:py-[clamp(0.5rem,2.2dvh,3rem)]";

/**
 * El contenedor de la guia: como `PAGE_CONTENT`, con los espacios de un computador algo
 * mas apretados. La guia lleva mas que el inicio --contexto, cuatro pasos y dos bloques--
 * y, aun asi, tiene que caber en una sola vista en 1390 x 760: el aire entre bloques y
 * arriba y abajo cede con el alto de la ventana (y crece en una grande).
 */
export const GUIDE_CONTENT =
  "mx-auto flex w-full max-w-content flex-col gap-10 px-4 py-12 tablet:px-8 tablet:py-16 roomy:my-auto roomy:gap-[clamp(0.5rem,1.8dvh,2.25rem)] roomy:py-[clamp(0.25rem,1.2dvh,3rem)]";

/** El titulo de una pantalla de una sola vista. */
export const PAGE_TITLE =
  "font-display text-title font-light text-fg tablet:text-figure desktop:text-display roomy:text-[length:clamp(1.75rem,5.2dvh,3rem)]";

/**
 * El titulo de una pantalla de detalle --un caso, una traza, la bandeja--: tamano de
 * titulo de seccion y no de pagina, porque lo que importa en ellas es lo de abajo.
 * (Antes usaban `text-h2`, una clase que la escala de tipos ya no define: el titulo salia
 * del tamano del cuerpo.)
 */
export const DETAIL_TITLE = "font-display text-title font-medium text-balance text-fg";

/**
 * El titulo del caso del visitante y del caso de ejemplo: el mismo, y desde tableta con el
 * tamano y el peso de los titulos de pagina, que es lo primero que se lee al llegar.
 */
export const CASE_PAGE_TITLE = `${DETAIL_TITLE} tablet:text-figure tablet:font-light`;

/**
 * El ancho de la columna del caso del visitante y del caso de ejemplo. 52 rem y no los
 * 42 de antes (Miguel, 2026-10-12: "que todo el contenido se alargue hacia los laterales
 * al menos un poco"); en un telefono `w-full` manda y no cambia nada.
 */
export const CASE_COLUMN_WIDTH = "max-w-[52rem]";

/**
 * El ancho de la pantalla del visitante que abre su caso (Miguel, 2026-10-14): lleva dos
 * paneles lado a lado --el del ajustador y los datos del reporte-- y no caben en la columna
 * de `CASE_COLUMN_WIDTH`, que sigue siendo la del caso de ejemplo. 76 rem como maximo, con
 * el mismo relleno lateral; en un telefono `w-full` manda y no cambia nada.
 */
export const CASE_WORKSPACE_WIDTH = "max-w-[76rem]";

/**
 * Los dos paneles de la pantalla del visitante. Por debajo de `desktop` (64 rem) es una sola
 * columna y **manda el orden del documento**: primero los datos del reporte, despues el panel
 * del ajustador. Desde `desktop` son dos columnas, 7/12 para el panel del ajustador y 5/12
 * para los datos, alineadas arriba (sin eso la celda de los datos se estiraria hasta el alto
 * de la otra y no tendria por donde quedarse a la vista).
 */
export const CASE_WORKSPACE_PANES =
  "grid gap-4 desktop:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] desktop:items-start";

/** El panel del ajustador: en escritorio va a la izquierda aunque en el documento sea el segundo. */
export const CASE_ADJUSTER_PANE = "desktop:col-start-1 desktop:row-start-1";

/**
 * Los datos del reporte y las reglas: en escritorio van a la derecha y **se quedan a la vista
 * al desplazar la pagina**. La cabecera del sitio mide unos 3,3 rem (el control de la marca de
 * 44 px, 8 px de relleno y la raya), asi que se pega a 4,5 rem y mide, como mucho, la ventana
 * menos ese margen y 1 rem de aire abajo; si no cabe, se desplaza por dentro y se funde con el
 * fondo por el borde que sigue (`ut-scroll-fade-y`). El anillo de foco va por dentro: la
 * mascara de la fundida recortaria el de fuera.
 */
export const CASE_DATA_PANE =
  "flex flex-col gap-4 desktop:col-start-2 desktop:row-start-1 desktop:sticky desktop:top-[4.5rem] desktop:max-h-[calc(100dvh_-_5.5rem)] desktop:overflow-y-auto ut-scroll-fade-y focus-visible:-outline-offset-2";

/** El titulo de un bloque dentro de una pantalla de detalle. */
export const BLOCK_TITLE = "font-display text-lead font-medium text-fg";

/** El titulo de una seccion. */
export const SECTION_TITLE = "text-title font-medium text-fg";

/**
 * El contenedor de una pantalla que **no** cabe en una sola vista --cifras, gasto,
 * comparacion--: crece con su contenido y la pagina se desplaza. Recortar datos para
 * que quepan seria peor que desplazar.
 */
export const LONG_PAGE_CONTENT =
  "mx-auto flex w-full max-w-content flex-col gap-10 px-4 py-12 tablet:px-8 tablet:py-16";

/**
 * La rejilla de una fila de aseguradora, compartida por la fila y por su esqueleto
 * para que ocupen el mismo lugar.
 */
export const INSURER_ROW_GRID =
  "grid gap-4 border-t border-hairline py-5 tablet:grid-cols-[minmax(0,1fr)_auto] tablet:items-center roomy:py-[clamp(0.4rem,1.4dvh,1.25rem)]";

/**
 * El aire entre la linea de presentacion y el titulo de la seccion de aseguradoras en el
 * inicio (decision de Miguel, 2026-10-07: estaban demasiado juntos). Se suma al espacio
 * normal entre bloques y se encoge con la altura de la ventana, para que el inicio siga
 * cabiendo en una vista.
 */
export const HOME_HEADER_SPACE = "roomy:mb-[clamp(0.25rem,2.6dvh,1.75rem)]";

/**
 * La columna de lectura del chat (decision de Miguel, 2026-10-08: sin caja, como una
 * conversacion que ocupa la pagina). El encabezado, la linea del caso y el cuadro de
 * escribir van en esta columna; la conversacion usa `CHAT_TRANSCRIPT_GUTTER` para
 * caer en el mismo ancho. Contenido de 53 rem como maximo (decision de Miguel,
 * 2026-10-11: un poco mas ancha, de 45 rem); lo que se lee mide menos que eso --la
 * agente 72 caracteres, la burbuja de la persona 36 rem--, asi que ensanchar la
 * columna no alarga los renglones.
 */
export const CHAT_COLUMN = "mx-auto w-full max-w-[56rem] px-4 tablet:px-6";

/**
 * El relleno lateral de la conversacion: la region que se desplaza va **a todo el
 * ancho**, para que la barra de desplazamiento quede en el borde de la ventana y la
 * rueda funcione tambien sobre los margenes, y este relleno deja su contenido en la
 * misma columna que `CHAT_COLUMN` (53 rem, o el ancho menos el margen de la columna).
 */
export const CHAT_TRANSCRIPT_GUTTER =
  "px-[max(1rem,calc(50%_-_26.5rem))] tablet:px-[max(1.5rem,calc(50%_-_26.5rem))]";

/**
 * La pestana de polizas. En un computador con espacio (`roomy`) **la pagina no se
 * desplaza** (Miguel, 2026-10-11): el contenido mide lo que queda de la ventana, la lista
 * y el detalle se reparten ese alto y cada uno se desplaza por dentro si no le alcanza.
 * Las tarjetas de la lista se aprietan con el alto para que quepan todas en una pantalla
 * normal. Fuera de `roomy` todo fluye como una pagina.
 */
export const POLICIES_CONTENT =
  "mx-auto flex w-full max-w-content flex-col gap-6 px-4 py-12 tablet:px-8 tablet:py-16 roomy:min-h-0 roomy:flex-1 roomy:gap-[clamp(0.5rem,1.8dvh,1.5rem)] roomy:py-[clamp(0.5rem,2dvh,2rem)]";

/** La lista y el detalle de las polizas: ocupan el alto que queda y no lo pasan. */
export const POLICIES_PANES =
  "grid gap-6 desktop:grid-cols-[minmax(0,23rem)_minmax(0,1fr)] roomy:min-h-0 roomy:flex-1 roomy:grid-rows-[minmax(0,1fr)]";

/**
 * La lista de polizas. En un computador con espacio (`roomy`) es una rejilla de filas del
 * mismo alto: cada tarjeta mide lo que su texto pide como minimo y, si sobra ventana,
 * crece hasta 8 rem; lo que aun sobre se reparte entre las separaciones, de modo que la
 * lista termina donde termina el detalle en una pantalla grande y no deja un hueco abajo.
 * Si la ventana es baja y no caben las seis, la lista se desplaza por dentro y se funde
 * con el fondo por el borde que sigue (`ut-scroll-fade-y`): ninguna tarjeta queda cortada
 * a ras.
 */
export const POLICIES_LIST =
  "flex flex-col gap-2 roomy:grid roomy:min-h-0 roomy:auto-rows-[minmax(min-content,8rem)] roomy:content-between roomy:gap-[clamp(0.25rem,0.9dvh,0.5rem)] roomy:overflow-y-auto roomy:pr-1 ut-scroll-fade-y";

/**
 * Una poliza de la lista: su relleno vertical cede con el alto de la ventana. Con las tres
 * lineas en 20 px de interlineado y sin separacion entre ellas, las seis caben en 1390 x
 * 760 y en 1280 x 720.
 */
export const POLICIES_CARD_SPACE = "p-3 roomy:py-[clamp(0.25rem,0.9dvh,0.75rem)]";
