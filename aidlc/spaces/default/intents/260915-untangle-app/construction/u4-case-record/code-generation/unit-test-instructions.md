# Instrucciones de prueba — U4 `case-record`

## El comando, y por qué está acotado

```
mise run test:u4
```

que se declara en `mise.toml` como:

```
uv run --project app/backend pytest -c app/backend/pyproject.toml \
  app/backend/tests/unit/case_record app/backend/tests/integration/u4 -q
```

Acotado a las rutas de esta unidad y a nada más, igual que `test:u1`, `test:u2`
y `test:u3`. La razón es concreta: `build-and-test` ejecuta el comando de cada
unidad, así que un comando sin acotar volvería a correr la suite entera una vez
por unidad.

**Esa tarea no existe todavía y la crea el paso 32 de este plan.** El contrato de
pruebas exige que el runner esté listo antes del primer paso de prueba; aquí el
runner ya existe —`pytest` con su configuración, instalados por U1— y lo que
falta es solo el nombre acotado. El primer paso de prueba del plan es el 5, tres
pasos después de que exista el directorio, y el 32 declara el atajo.

Mientras la tarea no exista, el comando equivalente es el de arriba escrito
entero. No se usa `mise run test` a secas en ningún momento.

## Estrategia y volumen

Estrategia activa **Standard**: de cinco a ocho pruebas por componente,
unitarias más integración en las fronteras. Siete componentes, así que el
volumen esperado está entre cuarenta y cincuenta y cinco pruebas.

El piso de cobertura es doble y ninguno sustituye al otro: **80 % agregado** del
aplicativo y **80 % propio del módulo del caso**, que es módulo crítico. Los dos
los mide `mise run cov`, que devuelve distinto de cero cuando no se alcanzan.

## Qué probar por componente

| Componente | Pruebas | Qué asegura |
| --- | --- | --- |
| `models.py` y `schema/` | 6–8 | Los siete campos del siniestro y los dos de la consulta; los enums rechazan lo que no está en su conjunto; las doce transiciones cargan y ninguna más; un tipo de registro sin campos declarados no permite crear |
| `numbering.py` | 5–6 | La forma del número; unicidad dentro de la aseguradora; inmutabilidad; dos prefijos iguales hacen fallar el arranque; un prefijo ausente también |
| `crypto.py` | 7–8 | El valor sellado no contiene el original ni por fragmentos ni con otra codificación; descifrar devuelve el original; clave equivocada da el valor no disponible sin tumbar la lectura; el identificador de clave viaja con la fila; sin clave el proceso no arranca; el error no lleva el valor |
| `rules.py` | 8 | Cada transición declarada se aplica; una no declarada se rechaza dejando su entrada; las cuatro condiciones de la vuelta atrás, con el reloj inyectado en 14:59 y en 15:01; la completitud da 5/7 exacto; un campo dicho sin confirmar cuenta o no según lo que su campo exige; una prueba de propiedad sobre secuencias de transiciones |
| `repository.py` | 6–7 | Un caso de otra aseguradora responde igual que uno inexistente; el dato personal se guarda cifrado; se recupera descifrado; la regla de importación falla ante una conexión plantada fuera del punto único |
| `api.py` e `history.py` | 6–8 | Las seis operaciones devuelven lo que el contrato declara; un turno sin redactar no compila; el historial no expone edición ni borrado; un rechazo de transición y un rechazo de cierre dejan su entrada |
| `purge.py` | 5–6 | Un caso público sembrado con las cinco tablas pobladas desaparece entero; uno local se conserva; el recuento del informe coincide con lo borrado |

## Pruebas de integración

Cuatro fronteras, contra base efímera con contenedor:

1. **Aislamiento**: dos aseguradoras con casos sembrados, y una consulta desde
   cada sesión que solo ve lo suyo.
2. **Migración**: sube, baja y vuelve a subir, con la aserción de aislamiento
   corriendo después.
3. **Cifrado extremo a extremo**: se siembra un caso por la superficie y se lee
   la columna cruda por el punto único de sesión, exigiendo que el valor
   sembrado no aparezca.
4. **Borrado**: el purgador contra las cinco tablas pobladas, y la prueba de U2
   que interroga al catálogo comprobando que ninguna tabla marcada quedó sin
   purgador.

## Datos de prueba

- **Fixtures por estado.** Un caso sembrado en cada uno de los siete estados, con
  su estado y su resolución esperados, como archivos de datos versionados con
  identificador estable. No se generan en tiempo de corrida.
- **Sin datos de personas reales.** Nombres, teléfonos, placas y cédulas son
  sintéticos, y los de las partes se eligen de forma que el escaneo de secretos
  no los confunda con nada.
- **Cada prueba monta lo suyo.** Independiente del orden de ejecución y de estado
  compartido, y se puede correr sola. Las de integración usan una transacción que
  se revierte, o truncan al montar.

## Dobles y simulación

- **El reloj se inyecta**, nunca se lee del sistema, en todo lo que dependa de
  la ventana de quince minutos. Es lo que hace comprobables los bordes de 14:59
  y 15:01 que pide la decisión de arquitectura.
- **La redacción no se simula.** U3 está construida y su punto único es barato;
  simularla convertiría la prueba de que el turno se guarda redactado en una
  prueba de que se llamó a un doble.
- **La base no se simula** en las pruebas de integración: contenedor efímero, que
  es lo que ya usan U1 y U2. Las unitarias de lógica pura no la necesitan, y esa
  es justamente la razón de que `rules.py` no importe el repositorio.
- **La clave de cifrado se genera en el montaje de cada prueba.** Nunca una clave
  real, nunca una fija escrita en el código de prueba.

## Cobertura

| Qué | Umbral | Comando |
| --- | --- | --- |
| Agregado del aplicativo | 80 % | `mise run cov` |
| Módulo del caso, por ser crítico | 80 % | `mise run cov`, tras añadir su fila a la lista de módulos críticos |

El umbral no se baja para que un paso pase. Si no se alcanza, se escriben más
pruebas o se dice que no se alcanzó, con el número real.
