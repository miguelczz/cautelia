"""El generador de datos sinteticos (U7, MOD-12, ADR-016).

Dos mundos que no se tocan, y esa separacion es la unidad entera:

1. **La redaccion** (`drafting`): pide al modelo, una vez por parte, aseguradora
   e idioma, un borrador de texto propio. El borrador va a `tmp/`, que git
   ignora, y **nadie de la composicion lo lee**. Es el unico modulo del paquete
   que importa `untangle.providers`, y solo la raiz de composicion
   (`untangle.server.synthetic_draft`) lo importa a el: dos contratos de
   importacion lo comprueban.
2. **La composicion**: lee los textos fuente revisados de `app/data/sources/` y
   la configuracion versionada de las aseguradoras, compone en memoria con el azar
   sembrado, valida todo y solo entonces escribe `app/data/` y su manifiesto, con
   los mismos bytes en cada corrida. No llama a ningun modelo ni lee ninguna clave
   (BR1.5).

Los modulos de la composicion:

- `models`: la forma de todo lo que se lee y se escribe, con sus validaciones.
- `sources`: carga los textos fuente y rechaza el que no trae su marca de
  revision, nombrando el archivo y la clave (BR2.2).
- `chooser`: el azar, derivado de SHA-256 sobre semilla, salida y contador
  (CG-U7-1). Ningun modulo del paquete usa `random`, `secrets` ni `uuid`.
- `canonical`: la escritura en forma canonica (BR1.1).
- `manifest`: el manifiesto con los hashes de entradas y salidas, y su
  comprobacion contra el arbol (BR1.4), que corre en `schema:check`.
- `generator`: el nucleo; recibe los compositores del corpus y garantiza que
  compongan sin azar ajeno a la semilla, sin reloj y sin escribir a medias.
- `composition`: el unico compositor del corpus, que recorre F3.2 en orden y usa:
  - `corpus`: formularios, clausulas, distractores, relaciones, copias de la
    agencia y la comprobacion de las diferencias declaradas;
  - `people`: personas y vehiculos ficticios desde los repertorios escritos a mano;
  - `policies`: las polizas emitidas, con las de ejemplo y las de DS-8;
  - `cases`: los casos sembrados desde sus turnos, y la cobertura de estados y de
    criterios;
  - `ds8`: DS-8, con las mismas filas que escribio U2.
- `cli`: `synthetic:generate` y `synthetic:check`, con el compositor registrado en
  `cli.CORPUS_COMPOSERS`.
"""
