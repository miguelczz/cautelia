# Correcciones tras la revisión — U2 `tenancy`, requisitos de calidad

La revisión asesora de esta etapa devolvió `NOT-READY` con tres hallazgos, los
tres correctos y los tres errores de quien escribió los artefactos. Miguel
instruyó el 2026-09-20: **"Aplica las tres correcciones"**.

**Por qué están aquí y no dentro de los documentos.** `security-requirements.md`
y `tech-stack-decisions.md` quedaron congelados en cuanto se registró el recibo
de la revisión: el framework impide editarlos para que la revisión siga
cubriendo exactamente los bytes que certificó. Las dos vías de desbloqueo que
ofrece no aplican aquí: pedir cambios exige una etapa activa, y bajo iteración
por unidad esta figura como pendiente; y reiniciar la etapa exige un salto que
marcaría `functional-design` como saltada para las veintiuna unidades restantes.
Cambiar tres frases no justifica ese riesgo.

Este archivo **no es uno de los artefactos declarados de la etapa**: no altera lo
revisado, y es lo que leen la generación de código de U2 y cualquiera que abra
esta carpeta. Es el mismo patrón que se usó con SEC-U1.4 en U1, donde la
corrección quedó en el resumen de la etapa en curso.

## Lo que rige, por encima de lo que dicen los documentos congelados

### R-01 — Los comandos que producen el valor real

Tres controles citaban `mise run rls:check` y `mise run migrate:check`, que **no
existen** en el archivo de tareas, mientras `tech-stack-decisions.md` afirmaba
que esta unidad no añade tareas. Las dos cosas no podían ser ciertas a la vez.

**Rige:** U2 **sí añade tres tareas** al archivo de tareas de la raíz. Lo que no
crece es el guion de verificación: sigue teniendo nueve pasos, y las tres nuevas
se invocan desde el paso 6, que ya agrupa `schema:check`, `contracts:check`,
`env:check` y `supply:check`.

| Tarea nueva | Qué hace | Controles que la usan |
| --- | --- | --- |
| `rls:check` | Pregunta al catálogo vivo de la base qué tablas hay y exige de cada una aislamiento habilitado, forzado y política; comprueba además que el rol vivo de la conexión no puede saltarse las políticas | SEC-U2.1, SEC-U2.4 |
| `migrate:check` | Sube, baja y vuelve a subir contra una base efímera con el rol del aplicativo; falla ante dos cabezas o ante una revisión que crea una tabla sin su aislamiento | SEC-U2.12 |
| `tenancy:literals` | Busca identificadores de aseguradora literales fuera del cargador de configuración y de las fixtures | SEC-U2.14 |

La frase de `tech-stack-decisions.md` que dice "el guion de verificación no crece
de lista, crece de pasos dentro de los que ya existen" es correcta en su
segunda mitad y engañosa en la primera: **el archivo de tareas gana tres
entradas**, aunque el guion siga teniendo nueve pasos.

### R-02 — NFR12 no es de esta unidad

`NFR12.1` atribuía a U2 parte de NFR12 (resistencia adversarial). No hay
respaldo: US4.11 declara `Realiza: FR9.1, FR9.2, FR9.4, NFR10` y US5.7 declara
`Realiza: FR9.4`; ninguna nombra NFR12. Y el enunciado de NFR12 mide que ninguna
respuesta obedezca una instrucción inyectada, que es trabajo de U10 y U21.

**Rige:** `NFR12` queda **fuera del alcance de U2** y `NFR12.1` **no existe**. La
verificación de RT-4 contra el despliegue vivo ya la cubre `NFR10.3`, que medía
exactamente lo mismo. Los objetivos medibles de U2 son cinco, no seis:

| ID | Objetivo | Valor esperado | Comando |
| --- | --- | --- | --- |
| NFR10.1 | Filas de otra aseguradora en una consulta sin filtro | Exactamente 0 | `mise run test:u2` |
| NFR10.2 | Pruebas de aislamiento en verde | 100 % | `mise run test:u2` |
| NFR10.3 | Casos o pólizas ajenas por RT-4 contra el despliegue vivo, por idioma | 0 en español y 0 en inglés | `mise run evals:run -- --subset rt4-live` |
| NFR18.2 | Cobertura del módulo de aislamiento | Mayor o igual a 80 % | `mise run cov` |
| NFR19.1 | Enlaces y claves de navegador que sobreviven al reinicio | Exactamente 0 | `mise run test:u2` |

En `traceability.json`, `NFR12` debe leerse como no aplicable a esta unidad, con
esta razón.

### R-03 — SEC-U2.14 sin comando

Era el único control cuya comprobación decía "chequeo del guion de verificación"
sin nombrar nada ejecutable.

**Rige:** su comando es `mise run tenancy:literals`, la tercera tarea de la tabla
de R-01.

## Qué tiene que hacer la generación de código de U2

Tomar este archivo como autoritativo donde contradiga a los dos documentos
congelados: crear las tres tareas con esos nombres exactos, invocarlas desde el
paso 6 del guion, y no construir nada para `NFR12.1`.
