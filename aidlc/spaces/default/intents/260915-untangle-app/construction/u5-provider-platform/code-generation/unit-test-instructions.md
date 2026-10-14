# Instrucciones de prueba — U5 `provider-platform`

## El comando exacto de esta unidad

```
uv run --project app/backend python -m pytest app/backend/tests/unit/providers app/backend/tests/unit/telemetry app/backend/tests/integration/u5
```

Queda en el archivo de tareas como `mise run test:u5`, con la misma forma que
`test:u2`, `test:u3` y `test:u4`: acotado a las rutas de esta unidad, **nunca**
un comando de proyecto entero. `build-and-test` corre el de cada unidad, y uno
sin acotar volvería a correr la suite completa una vez por unidad.

**El runner ya existe.** `pytest`, `pytest-asyncio`, `pytest-cov` y
`testcontainers` están instalados desde U1, y la configuración de cobertura con
su piso está en el manifiesto. El contrato de pruebas exige que el runner esté
listo antes del primer caso; aquí se **verifica**, no se crea: correr el comando
de arriba antes de escribir la primera prueba tiene que devolver "ningún caso
recogido", no un error de importación.

## Estrategia activa y volumen

Estrategia **Standard**: de cinco a ocho pruebas por componente, unitarias más
integración en las fronteras. El scope `classic` no añade piso de casos nuevos;
sí exige mantener verde la suite que ya existe y el 80 % agregado.

**Rama determinista.** Se implementa cada capa y a continuación se escriben y
corren las pruebas de esa capa, antes de pasar a la siguiente. Sin caso de
golden set previo: ninguna historia de esta unidad realiza M1, M4, M5, M6, M8,
M9, M13 ni M15.

## Reparto por pieza

| Pieza | Dónde viven sus pruebas | Cuántas | Qué cubren |
| --- | --- | --- | --- |
| Configuración de proveedores y precios | `tests/unit/providers/test_config.py` | 5–6 | Alias móvil rechazado; uso sin plan; tope `none_available` sin sustituto; fecha de comprobación vencida; precios con versión y fecha |
| Modelos del dinero y las cuotas | `tests/unit/telemetry/test_models.py` | 6–8 | El par costo-estado en las tres formas; `float` rechazado donde va dinero; cláusulas verificadas ≤ recuperadas; negación de cuota con motivo cerrado |
| Cálculo del costo | `tests/unit/telemetry/test_pricing.py` | 5–6 | Precio presente; precio ausente da "no medido" y nunca cero; suma de veinte fracciones independiente del orden |
| Aritmética del presupuesto | `tests/unit/telemetry/test_budget.py` | 6–8 | Los tres estados; el público restante con reserva; el cruce de la alerta una sola vez; el par que devuelve la agregación |
| Aritmética del cupo | `tests/unit/telemetry/test_quota.py` | 6–8 | Cupo a mitad de ventana y de presupuesto; cupo cero; tope de quince; medianoche de la zona configurada con reloj inyectado |
| Ayudante de tramos y resumen | `tests/unit/telemetry/test_traces.py` | 6–8 | Tres niveles anidados; grafía de los cuatro nodos; ningún dato personal en ningún atributo; `lost` a los diez segundos; resumen negado a otro navegador |
| Puertos y fábrica | `tests/unit/providers/test_factory.py` | 5–6 | Un cliente por uso con su clave; la fábrica no acepta clave por argumento; el cliente no se exporta |
| Adaptador de Gemini | `tests/unit/providers/test_gemini.py` | 7–8 | Los cuatro errores y ningún quinto; sin reintento ante saldo agotado; una sola llamada ante `rate_limited`; validación fallida es `invalid_response`; circuito abre a los cinco y no ante `invalid_response`; el texto externo queda fuera de la instrucción de sistema |
| Repositorio y esquema | `tests/integration/u5/test_repository.py` | 6–8 | Dos escrituras simultáneas no pasan el techo; el fallo de la segunda sentencia revierte la primera; borrar el caso deja la columna en nulo; la ventana sobrevive al purgador y al cambio de mes |
| Aislamiento y columnas | `tests/integration/u5/test_isolation.py` | 4–5 | La aserción pasa con las tres exclusiones escritas; falla ante una tabla excluida con `visitor_email`; el resumen de traza no se ve desde otra aseguradora |
| Superficie y purgador | `tests/integration/u5/test_api.py` | 6–8 | Facturable síncrono y no facturable fuera del camino; base caída rechaza lo facturable y el chat sigue; la cola llena escribe síncrono; el purgador borra lo de visitante y no la ventana |

## Cobertura

- **Piso agregado del 80 %**, que es el que aplica: U5 **no** está en la lista
  afirmada de módulos críticos con piso propio. El comando es `mise run cov` y
  lee su umbral del manifiesto.
- **No se toca el umbral ni la lista de exclusión** para que un paso pase. Si la
  cobertura no llega, lo que falta son pruebas.
- Los dos módulos nuevos —`providers` y `telemetry`— entran al cálculo agregado
  por sí solos: el agregado cubre todo el código del aplicativo.

## Dobles, y qué no se dobla

| Qué | Cómo se prueba | Por qué |
| --- | --- | --- |
| La API de Gemini | `respx`, inyectando los cuatro errores y respuestas mal formadas | Sin clave y sin costo. Una prueba que llamara al proveedor gastaría el presupuesto que esta unidad existe para proteger |
| La base de datos | **No se dobla**: base efímera con `testcontainers`, con la misma imagen anclada | Las propiedades que importan —el bloqueo de la fila, la transacción, el borrado que deja en nulo— solo existen en un motor real. Un doble las daría por buenas |
| El reloj | Inyectado en todas las pruebas de cuota y de ventana | La medianoche de la zona configurada y el cambio de mes son conducta, no ambiente |
| El backend de trazas | Exportador de prueba que registra lo que recibiría | Lo que se comprueba es qué sale, no que Langfuse lo reciba |
| El acumulado del presupuesto | **Forzado en la base**, nunca gastado de verdad | Regla del proyecto: las pruebas de límites no consumen el presupuesto que protegen |
| La clave del proveedor | Generada en el montaje del caso, nunca fija ni real | Una clave fija en el código de prueba es una clave en el repositorio |

## Datos de prueba

- **Sembrados en el caso, no compartidos.** Cada prueba monta lo suyo; ninguna
  depende del orden de ejecución ni de lo que dejó otra.
- **Los datos personales de las pruebas de trazas son ficticios y reconocibles**,
  para poder buscarlos enteros y por fragmentos en lo emitido.
- **Ningún golden set.** Esta unidad es de rama determinista; lo que se mide
  sobre DS-5 pertenece a U16 y a U21.

## Qué tiene que estar verde antes de dar la unidad por hecha

1. `mise run test:u5` — las pruebas de esta unidad.
2. `mise run lint` — con los cuatro contratos de importación nuevos.
3. `mise run types` — que es donde vive la lista cerrada de atributos y el
   rechazo de la coma flotante en dinero.
4. `mise run rls:check` — con las tres exclusiones y la aserción de columnas.
5. `mise run migrate:check` — la revisión sube, baja y vuelve a subir.
6. `mise run cov` — el agregado del 80 %.
7. `bash scripts/verify.sh` — los nueve pasos, que es la compuerta de verdad.
