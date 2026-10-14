# Hallazgos de la tanda 1 — U14 `inbox`

## 1. DS-8 declaraba una colisión que el esquema del caso no admite — RESUELTO

**Qué pasa.** `app/data/fixtures/ds8_isolation.json` declara el **mismo identificador
de caso** (`CASE-7F3A21`) en dos aseguradoras, a propósito: es lo que hace que una
prueba de aislamiento signifique algo. `case_record` no lo admite, porque su llave
primaria es `case_id` a secas. Sembrar la segunda fila choca contra `case_record_pkey`.

**Por qué nadie lo había visto.** Ningún código había sembrado nunca las filas `cases`
de DS-8. Las pruebas de aislamiento de U2 usan las de enlaces firmados y claves de
navegador, que nombran el caso como texto y no apuntan a `case_record` con llave
foránea. U14 es la primera unidad que intenta usarlas como casos.

**Las dos cosas están aprobadas y se contradicen.** DS-8 dice que el identificador
colisiona; el esquema de U4 dice que es único en toda la base. Una de las dos está mal.

**Qué se hizo mientras tanto.** La prueba de la compuerta dura siembra el identificador
compartido en la primera aseguradora y, en la segunda, el mismo prefijado por su
aseguradora —una sustitución **visible**, escrita en el `conftest`, no un dato inventado
en silencio—. El número de póliza, que sí colisiona y sí cabe, se conserva tal cual. La
prueba no se debilita: las dos filas viven en la misma tabla, así que a una consulta a
la que le faltara el filtro por aseguradora se le caería igual.

**Las dos salidas, para decidir.**

1. **Llave compuesta en `case_record`**: `(tenant_id, case_id)`. DS-8 se puede sembrar
   literalmente y el identificador de caso deja de ser un espacio de nombres compartido
   entre aseguradoras. Toca la tabla central y las llaves primarias de sus hijas
   (`case_field` es `(case_id, field_key)`), en U4, U5, U10, U12 y U13. Las llaves
   foráneas ya son compuestas desde `u10_compliance_0002_tenant_fks`, así que esa mitad
   está hecha.
2. **Corregir DS-8**: si el identificador de caso es global por diseño, la fila que lo
   repite describe algo imposible y se quita, dejando las colisiones que sí lo son
   —número de póliza y nombre del asegurado—, con su razón escrita.

Es una decisión de Miguel porque cambia un diseño aprobado, no una elección técnica
libre.

**Decisión de Miguel, 2026-09-28: opción B.** Manda el esquema. Aplicado así:

- La fila de la segunda emisora **conserva su sitio** y lleva su propio identificador
  (`CASE-7F3A22`), en vez de desaparecer: sigue colisionando en número de póliza y en
  nombre del asegurado, que es lo que hace que la prueba de aislamiento sobre casos
  signifique algo, y borrarla habría dejado a la segunda aseguradora sin ningún caso.
  Lo que se quitó es lo imposible —el identificador repetido—, no la fila.
- La colisión del identificador **sigue declarada, con su alcance**: vive sobre
  `case_access_link`, que nombra el caso como texto y no tiene llave foránea, y es
  donde U2 la ejercita y donde RT-4 la ataca.
- La razón entera quedó escrita en `synthetic_data/ds8.py`, y la cifra que fija el
  contenido de DS-8 se actualizó con la suya al lado, nombrando la versión anterior.
- El `conftest` de U14 ya no sustituye ningún identificador: siembra las filas tal
  como están. Rota la comparación de la credencial, se siguen cayendo las mismas tres
  pruebas.

## 2. La línea que parece imponer el aislamiento no es la que lo impone

Romper `credencial.tenant_id` → identificador de la dirección no tumbó ninguna prueba:
llegados ahí los dos valen lo mismo, porque la comparación de `verify_credential` ya
rechazó. Desactivar esa comparación tumba tres. Queda escrito junto al código, en el
docstring de `inbox/api.py`, y la lección general en
`docs/reference/como-se-revisa-el-codigo.md` como quinta regla sobre quien revisa.

## 3. Un criterio leído al revés, encontrado releyendo el diseño

La cola se escribió mostrando los casos abiertos y escondiendo los cerrados. La tabla
del diseño funcional dice exactamente lo contrario: `open` y `capturing` no aparecen
—el caso sigue en conversación— y `closed` sí. Corregido, con prueba que lo fija por
las dos mitades: ni sin filtro ni pidiéndolo por su nombre.

## 4. Una excepción de linter, acotada y escrita

Desde que la cola trae cursor, el generador del cliente produce ayudantes de paginación
infinita con `@ts-ignore`. La regla `@typescript-eslint/ban-ts-comment` queda apagada
**solo** en `src/shared/api/**`, que es código generado y comprobado contra deriva, con
la razón escrita al lado en `eslint.config.ts`. Ninguna otra regla, umbral ni piso se
tocó.
