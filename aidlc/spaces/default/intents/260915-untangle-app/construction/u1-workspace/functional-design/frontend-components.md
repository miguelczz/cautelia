# Interfaz — U1 `workspace`

**U1 no tiene pantallas.** Es la base del repositorio, el catálogo de textos y el
corredor de evaluaciones: todo lo que hace se ejecuta por comando o dentro del
proceso servido. Este documento existe porque la unidad no lleva tipo y por eso
recibe la matriz completa de diseño, y porque sí deja **una superficie que la
interfaz consumirá después**: el módulo tipado de claves del catálogo.

**Fuentes consumidas.** `../../../inception/units-generation/unit-of-work.md`
(U1 no contiene la base visual de la interfaz, que es de U6),
`../../../inception/units-generation/unit-of-work-story-map.md` (ninguna de sus
tres historias tiene pantalla),
`../../../inception/requirements-analysis/requirements.md` (FR11.3, el comando
único), `../../../inception/domain-design/components.md` (CopyCatalog aparece
como dependencia de WebClient, no como parte de él) y
`../../../inception/contract-design/contract-summary.md` (C-21, el catálogo, y
C-28, los artefactos generados).

## Lo que U1 entrega a la interfaz

| Superficie | Qué es | Quién la consume |
| --- | --- | --- |
| Módulo tipado de claves | Un módulo generado desde el mismo catálogo, con una clave por entrada | U6 y toda pantalla posterior |
| Lista de idiomas admitidos | Español e inglés, como valores cerrados | El selector de idioma de U6 |

**Cómo se genera.** El módulo se produce con un comando del archivo de tareas a
partir de los archivos del catálogo, y se versiona. El chequeo de deriva de
contratos (C-28) lo cubre: si el catálogo cambia y el módulo no se regenera en el
mismo commit, la compuerta falla.

**Qué gana la interfaz con eso.** Una clave que no existe deja de ser un texto
vacío en pantalla y pasa a ser un error de tipos antes de compilar. Es la mitad
de la comprobación de paridad que no puede hacer un chequeo de texto.

## Lo que no está aquí

- **Sistema de diseño, rutas, cliente de la API y páginas de estado:** son de U6
  `web-shell`.
- **Las pantallas de cada capacidad:** chat (U13), bandeja (U14), consola de voz
  (U16 y U17) y paneles (U22).
- **Las frases del catálogo:** cada unidad agrega las suyas cuando construye la
  conducta que las usa. U1 entrega el catálogo vacío con sus chequeos, no su
  contenido.

## Accesibilidad

No aplica en esta unidad: no hay superficie visible. El arnés de accesibilidad
que recorre cada pantalla visitable llega con U6.
