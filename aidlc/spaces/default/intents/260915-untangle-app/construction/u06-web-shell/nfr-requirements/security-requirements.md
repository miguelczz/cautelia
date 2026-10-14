# Requisitos de seguridad — U6 `web-shell`

U6 es la puerta por la que entra cualquiera que abra la demo: sirve la
aplicación, sus cabeceras y dos rutas sin credencial (la salud y el directorio
del sitio). No autentica a nadie ni guarda casos, así que su superficie de
ataque no está en la identidad sino en **lo que el navegador ejecuta y a quién
le habla**, en **lo que las rutas públicas cuentan** y en **las dos tablas
nuevas** de la telemetría de activación.

Todo requisito lleva un identificador estable y el comando que produce su valor
real. **`mise run test:u6` y `mise run a11y` no existen todavía**: los crea la
generación de código de esta unidad y los declara su diseño de infraestructura.
Los demás comandos citados existen hoy.

## Modelo de amenazas

Cuatro elementos y sus flujos, revisados con STRIDE. La frontera de confianza
es una sola: entre el navegador de un visitante anónimo y el proceso.

| Elemento | Amenaza (STRIDE) | Qué podría pasar | Mitigación | Requisito |
| --- | --- | --- | --- | --- |
| Aplicación en el navegador | Tampering / Elevation | Un texto controlado por un tercero se inserta como HTML y ejecuta código (XSS) | Todo texto se dibuja como texto; nada se inserta como HTML; política de contenido sin scripts en línea no declarados | SEC-U6.1, SEC-U6.8 |
| Aplicación en el navegador | Information disclosure | La página le habla a un tercero (fuentes, analítica, CDN) y le revela la dirección y la hora de cada visita | Cero peticiones a orígenes de terceros | SEC-U6.2 |
| Aplicación en el navegador | Information disclosure | Datos de un caso quedan en el almacenamiento del navegador y los lee quien use el equipo después | El almacenamiento solo guarda preferencias | SEC-U6.5 |
| Rutas públicas (salud, sitio) | Information disclosure | Un error o la salud revelan configuración, rutas internas, trazas de pila o valores de claves | Errores con la forma de C-01 y sin detalle; salud sin valores sensibles | SEC-U6.3, SEC-U6.4 |
| Rutas públicas | Spoofing | Una página del aplicativo se incrusta en un marco ajeno para engañar a quien la ve | Prohibición de marcos | SEC-U6.1 |
| Rutas de caso | Information disclosure | La diferencia entre "enlace manipulado" y "caso que no existe" permite adivinar qué casos existen | Misma página y mismo texto para los dos (BR5.6) | SEC-U6.6 |
| Tablas de activación | Information disclosure | El avance de una sesión de una aseguradora se lee desde otra, o el conteo apunta a una persona | Aislamiento por aseguradora con su prueba; sin columnas de texto libre ni de dato personal; borrado nocturno del avance | NFR10.5, NFR11.7, NFR19.3 |
| Cadena de suministro | Tampering | Una dependencia nueva de la interfaz trae código malicioso o una vulnerabilidad conocida | Lockfile con integridad, instalación congelada, scripts de instalación bloqueados, auditoría que bloquea | SEC-U6.7 |
| Rutas públicas | Denial of service | Tráfico que agota el proceso | Las dos rutas no llaman a ningún proveedor ni gastan dinero; su costo es una lectura de configuración y las sondas; el límite de red es del hospedaje (`infra`) | SEC-U6.9 |

**Repudiation** no aplica aquí: U6 no toma decisiones sobre casos ni acciones de
personas que haya que atribuir. Las decisiones del ajustador y su rastro son de
U14.

## Objetivos medibles

| ID | Requisito | Valor esperado | Comando |
| --- | --- | --- | --- |
| SEC-U6.1 | Toda respuesta del proceso —aplicación, estáticos, API y errores— lleva el conjunto único de cabeceras: política de seguridad de contenido **sin** `unsafe-inline` ni `unsafe-eval` para scripts (el paso mínimo de modo se autoriza por su huella), prohibición de marcos, prohibición de adivinar el tipo, política de referencia, política de permisos que niega lo que el aplicativo no usa, y transporte estricto cuando se sirve por HTTPS | **100 % de las respuestas recorridas** con el conjunto completo | `mise run test:u6` |
| SEC-U6.2 | Peticiones del navegador a orígenes distintos del propio, en todas las pantallas registradas | **Exactamente 0** | `mise run a11y` (registra cada petición de red del recorrido) |
| SEC-U6.3 | Contenido sensible en las respuestas de salud y del directorio del sitio: valores de claves, direcciones de base de datos, rutas del disco, trazas de pila, identificadores de cuentas de proveedor | **Exactamente 0** | `mise run test:u6` |
| SEC-U6.4 | Errores no previstos de la API con `code: internal` y sin detalle interno en el cuerpo | **100 %** de los errores provocados en la prueba | `mise run test:u6` |
| SEC-U6.5 | Claves del almacenamiento del navegador tras recorrer todas las pantallas, distintas de la preferencia de modo y, donde aplica, de idioma | **Exactamente 0** | `mise run a11y` (inspecciona el almacenamiento al terminar) |
| SEC-U6.6 | Diferencia visible entre la página de un enlace manipulado y la de un caso inexistente | **Ninguna**: mismo texto, mismo estado HTTP de la API | `mise run test:u6` |
| SEC-U6.7 | Dependencias nuevas de la interfaz: lockfile con integridad, instalación congelada, scripts de instalación bloqueados salvo la lista permitida, auditoría sin hallazgos altos ni críticos y licencia registrada | **Todas**, y la auditoría en verde | `mise run supply:check` y `mise run audit` |
| SEC-U6.8 | Inserción de HTML desde datos en componentes de la interfaz | **Exactamente 0** usos; el linter con sus reglas de seguridad y de React lo rechaza | `mise run lint` |
| SEC-U6.9 | Llamadas a proveedores o gasto desde las rutas de salud y del directorio del sitio | **Exactamente 0** | `mise run test:u6` (con los puertos de proveedor espiados) |
| NFR10.5 | Las dos tablas de activación tienen aislamiento forzado por aseguradora y su política, y cada una llega con su prueba de aislamiento | **100 %**; la aserción de esquema falla si alguna no la tiene | `mise run rls:check` y `mise run test:u6` |
| NFR11.7 | Columnas de texto libre o de dato personal en las tablas de activación | **Exactamente 0** | `mise run test:u6` (contra el catálogo vivo, con la lista versionada de columnas prohibidas que ya usa U5) |
| NFR19.3 | Avance de activación que sobrevive al reinicio nocturno | **Exactamente 0 filas**; el purgador de U6 está en el registro de la raíz de composición | `mise run test:u6` y la prueba de completitud del registro de purgadores de U2 |

## Lo que se decidió y por qué

**Sin scripts en línea, salvo uno con su huella.** El modo claro u oscuro tiene
que aplicarse antes del primer pintado (BR1.2), y eso exige un paso mínimo que
corra antes de la aplicación. En vez de abrir la política a cualquier script en
línea, ese paso se autoriza por su huella criptográfica: si alguien lo cambia, el
navegador lo rechaza hasta que la política se regenere en el mismo commit. El
valor exacto de la política lo fija NFR Design de esta unidad (ADR-002).

**Cero terceros, y comprobado.** Las fuentes se sirven desde el propio origen
(FD-U6-4) y no hay analítica ni CDN. El arnés registra cada petición del
recorrido, así que un tercero que entre sin que nadie lo decida hace fallar la
entrega en vez de pasar desapercibido.

**La salud cuenta lo necesario para el chequeo y nada más.** Lo que el chequeo
periódico necesita saber —si la base responde, cuántas aseguradoras cargaron,
qué superficies están de pie, qué commit corre— no es sensible. Los indicadores
de diagnóstico que U1 y U5 ya publicaban pasan como nombres de uso y un conteo
(FD-U6-6); ni una clave, ni una dirección, ni un identificador de cuenta.

**Las rutas públicas no necesitan límite propio.** La regla de `project.md` que
exige límites por sesión, origen y día aplica a las superficies que invocan al
modelo. Estas dos no lo invocan ni gastan (SEC-U6.9); lo que las protege del
tráfico abusivo es el hospedaje, que es del intent `infra`.

**Las tablas nuevas entran por la puerta que ya existe.** Aislamiento por
aseguradora con la aserción de U2, marca de dato de visitante en el avance y
purgador en el registro escrito a mano de la raíz de composición. No se inventa
un mecanismo nuevo para ninguna de las tres cosas.

## Cumplimiento

- La interfaz nunca afirma "cumple con" una norma; el chequeo de contenido de U1
  ya corre sobre el copy del producto.
- La línea base de accesibilidad es **inspirada en** WCAG 2.1 AA y así se nombra
  (US1.33); no se presenta como cumplimiento.
- El inicio declara que es una demostración con aseguradoras ficticias y pólizas
  de ejemplo, sin prometer lo que no existe (BR4.1, BR4.3).

## Sources

- `../functional-design/functional-spec.md` y `../functional-design/rules.md` —
  BR1.2, BR3.5, BR5.1, BR5.2, BR5.6, BR6.1, BR6.2, BR6.4, BR8.2 y FD-U6-4 a
  FD-U6-6.
- `../../../inception/contract-design/contract-summary.md` — C-01 (errores,
  cookies, aislamiento) y C-02 (salud).
- `../../../inception/domain-design/decisions.md` — ADR-002 (la política de
  contenido en NFR Design; scripts de instalación bloqueados).
- `../../../inception/requirements-analysis/requirements.md` — NFR10, NFR11 y
  NFR19.
- `aidlc/spaces/default/memory/project.md` — prohibiciones sobre superficies
  públicas, `tenant_id` literal y afirmaciones de cumplimiento.

## Assumptions & Open Questions

- **El valor de la política de contenido queda para NFR Design**, como fija
  ADR-002. Aquí se fija lo que no puede tener: scripts en línea sin huella ni
  evaluación de código.
- **La política de permisos y el micrófono.** U6 niega lo que el aplicativo no
  usa; el permiso del micrófono para la consola lo abre U16 cuando exista, en el
  mismo conjunto único de cabeceras y no con uno propio.
