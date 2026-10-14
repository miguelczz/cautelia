# Requisitos de rendimiento — U1 `workspace`

U1 no atiende peticiones de personas: su rendimiento se mide en **cuánto tarda
alguien en llegar del repositorio a una cifra**. Aquí se registra NFR21, la meta
que Units Generation asignó a esta unidad, con el comando que produce su valor
real.

**Fuentes consumidas.** `../functional-design/functional-spec.md` (Flujo 1, el
comando único, y su paso 8), `../functional-design/rules.md` (BR1.1, BR1.2,
BR1.6, BR1.7 y BR1.8), `../../../inception/requirements-analysis/requirements.md`
(NFR17 y NFR21 con su valor esperado),
`../../../inception/contract-design/contract-summary.md` (C-27, el formato de los
casos y del reporte) y `../../../../codekb/untangle/technology-stack.md` (el
repositorio solo tiene la landing; el aplicativo se crea, no se verifica).

## Metas

| ID | Qué mide | Valor esperado | Cómo se mide | Quién la registra |
| --- | --- | --- | --- | --- |
| NFR21.1 | Tiempo de una persona desde clonar el repositorio hasta ver el reporte de evaluación, en máquina limpia | **Menos de 15 minutos** | Cronómetro humano, dos veces: Miguel y una persona voluntaria, cada uno en su máquina, con la imagen declarada en el README. **Es una medición humana, no un comando**, porque el criterio mide la experiencia de quien llega al repositorio | U1 |
| NFR21.2 | La misma secuencia, automatizada, en el flujo de integración continua sobre Linux | **Menos de 15 minutos**, y su duración se publica | Un trabajo del flujo que parte de un entorno limpio y mide su tiempo total. **Esta es la fila que alimenta la matriz de verificación de Build and Test**, porque produce un número sin intervención humana | U1 |
| NFR17.1 | Duración de la corrida de evaluación de texto | Se mide y se publica siempre, con o sin meta cumplida | El corredor la registra en la corrida y el reporte la muestra (BR1.8) | U1 mide; la **meta** de 10 minutos la registra U21 |

## Qué entra en los 15 minutos

Decisión Q2 de esta etapa: **todo lo que hace falta**, contado desde el clon.

1. Instalar las herramientas fijadas por el archivo de versiones.
2. Instalar las dependencias de los dos proyectos en modo reproducible.
3. Levantar los servicios locales que la corrida necesite.
4. Correr el comando único sobre el subconjunto declarado.
5. Ver el reporte.

**Sin clave de proveedor, y a propósito** (corrección del 2026-09-19). El
subconjunto de arranque solo lleva casos que **no llaman a ningún modelo**:
esquema del caso, aislamiento entre aseguradoras, paridad del catálogo de textos,
frases prohibidas, ausencia de texto de cláusula ajena. Quien clona ve un reporte
real en 15 minutos sin crear una cuenta en ningún proveedor.

Los casos de conversación, que sí necesitan clave, aparecen en ese mismo reporte
marcados **"no medido: sin clave de proveedor"** y se ejecutan en cuanto alguien
pone la suya. Es el mismo vocabulario que el proyecto usa para toda compuerta que
no se pudo ejecutar, y evita el fallo anterior: el camino medía a un visitante
que, tal como estaba especificado, se estrellaba con un error en el primer paso.
La meta mide a quien llega al repositorio, y quien llega al repositorio no tiene
clave.

**La consecuencia, dicha por adelantado:** la descarga de dependencias y de los
modelos de detección de datos personales entra en el cronómetro. Es lo que vive
quien llega al repositorio, que es a quien mide el criterio. Si la meta no se
alcanza, se publica el tiempo real con su causa; **el umbral no se baja**.

### Presupuesto por paso

Reparto objetivo de los 15 minutos, en una máquina limpia con caché fría. No es
una medición: es el presupuesto contra el que se compara la primera medición
real, y el que dice qué paso hay que atacar si no se cumple.

| Paso | Presupuesto | Qué lo mueve |
| --- | --- | --- |
| Instalar las herramientas del archivo de versiones | 2 min | Descarga de los dos runtimes |
| Dependencias de Python en modo reproducible | 3 min | Tamaño del árbol y caché del gestor |
| Dependencias de TypeScript en modo reproducible | 2 min | Igual |
| Modelos de detección de datos personales en los dos idiomas | 2 min | Descarga; es la pieza más pesada que no es código |
| Levantar la base de datos local y aplicar migraciones | 2 min | Descarga de la imagen la primera vez |
| Correr el subconjunto declarado y ver el reporte | 3 min | Número de casos del subconjunto |
| **Total** | **14 min** | Deja un minuto de margen sobre la meta |

**El camino de los 15 minutos no levanta el backend de trazas.** No hace falta:
BR1.3 ya exige que el reporte se genere igual con los enlaces marcados como no
disponibles. Quien quiera trazas las levanta después, fuera del cronómetro.

**Las dos palancas cuando no se cumple**, en este orden: reducir el subconjunto
declarado del arranque, y precargar en la imagen declarada lo que se pueda
precargar. Nunca bajar el umbral.

## Qué no mide esta unidad

- Las latencias del turno de voz y del chat: son de U16, U18 y U13.
- El costo por caso: es de U5.
- La meta de 10 minutos de la corrida de evaluación: la registra U21, aunque el
  corredor de U1 sea quien la mide.

## Restricciones de recursos

| Restricción | Valor | Por qué |
| --- | --- | --- |
| Minutos de integración continua | 2.000 al mes, con bloqueo al agotarse | Límite del plan privado; por eso el escaneo del historial completo corre por hito y no en cada corrida |
| Gasto de proveedor durante la corrida | El subconjunto declarado corre en el plan gratuito | La corrida de la compuerta no puede depender del presupuesto de la voz |
