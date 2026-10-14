# Correcciones tras la revisión — U2 `tenancy`, diseño de calidad

La revisión asesora devolvió `READY` con dos hallazgos `Major`, los dos
correctos. Se aplican aquí porque `security-design.md` y
`logical-components.md` quedan congelados en cuanto se registra el recibo de la
revisión; este archivo no es artefacto declarado de la etapa, así que no altera
lo que la revisión certificó.

Regla permanente que Miguel fijó el 2026-09-20: cuando un hallazgo sea
corrección de hecho sin decisión de por medio, se aplica y se reporta.

## R-01 — A SEC-U2.5 le faltaba un comando

La tabla "Cómo se comprueba cada control" de `security-design.md` mapea
`SEC-U2.5` solo a `mise run test:u2`. El documento autoritativo,
`../nfr-requirements/security-requirements.md`, exige **dos** comandos para ese
control: `mise run test:u2` **y** `mise run env:check`.

**Rige:** `SEC-U2.5` se comprueba con los dos. Cada uno mide una mitad distinta:

| Comando | Qué demuestra |
| --- | --- |
| `mise run env:check` | Que existen las **dos** variables de entorno declaradas, y que el código lee exactamente esas |
| `mise run test:u2` | Que una clave **no valida** lo firmado por la otra, que es lo único que prueba que están separadas de verdad |

Declarar dos variables sin probar el rechazo cruzado sería otra vez un control
escrito y no vivo.

## R-02 — El contrato de importación no alcanza a las reglas internas

`logical-components.md` afirma que sus tres reglas de dirección son
"comprobables por el contrato de importación". Es cierto solo de la tercera (que
nadie fuera del módulo importe una pieza interna), que es la que describe
`SEC-U2.2`. Las dos primeras hablan de dependencias **entre las seis piezas
dentro de** `tenancy`, y el mecanismo descrito no las cubre.

**Rige:** las reglas internas necesitan su propio contrato de capas, y U2 lo
crea. `app/backend/.importlinter` gana un contrato de tipo capas para el módulo,
con este orden —cada capa solo puede importar las de abajo—:

```
tenancy.api
tenancy.staff_identity | tenancy.visitor_access | tenancy.purge | tenancy.rls_assertion
tenancy.session
tenancy.config
```

Las tres reglas quedan así comprobadas por herramienta:

1. **El cargador no depende de nada del módulo** — es la capa más baja.
2. **Todo lo que toca la base pasa por la sesión** — ninguna pieza del nivel
   intermedio puede importar el cliente de base de datos, porque ese import solo
   está permitido en `tenancy.session`; se declara además como módulo prohibido
   para el resto.
3. **Solo la superficie pública sale del módulo** — el contrato que ya existe
   desde U1 para las fronteras entre módulos.

Sin ese contrato, "Identidad del personal" podría importar el cliente de base de
datos directamente y nada lo diría: exactamente el tipo de regla que sobrevive
en la memoria del autor y no llega a la semana seis.

## Qué tiene que hacer la generación de código de U2

Tomar este archivo como autoritativo donde contradiga a los dos documentos
congelados: comprobar `SEC-U2.5` con los dos comandos, y añadir el contrato de
capas interno a `app/backend/.importlinter` con las cuatro capas de arriba.
