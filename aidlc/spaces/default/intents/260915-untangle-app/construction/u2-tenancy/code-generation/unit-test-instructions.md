# Instrucciones de prueba — U2 `tenancy`

Cómo se prueba esta unidad, con qué comandos exactos y contra qué metas. Todos
los comandos están **acotados a U2**: `build-and-test` ejecuta los de cada
unidad, y un comando que corriera la suite entera la repetiría veintidós veces.

## El comando de esta unidad

```bash
uv run --project app/backend pytest app/backend/tests/unit/tenancy app/backend/tests/integration/u2 -q
```

Queda además nombrado en el archivo de tareas de la raíz como `test:u2`, igual
que `test:u1`, porque la tubería invoca comandos nombrados y no mantiene su
propia lista.

**Antes del primer caso** hay que comprobar que ese comando es ejecutable. U1
dejó instalados el runner, la configuración de cobertura y el corredor de
evaluaciones; el contrato de pruebas exige verificarlo, no darlo por hecho.

## Qué necesita una base de datos y qué no

| Comando | Base | Qué levanta |
| --- | --- | --- |
| `mise run test:u2` | Sí | **Una sola** base efímera por corrida de la suite, compartida por todas las pruebas de la unidad |
| `mise run rls:check` | Sí | Reutiliza la de la suite dentro de ella; levanta la suya cuando se invoca solo |
| `mise run migrate:check` | Sí | **La suya propia**, porque necesita una base virgen para subir, bajar y volver a subir |
| `mise run tenancy:literals` | No | Es una búsqueda sobre el código |
| `mise run evals:run -- --subset smoke` | **No** | Y tiene que seguir sin necesitarla: es lo que mantiene la cifra publicada de NFR21 |

La base efímera se levanta desde la propia suite con contenedores, con la imagen
anclada por huella del entorno local, y se conecta **con el rol del aplicativo**.
Conectarse como superusuario haría que toda la suite de aislamiento pasara sin
que exista aislamiento: es el fallo que no avisa.

## Qué se prueba, por capa

La unidad está en la rama evaluada, así que sus casos previos —las fixtures de
DS-8 y el escenario RT-4 de DS-6— se escriben, se corren y **se comprueba que
fallan** antes de implementar nada. Las capas que la sostienen siguen la rama
determinista, en este orden.

| Capa | Archivo de pruebas | Qué afirma |
| --- | --- | --- |
| Modelo de datos y conducta de la base | `tests/unit/tenancy/test_rls_assertion.py` | La aserción falla ante una tabla sin política, falla ante un rol con privilegio de salto, y pasa con el esquema correcto |
| Repositorio y acceso a datos | `tests/integration/u2/test_isolation.py` | Consulta sin filtro devuelve solo lo de su aseguradora; sin aseguradora fijada, cero filas; aseguradora inexistente falla antes de abrir transacción |
| Lógica de negocio: configuración | `tests/unit/tenancy/test_config.py` | Una carpeta rota no tumba a las otras dos; una cuarta carpeta queda disponible sin tocar código |
| Lógica de negocio: identidad | `tests/unit/tenancy/test_staff_identity.py` | La credencial lleva sus cuatro campos y caduca a las doce horas; las tres causas de rechazo dan respuestas idénticas entre sí; el agente de cuenta no decide; rotar invalida en el acto |
| Lógica de negocio: visitante | `tests/unit/tenancy/test_visitor_access.py` | El enlace se canjea dos veces dentro de su hora y no a las dos; las cuatro causas responden igual; la clave de navegador tiene una fila por aseguradora |
| Lógica de negocio: borrado | `tests/unit/tenancy/test_purge.py` | Los dos purgadores están registrados; una tabla con datos de visitante sin purgador hace fallar la prueba |
| Fronteras | `tests/integration/u2/test_import_contracts.py` | Los tres contratos de importación fallan ante una violación plantada a propósito |

Con la estrategia `Standard` —de cinco a ocho pruebas por componente— y seis
componentes, el orden de magnitud esperado es **entre 35 y 50 pruebas**. El
número exacto lo da la corrida, no esta estimación, y se registra medido en el
resumen de la etapa.

## Cómo se prueba lo que no se puede probar de frente

- **El rol sin privilegio de salto.** No basta con crear el rol así: la prueba
  pregunta al motor qué privilegios tiene el rol **vivo** de la conexión y falla
  si puede saltarse las políticas. Leer la migración que lo creó no prueba nada.
- **Las dos claves separadas.** No basta con que existan dos variables: la
  prueba presenta lo firmado con una clave al verificador de la otra y exige
  rechazo. Eso es lo único que prueba que están separadas.
- **El rechazo indistinguible.** La prueba compara las tres respuestas **entre
  sí**, no contra una plantilla escrita a mano. Una plantilla se actualiza y
  deja de detectar que una de las tres divergió.
- **La ausencia de fuga.** Las fixtures de DS-8 traen colisiones a propósito
  —mismo número de póliza, mismo nombre— porque una prueba con datos distintos
  pasaría aunque el aislamiento no existiera.

## Metas de cobertura

| Meta | Valor | Comando |
| --- | --- | --- |
| Agregado del aplicativo (NFR18.1) | 80 % o más | `mise run cov` |
| Módulo de aislamiento, crítico (NFR18.2) | 80 % o más | `mise run cov` |

NFR18.2 **se enciende con esta unidad**: U1 lo dejó declarado como no aplicable
hasta que llegara el primero de los cuatro módulos críticos, y `tenancy` es ese
primero.

El umbral **no se baja nunca** para que un paso pase. Si la cobertura no llega,
se escriben más pruebas o se explica por escrito qué quedó sin cubrir y por qué.

## Datos de prueba y dobles

- **Las fixtures de DS-8 viven versionadas**, un archivo por caso, con
  identificador estable. No se generan en tiempo de corrida.
- **Nada de datos de personas reales**, ni aquí ni en ningún sitio: los tres
  nombres de bandeja son los perfiles ficticios que fija FR9.6.
- **La base no se simula.** Las pruebas de aislamiento corren contra PostgreSQL
  de verdad, porque lo que se prueba es una conducta del motor —las políticas de
  fila— que un doble no tiene.
- **El reloj sí se controla**, para probar caducidades de doce horas y de una
  hora sin esperarlas.
- **Cada prueba es independiente del orden** y se puede correr sola.

## Lo que esta unidad no prueba

Las pantallas de la bandeja y del visitante (U14, U6), la ruta HTTP que canjea
el enlace (U14), el reinicio nocturno que llama a los purgadores (U20) y el
aislamiento de las tablas de puntos de control del grafo (U12). Cada una llega
con su unidad y con sus propias pruebas.
