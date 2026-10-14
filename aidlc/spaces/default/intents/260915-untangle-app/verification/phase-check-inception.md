# Verificación de frontera: Incepción → Construcción

**Veredicto: PASA.** Ningún hallazgo abierto. Las tres etapas de Incepción que
producen trazabilidad la tienen completa, sin huecos (`GAP`) ni elementos
huérfanos (`ORPHAN`), y los elementos marcados `N/A` o `Deferred` llevan su
justificación y su destino.

Fecha: 2026-09-18. Etapa que la ejecuta: `delivery-planning` (2.9), como paso 5
de su protocolo.

## Qué se revisó

| Etapa | Archivo | Elementos hacia adelante | Elementos hacia atrás |
| --- | --- | --- | --- |
| User Stories (2.4) | `inception/user-stories/traceability.json` | 118 `OK`, 1 `Deferred` | 10 `N/A` |
| Domain Design (2.6) | `inception/domain-design/traceability.json` | 85 `OK`, 2 `N/A` | — |
| Units Generation (2.7) | `inception/units-generation/traceability.json` | 85 `OK`, 2 `N/A` | — |

Contract Design (2.8) no produce trazabilidad: es dueña de los contratos
formales, no de la cobertura de requisitos, así que no entra en esta
comprobación.

## Cobertura

- **Requisitos a historias:** los 119 elementos de requisitos que User Stories
  rastrea tienen historia, salvo NFR18 (piso de cobertura del 80 %), marcado
  `Deferred` con su destino escrito: se registra como objetivo medible en
  `nfr-requirements` de U1 y se verifica en Build and Test. No es una conducta
  observable por un perfil de usuario, así que no podía ser historia.
- **Historias a componentes:** las 87 historias tienen componente, salvo dos
  marcadas `N/A` con su razón: US4.2 (video) y US4.3 (landing) son entregables
  de MOD-15 y no software en ejecución.
- **Historias a unidades:** las mismas 85 tienen unidad, y las mismas dos siguen
  `N/A`. Los destinos de esas dos filas prometían que se planificarían en
  Delivery Planning, y así ocurrió: están en la tabla "Lo que no es un Bolt" de
  `inception/delivery-planning/bolt-plan.md`, con su semana.
- **Historias sin requisito propio:** diez historias vienen de un principio, de
  la guía de voz o de un escenario de red-team en vez de un requisito
  funcional; cada una declara su origen. No son huérfanas: tienen procedencia
  escrita.

## Contradicciones entre etapas

No se encontró ninguna. Las enmiendas del 2026-09-17 a Domain Design y Units
Generation se revisaron de forma independiente antes de Contract Design y
quedaron sin hallazgos abiertos; Contract Design pasó su segunda revisión sin
hallazgos nuevos.

## Lo que queda abierto y no bloquea

Trece preguntas que Incepción deja escritas con su dueño y su etapa de
resolución: PA-2 a PA-13 en `unit-of-work.md` y OQ4 en `requirements.md`, más las
diez preguntas abiertas de contrato en `contract-summary.md`. Ninguna es un hueco
de trazabilidad: todas tienen destino declarado en Construcción o en el intent
`infra`.

## Aprobación

- [x] Revisado y consolidado por la etapa `delivery-planning`.
- [ ] Aprobado por Miguel en la compuerta de `delivery-planning`.
