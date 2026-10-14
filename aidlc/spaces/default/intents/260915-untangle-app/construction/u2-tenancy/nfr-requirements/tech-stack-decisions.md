# Decisiones de stack — U2 `tenancy`

Qué herramientas añade esta unidad y por qué. Las elecciones grandes ya están
tomadas en los ADR de Domain Design y U1 instaló el andamiaje; aquí solo se
registra **lo que U2 añade encima**, que es todo lo relacionado con la base de
datos, porque U1 decidió a propósito no crear ninguna tabla (CG-1).

**Fuentes consumidas.** `../functional-design/functional-spec.md` (los siete
flujos, y en particular el punto único de sesión y la aserción),
`../functional-design/rules.md` (BR1.1, BR1.2, BR1.7, BR1.10, BR1.11 y BR2.1),
`../../../inception/requirements-analysis/requirements.md` (NFR18),
`../../../inception/contract-design/contract-summary.md` (C-10, C-25, C-30) y
`../../../../codekb/untangle/technology-stack.md`.

## Lo que U2 añade

| Pieza | Qué se fija | De dónde viene |
| --- | --- | --- |
| Acceso a la base de datos | El cliente asíncrono de PostgreSQL y el mapeador que ya fija ADR-002; U2 lo envuelve en el punto único de sesión y nadie más lo toca | ADR-002, C-10 |
| Migraciones | Alembic, una sola historia lineal, con SQL explícito para lo que el mapeador no modela: habilitar el aislamiento, forzarlo y declarar la política | ADR-002, C-30 |
| Base efímera para pruebas | Contenedor con la misma imagen anclada por huella que ya usa el entorno local, levantado y destruido por la suite, con el **rol del aplicativo** y no con el superusuario | BR1.7 |
| Firma de la credencial de bandeja | **PyJWT**. El tutorial de seguridad de la documentación oficial de FastAPI instala `pyjwt` e importa `jwt`; es el camino documentado del ecosistema y el que reconoce quien evalúe el repositorio | Decisión Q4 |
| Firma del enlace de caso | Biblioteca estándar. El token no lo interpreta nadie externo y su fila se busca por el resumen del token, así que un formato estándar añadiría carga útil y superficie sin comprar nada | Decisión Q4 |
| Esquema de la configuración por aseguradora | JSON Schema, con la validación en el guion de verificación, igual que el resto de archivos versionados del proyecto | CD-4, C-25 |

**Dependencias nuevas de tiempo de ejecución**, cada una con su línea de
justificación, como pide la práctica del equipo:

| Dependencia | Qué hace | Por qué no la biblioteca estándar | Licencia |
| --- | --- | --- | --- |
| `pyjwt` | Codifica y verifica la credencial firmada de la bandeja | La biblioteca estándar no trae JWT; escribirlo a mano es exactamente el tipo de criptografía casera que no se hace | MIT |

El enlace de caso **no** añade dependencia: se firma con `hmac` y `secrets` de la
biblioteca estándar, y su token se compara en tiempo constante.

## Lo que U2 no cambia

- **Ninguna versión anclada por U1 se mueve.** Python, Node y sus gestores
  siguen donde U1 los dejó.
- **El guion de verificación no crece de lista**, crece de pasos dentro de los
  que ya existen: la aserción de aislamiento y la comprobación de migraciones
  entran en el paso de aserciones de esquema, que ya está.
- **El piso de cobertura no se toca.** Lo que cambia es que a partir de U2 hay un
  módulo crítico que medir aparte (NFR18.2), y eso es una fila más en el
  comando, no un umbral distinto.

## Lo que queda anotado para las unidades siguientes

La elección del mecanismo de aislamiento para las tablas de puntos de control
del grafo la hace U12, entre un pool por aseguradora y un almacén propio con
transacción. En los dos casos con columna de aseguradora, aislamiento habilitado
y forzado, así que la aserción de U2 las cubrirá sin cambiar de forma.
