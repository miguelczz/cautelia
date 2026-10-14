# Resumen del código — U10 `compliance`

U10 deja los controles que impiden que la agente prometa cobertura, montos o
culpa, dé consejo legal, diga ser humana, prometa transferencias o plazos, o
revele configuración; la detección de quien pide una persona, pregunta si habla
con una, o reporta heridos graves; el registro de la divulgación; la revisión de
cuatro controles al cierre y el nodo que cierra o deriva. Se construyó en dos
tandas por la rama evaluada: los casos primero, en rojo, y después la conducta
hasta dejarlos en verde.

## Evidencia de la rama evaluada

- **Paso 4, en rojo:** los 28 casos nuevos (12 de DS-2 y 16 de DS-6, 14 por
  idioma), corridos uno por uno sobre el commit `bb60516f549c`, terminaron los 28
  con el criterio sin registrar. Ninguno pasaba.
- **Paso 14, en verde:** el subconjunto de arranque corre 40 casos, los 14
  criterios de U10 en cada idioma más los 12 de U1: **español 20 pasan, 0
  fallan; inglés 20 pasan, 0 fallan**, en 0,93 s. Desde este commit corren en
  cada entrega por GitHub Actions.

## Resultados

| Compuerta | Resultado |
| --- | --- |
| `mise run test:u10` | 199 pruebas en verde |
| Suite completa | 1.019 pruebas del servidor y 162 de la interfaz |
| `mise run cov` | **87,65 %** agregado (servidor 91,17 %), sin exclusiones nuevas |
| `mise run rls:check` | 13 tablas con política; 11 llaves foráneas entre tablas aisladas revisadas, 0 fallos |
| `mise run contracts:check`, `lint`, `types`, `migrate:check` | En verde |
| `scripts/verify.sh` | 9 de 9 tras el commit |
| p95 de la guardia por frase (CG-U10-4) | **0,069 ms** sobre 320 evaluaciones, sin umbral propio: el presupuesto del turno es de U12 |

## Decisiones del conductor durante la generación

1. **Frase de derivación en inglés:** la del PRD, literal. En español, la de
   AC1.9.1.
2. **BR3.2 enmendada:** una negación ("todos estamos bien") ya no apaga una
   emergencia con un herido grave nombrado en el mismo turno. Se agregaron las
   filas y se extendieron los cuatro casos de emergencia, sin debilitar ninguno.
3. **La revisión lee el caso por un puerto** que arma la raíz de composición:
   `compliance` no importa `case_record` y el contrato `sin-ciclos` queda igual.
4. **Hueco de aislamiento cerrado.** Una fila de una aseguradora podía apuntar a
   un caso de otra, porque la llave foránea no pasa por la política de fila. La
   migración `u10_compliance_0002_tenant_fks` hace que las diez llaves entre
   tablas aisladas —las cuatro hijas del caso de U4, `trace_summary` de U5, las
   tres de U10 y dos que apuntan a un turno— lleven la aseguradora. `rls:check`
   tiene una cuarta pregunta que falla si vuelve a faltar, con una prueba por
   llave. Sin la migración fallan 10 de 11: el hueco era real.
5. **El arnés de accesibilidad elige un puerto libre**, así ver la demo en local
   nunca choca con la verificación. Las aserciones de U6 no cambiaron.

## Desviaciones declaradas

- **Contratos:** C-20 difiere en firmas que exigieron sus reglas, y C-12 gana
  `transcript_of`. Los dos quedan enmendados en `contract-summary.md` con fecha.
- **Entidades:** la guardia devuelve borradores de intervención sin
  identificador, porque el turno todavía no existe cuando evalúa;
  `ClosureDecision` gana la clave de la frase de cierre (BR6.4).
- **El evento de una intervención sale por `observability`**, sin la frase ni el
  identificador de traza: `compliance` no puede importar `telemetry` sin cerrar
  un ciclo. Anotarlo en el tramo del turno queda para U12.
- **Los objetivos de evaluación se registran en `evals/cli.py`**, como los de
  U3: el contrato `produccion-sin-evals` prohíbe hacerlo en la raíz de
  composición.
- **Contrato nuevo de importación, `cumplimiento-sin-proveedores`:** hace
  comprobable por herramienta que nada de U10 llega a un proveedor (BR5.3).
- **Nodo:** 5.000 ms y 2 intentos, fijados con el dato de que el detector de U3
  tarda unos 9 ms por turno; si la revisión falla, el nodo degrada a la frase de
  derivación.
- **Las exenciones de BR1.8 están vacías** hasta que U8 publique sus plantillas
  de respuesta verificada; el mecanismo está probado.
- **La migración se llama `u10_compliance_0001_tables`**: el nombre del plan no
  cabía en los 32 caracteres del identificador de versión.

## Lo que queda abierto

- **Frases escritas sin un criterio que las fije:** las permitidas de monto,
  plazo y revelación, la de degradación y las cuatro de hallazgos para la bandeja.
  Conviene que Miguel las lea; están en `app/config/copy/es.yaml` y `en.yaml`.
- **Knotwell y BR1.7:** como agencia, mencionar la aseguradora que emitió la
  póliza caería hoy en revelación de configuración. La emisora de la póliza se
  conoce cuando U8 y U11 la verifican, así que la excepción se conecta ahí: la
  guardia ya recibe el caso, y U11 o U12 le pasan la emisora como permitida.

## Archivos

99 rutas del espacio de trabajo, listadas en `source-manifest.json`: el paquete
`compliance/controls/`, el nodo, dos migraciones, los patrones en
`app/config/compliance/`, 28 casos y sus frases de prueba, 13 archivos de
pruebas, y los cambios en U4, U5 y U6 por el hueco de aislamiento, el puerto de
la revisión y el puerto del arnés.

## Trazabilidad

`traceability.json` cubre 68 identificadores: los 29 criterios, las 30 reglas y
los `NFRx.y` de U10. 64 apuntan a un archivo que existe; 3 quedan diferidos
—AC1.10.4 al juez de U21, NFR9.2 a U12 y U13, NFR12.3 a la pasada de
publicación— y `NFR12.1` se declara inexistente, porque U2 lo retiró.
