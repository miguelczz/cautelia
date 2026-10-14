# Evidencia — `practices-discovery`

> **Integrado.** Registra qué inspeccionó cada participante, qué decidió Miguel
> en la entrevista, qué corrigieron los tres especialistas, y qué incertidumbre
> queda con su dueño. La separación entre "establece" y "sugiere" es deliberada:
> este repositorio tiene mucha documentación y casi ningún hecho de ingeniería,
> y confundir una cosa con la otra sería el error más fácil de cometer aquí.
>
> `phases/inception.md` prohíbe arrastrar contradicciones sin resolverlas. Por
> eso cada tensión detectada aparece abajo nombrada, y cada una lleva o su
> resolución o el nombre de quien la resuelve.

## Qué inspeccionó cada participante

**El lead (`aidlc-pipeline-deploy-agent`).** Evidencia del escaneo del
repositorio (`aidlc/spaces/default/codekb/untangle/`):
`code-quality-assessment.md` (línea base de pruebas, lint, CI, documentación y
deuda técnica TD-01 a TD-10), `technology-stack.md` (qué está decidido y qué es
hipótesis pendiente de ADR) y `dependencies.md` (manifiestos y herramientas
ausentes). Especificación y plan: `docs/specs/prd.md` Segmento 6 (principios P1
a P12), Segmento 8 (Must M1 a M20 y regla de corte), Segmento 9 (módulos MOD-01
a MOD-15 y multi-tenancy), Segmento 10 (umbrales publicables), Segmento 11
completo (datasets DS-1 a DS-8, criterios de calidad con sus compuertas duras,
QA de outputs, red-teaming RT-1 a RT-15, calendario), Segmento 12 (riesgos R1 a
R10 y mapa de fallos) y Segmento 13.1 (plan de los primeros 30 días);
`docs/PLAN-AIDLC.md` §2 (decisiones D-001 a D-017). Defaults del espacio:
`org.md`, `project.md`, `phases/inception.md` y `phases/construction.md`;
`team.md` está **vacío**, así que no hay práctica afirmada previa y esta no es
una re-corrida. Estado del repositorio, solo lectura: `git rev-parse HEAD`,
`git log`, `git status`, y el archivo de scope `.claude/scopes/aidlc-classic.md`
(`depth: Standard`, `skeleton: off`, `review_cap: advisory`).

**Calidad (`aidlc-quality-agent`).** Además del PRD, inspeccionó el **código del
propio framework** para comprobar qué llega realmente a Construcción:
`.claude/tools/aidlc-testing-posture.ts` (`buildPlanProfile`,
`combineTestObligations`, `structuredField`, `compatibleSpecialization`), el
contrato `## Testing Contract` de `code-generation-plan.md`, el inventario de la
`## Target Verification Matrix` de `build-and-test`, y el `aidlc-state.md`
(`Project Type`, `Test Strategy`, `Stages to Skip`). Tres de sus trece
posiciones tienen consecuencia mecánica demostrada, no opinión.

**Desarrollo (`aidlc-developer-agent`).** Inspeccionó el Segmento 9 del PRD
(módulos, features `F<módulo>.<n>`, multi-tenancy F9.1 a F9.6), los principios
P3, P4 y P12, la tabla de degradación de 12.3, el mapa FTCEM de 12.2, la deuda
TD-01 a TD-04 y TD-08 a TD-09 de la landing, y el árbol actual del repositorio
(`site/index.html` con 1.011 líneas de JavaScript en línea, 91 archivos `.ts` del
engine bajo `.claude/`). Aportó diez convenciones independientes del lenguaje.

**Seguridad de la cadena de entrega (`aidlc-devsecops-agent`).** Verificó contra
el repositorio actual la ausencia de `scripts/`, `.pre-commit-config.yaml` y
`.github/`; el contenido del `.gitignore`; las coincidencias reales de los dos
chequeos de contenido; y el precedente `site/PHOSPHOR-LICENSE.txt`. Marcó cada
recomendación **imprescindible** o **deseable**.

**Miguel.** Respondió las ocho preguntas en
`practices-discovery-questions.md`, en modo `Guide me`, con cuatro respuestas
que se apartan de la recomendación (Q1, Q2, Q5, Q7) y cuatro que la aceptan
(Q3, Q4, Q6, Q8).

## Lo que la evidencia establece

**La línea base de prácticas es cero, y no es una opinión.** Cero pruebas
automatizadas (búsqueda de `tests/`, `spec/`, `evals/`, `*.test.*`, `test_*.py`:
sin resultados), cero linters y formatters, cero CI, cero manifiestos y
lockfiles, sin README. Nueve commits directos a `main`, sin ramas, sin pull
requests, sin tags. La landing se publica a mano con la CLI de Vercel desde
`site/`.

**No hay código de aplicación del que inferir prácticas.** Lo único ejecutable
es `site/index.html`, fuera del alcance del aplicativo por D-005 y D-013. Su
consistencia de estilo viene de la disciplina del autor, no de una herramienta,
así que no es una práctica reproducible ni un estándar heredable. El escaneo del
engine lee `Languages: JavaScript`, que es una propiedad de la landing y no del
aplicativo (TD-08).

**El PRD ya obliga a un régimen de pruebas más exigente que el default**, y está
escrito y aprobado: golden sets en cada cambio con la regresión bloqueando (P5,
M8); compuertas duras de pasa o falla donde un solo fallo detiene la entrega
(PRD 11.2); tests unitarios del motor de reglas (M5); tests de aislamiento entre
tenants (M9); redacción de PII probada en cada punto de salida (M6, RT-14).

**El lenguaje del aplicativo no está decidido.** `technology-stack.md` lo marca
como hipótesis pendiente de un ADR de `domain-design`, y el `.gitignore`
anticipa Python y Node a la vez.

**El presupuesto y el equipo son restricciones duras, no contexto.** D-015 fija
5 USD en 90 días con alerta en 3; D-017 el repositorio privado bajo `miguelczz`;
el Segmento 13 asigna todo el calendario a una sola persona.

**Cuatro hechos mecánicos del framework, verificados en su código por el
especialista de calidad**, que cambian lo que hay que escribir:

1. Con `- **Methodology**: custom`, el resolutor **no expande capas**: emite dos
   pasos y el primero es la cadena literal del campo `- **Ordering**:`. La frase
   de `Ordering` **es** el plan de pruebas completo que recibe Code Generation.
2. Ese campo se parsea sobre **una sola línea**. Convertirlo en viñetas perdería
   todo menos la primera y no daría error visible.
3. El scope `classic` **no está** en la lista que activa el piso del 80 % en el
   contrato determinista (`mvp`, `enterprise`, `feature`, `infra`); cae en el
   `else` que emite "no extra new-test floor". El piso solo sobrevive si se
   escribe como obligación propia.
4. `Project Type: Brownfield` hace que cada unit reciba el paso "verifica el
   runner existente", y no existe ninguno.

## Las decisiones de la entrevista

**Q1 — Way of Working: commit directo a `main`.** Miguel respondió fuera de las
opciones, en la dirección de `C.`, con una precisión: *"Aunque es verdad, que
trabajo solo vamos a hacer uso de GitHub actions, por lo mismo con el tema del
CI/CD, este será las pruebas para los tests .Así usaremos la subida de código
directa a la rama Main"*. Consecuencia registrada y escrita en la práctica: la
compuerta corre después de que el cambio aterrizó, así que un `main` en rojo es
un incidente con prioridad de arreglo.

**Q2 — Walking Skeleton: no al esqueleto delgado.** También fuera de las
opciones: *"No la gracia de que tengamos una base construida la cual sea solida.
Después de eso haremos la creación de componente Uno A uno para mí eso es lo más
indicado en lugar de dejar un componente a medias es que después nos puede
quedar mal construir"*. Lectura registrada: base sólida y terminada primero,
después componentes uno a uno, ninguno a medias. Es un recorrido **por
componente**, no por etapa, y es insumo directo de `delivery-planning`.

**Q3 — Testing Posture: `A`**, que se escribe `custom`. El caso del conjunto de
evaluación se escribe antes de implementar el comportamiento que mide; las
pruebas unitarias del código determinista se escriben junto con su capa, después
de implementarla.

**Q4 — Cobertura: `A`.** 80 % agregado más piso del 80 % en las piezas críticas;
interfaz y adaptadores de proveedor pueden quedar por debajo mientras el
agregado se cumpla.

**Q5 — Deployment: `B`.** Chat web, bandeja de demostración **y** enlace en vivo
de la voz con límite por visitante. Se le explicó el punto completo antes de
decidir. Condiciones afirmadas como parte de la práctica: límite duro por
visitante y por día configurado también en el proveedor; techo mensual con corte
automático y modo degradado que deja vivo el chat; alerta antes del techo; misma
condición de publicación que el chat.

**Q6 — Code Style: `A`.** Afirmar la obligación sin la herramienta, y fijar hoy
las convenciones que no dependen del lenguaje.

**Q7 — Controles: `C`.** Confiar solo en GitHub Actions; sin gancho previo al
commit ni obligación de correr el guion en local. Se le presentó explícitamente
la consecuencia sobre el historial y aun así eligió `C`, así que es su decisión
y se registra como tal.

**Q8 — Regresión: `A`.** Contar casos en los conjuntos pequeños (cualquier caso
que pase a fallar bloquea y exige explicación escrita; el umbral de 2 puntos se
reserva para métricas de denominador grande), más una salida escrita para causas
externas: se registra la causa, se marca la corrida como no comparable y no se
toca el umbral.

## Contradicciones detectadas y su resolución

1. **`org.md` pide rama corta con pull request; Q1 afirma commit directo.**
   Resuelta por afirmación explícita del equipo, que es exactamente lo que esta
   etapa existe para capturar. Sigue siendo desarrollo sobre tronco único, en su
   variante sin rama intermedia, y no introduce ramas de vida larga. En el menú
   de `branching-strategies.md` el ajuste más cercano es **Trunk-Based
   Development**, cuyo mapeo de worktree (`--base main --target main --strategy
   squash`) se conserva sin cambios para los Bolts de Construcción; la
   desviación es que no hay pull request.
2. **El PRD exige camino completo en texto antes de la voz (R1, línea base v0 de
   la semana 3); Q2 rechaza el esqueleto delgado de punta a punta.** Resuelta: el
   desacuerdo es sobre lo **delgado**, no sobre el orden. La base que Miguel pide
   es terminada, no mínima, y la voz es un componente tardío en cualquier orden
   razonable, así que el texto sigue llegando antes que la voz. Queda como
   restricción explícita sobre `delivery-planning`: la secuencia de componentes
   debe completar el camino de texto antes de abrir la voz.
3. **Enlace en vivo de la voz (`C5`, "podría") contra el tope de 5 USD (D-015,
   M20).** **No se resuelve aquí.** Dueño: `requirements-analysis` (2.3), que
   debe reconciliarlo con el PRD y decidir explícitamente si el tope sube o si el
   límite por visitante se calibra para caber en los 5 USD. Esta etapa afirma la
   condición de publicación; la regla dura que impide publicar el enlace antes de
   esa reconciliación queda escrita en `## Forbidden`.
4. **D-014 manda CI al intent `infra`; Q1 introduce GitHub Actions ahora.**
   Resuelta por reparto: el **flujo de verificación** (pruebas, compuertas,
   escaneo de secretos, auditoría de dependencias) nace en este intent junto al
   primer código; la **tubería de despliegue**, el aprovisionamiento de entornos
   y la observabilidad de plataforma siguen en `infra`, que invoca el mismo guion
   en vez de crear un segundo juego de chequeos.
5. **F8.7 publica credenciales de demostración por tenant, contra la regla de
   secretos.** Resuelta nombrando la excepción con sus límites: son por tenant,
   no sirven fuera de él, no se reutilizan, y se rotan en el reinicio nocturno.
6. **`classic` no activa el piso del 80 % en el contrato determinista, pero
   `org.md` lo nombra en prosa.** Resuelta escribiéndolo como obligación propia
   del equipo, con su comando y su lista de exclusión versionada, en lugar de
   citarlo.
7. **`Project Type: Brownfield` contra la ausencia total de runner.** Resuelta
   sin tocar el `Project Type` (se fijó en `reverse-engineering` y ya está
   aprobado): se compensa con una declaración explícita de arranque desde cero en
   la prosa de `## Testing Posture` —el canal que sí llega al generador— y con la
   última cláusula del campo `- **Ordering**:`.
8. **Los dos chequeos de contenido arrancaban en rojo.** Verificado por el
   especialista de seguridad: el de frases prohibidas coincide hoy con cinco
   archivos legítimos (incluido el PRD que define la prohibición) y el de
   ISO/ACORD con diecisiete. Resuelta dándoles alcance de rutas (lo que se
   publica), lista de exclusiones versionada con razón por entrada, y la
   distinción entre estructura documentada y texto de cláusula.
9. **Inconsistencia interna del borrador del turno 1**: `team-practices.md` decía
   "mismo Bolt" y `discovered-rules.md` "primer commit" para el mismo andamiaje.
   Resuelta alineando ambos en el **mismo commit** que introduce el primer
   archivo de código del aplicativo.
10. **Frontera entre calidad y seguridad sobre los chequeos de contenido**
    (casos de prueba con identificador estable frente a reglas de linter).
    Resuelta sin sacrificar ninguna de las dos: viven como pasos del guion único
    de verificación, con identificador estable, y aparecen en el reporte por caso
    y en el diff contra la línea base.
11. **`.gitignore` ignora `.env.*`, lo que bloquea la plantilla que el README
    necesita.** Resuelta: se añade la negación `!.env.example`, y la plantilla
    lista nombres de variables, nunca valores.

## Incertidumbre que queda

Tres piezas no se cierran en esta etapa. Ninguna bloquea la promoción de las
prácticas; las tres tienen dueño.

**1. El alcance del enlace en vivo de la voz contra el tope de 5 USD.**
Dueño: `requirements-analysis` (2.3). Qué falta decidir: si el tope sube (D-016
ya contempla revisarlo) o si el límite por visitante se calibra para caber en los
5 USD, y si `C5` se promueve formalmente en el PRD. Mientras tanto rige la regla
`NEVER` que impide publicar el enlace. Lo que **sí** está cerrado y no vuelve a
abrirse: las condiciones de publicación (límite por visitante y por día también
en el proveedor, techo con corte automático, modo degradado que deja vivo el
chat, alerta antes del techo, compuertas duras en verde y checklist del segundo
día).

**2. El riesgo residual de confiar solo en la tubería (Q7).** Es una decisión
tomada con la consecuencia a la vista, y no se reabre. El riesgo que queda
escrito: un fallo entra a `main` antes de que nada lo revise, y **un secreto
commiteado permanece en el historial aunque se borre después**, con D-017
contemplando hacer público el repositorio en la semana 12. Las mitigaciones
afirmadas, todas compatibles con `C`: el escaneo de secretos es el primer trabajo
del flujo; se activa la protección de inserción del propio GitHub si está
disponible, que rechaza el envío en el servidor sin depender de nada local; toda
clave detectada se rota en el proveedor; y el guion único de verificación se
escribe igual, porque es lo que el flujo invoca. Dueño de la revisión: Miguel,
en la decisión de publicar de la semana 12, que es cuando el riesgo se
materializa o se descarta.

**3. La dependencia con el ADR de lenguaje.** Dueño: `domain-design`.
`## Code Style` queda aplicable solo si ese ADR fija, en la misma decisión,
**versión del runtime** (hoy no hay `.nvmrc` ni `.python-version`), **gestor de
dependencias y formato del lockfile**, y **comprobador de tipos** —porque el
conjunto de escritura por nodo y la taxonomía cerrada de errores presuponen que
hay tipos que alguien comprueba. Si el ADR no los trae, esta sección queda
bloqueada un segundo turno. Lo que **no** depende del ADR y ya está afirmado:
las diez convenciones independientes del lenguaje.

**Consecuencia registrada de elegir `custom`.** `compatibleSpecialization`
compara la capa `team` contra la capa `project`: con `custom` en `team.md`,
cualquier `## Testing Posture` que en el futuro se escriba en `project.md` y no
sea también `custom` lanza un error duro (`Testing Posture conflict`) y detiene
la resolución. Nadie debería añadir una especialización de proyecto sin saberlo.

**Deuda de seguridad de proceso, para que quede trazada.**
`code-quality-assessment.md` registra TD-01 a TD-10 y ninguna es de seguridad de
proceso. La ausencia de escaneo de secretos, de auditoría de dependencias y de
registro de licencias, en un repositorio que en la semana 12 puede volverse
público, es deuda de severidad alta para Construcción, con el mismo rango que
TD-09. Las tres quedan cubiertas por reglas de `## Mandated`; se nombra aquí para
que la trazabilidad no dependa de recordarlo.

## Assumptions & Open Questions

Supuestos que quedan vivos tras la integración, cada uno revocable:

- Supuse que la secuencia de componentes de Q2 mantiene la voz al final y por
  tanto no rompe la mitigación de R1. Si `delivery-planning` propusiera abrir la
  voz antes de cerrar el camino de texto, esta práctica hay que revisarla, no
  ignorarla.
- Supuse que el worktree de Construcción sigue siendo válido bajo commit directo,
  porque es un dispositivo mecánico de aislamiento y no una rama de revisión. Si
  el equipo prefiere que los Bolts commiteen directo sobre `main` sin worktree,
  es un ajuste del mapeo, no de la práctica.
- Supuse que las claves de proveedor van separadas por uso (voz, chat, evals);
  el PRD lo menciona como mitigación de cuota, no como regla, y aquí se eleva a
  regla dura con tope propio en el proveedor.
- Supuse que la landing no entra en ninguna práctica del aplicativo, ni en
  cobertura ni en estilo ni en pipeline, más allá del mínimo automatizable de
  TD-06.
- Supuse que los chequeos de contenido rinden como pasos del guion de
  verificación con identificador estable, y no como reglas de linter sin caso ni
  historia. La mecánica concreta puede cambiar; el identificador y su presencia
  en el reporte, no.
- Adopté las recomendaciones **deseables** del especialista de seguridad que son
  casi gratuitas y protegen una compuerta dura (regenerar y comparar el corpus
  sembrado, escanear el corpus antes de ingerirlo, DS-6 contra el despliegue
  vivo por hito, justificación de una línea por dependencia nueva). Descarté las
  que imponen un programa que este equipo no puede pagar: SAST comercial, DAST
  automatizado, SBOM firmado, atestación de procedencia, firma de commits y
  modelado STRIDE formal, porque el PRD ya contiene el modelado útil en RT-1 a
  RT-15.
