# Requisitos de seguridad — U1 `workspace`

U1 no autentica a nadie ni guarda datos de personas. Su superficie de ataque es
otra, y es la más subestimada de un proyecto que va a publicarse: **el
repositorio y la cadena de suministro**.

**Fuentes consumidas.** `../functional-design/functional-spec.md` (Flujo 1 paso 1
y Flujo 3), `../functional-design/rules.md` (BR1.2, BR1.10, BR3.6),
`../../../inception/requirements-analysis/requirements.md` (FR11.1 y las
restricciones del proyecto),
`../../../inception/contract-design/contract-summary.md` (C-01 convenciones, C-24
raíz de composición, C-28 artefactos generados) y
`../../../../codekb/untangle/technology-stack.md` (el repositorio actual, con la
landing y su `.gitignore`).

## Modelo de amenazas de esta unidad

Aplicado con STRIDE sobre lo único que U1 expone: el repositorio, la tubería y
el entorno de quien corre el comando.

| Amenaza | Qué podría pasar aquí | Control |
| --- | --- | --- |
| Divulgación de información | Una clave de proveedor llega a un commit y el repositorio se publica en la semana 12 | SEC-U1.1, SEC-U1.2 |
| Manipulación | Una dependencia comprometida entra por una resolución libre o por una versión recién publicada | SEC-U1.3, SEC-U1.4 |
| Elevación de privilegios | Un flujo de integración continua con permisos amplios puede escribir donde no debe | SEC-U1.5 |
| Repudio | No se sabe qué versión de qué modelo produjo una cifra publicada | SEC-U1.6 |
| Denegación de servicio | Una corrida agota los minutos de integración continua o la cuota del proveedor | SEC-U1.7 |
| Suplantación | Un commit se sube con la cuenta equivocada | SEC-U1.8 |

## Controles

| ID | Control | Valor esperado | Cómo se comprueba |
| --- | --- | --- | --- |
| SEC-U1.1 | Escaneo de secretos como **primer trabajo** del flujo | Cero hallazgos; uno bloquea | `gitleaks` sobre el cambio en cada corrida; sobre el historial completo por hito y antes de publicar (decisión Q3) |
| SEC-U1.2 | Ninguna clave en el repositorio | `.env.example` lista **nombres** de variables, nunca valores; el `.gitignore` ignora `.env*` con la negación de `.env.example` | Chequeo de contenido y revisión del `.gitignore` |
| SEC-U1.3 | Manifiesto y lockfile **con hashes de integridad** desde el primer commit, e instalación en modo reproducible | La instalación falla si el lockfile no coincide | El propio comando de instalación en la tubería |
| SEC-U1.4 | Espera de versiones recién publicadas | Dependencias con antigüedad mínima antes de instalarse; actualizaciones con período de enfriamiento | Configuración de los dos gestores y del robot de dependencias |
| SEC-U1.5 | Permisos mínimos en la tubería | Permisos vacíos por defecto, elevados solo donde haga falta; acciones fijadas por identificador de commit | Analizador de flujos en el guion de verificación |
| SEC-U1.6 | Trazabilidad de lo publicado | Cada corrida registra commit, identificador exacto de modelo y hash de prompt | Campo obligatorio de la corrida (OBS-U1.1) |
| SEC-U1.7 | Ningún gasto no escrito | El subconjunto de la compuerta corre en plan gratuito; los minutos de integración continua tienen tope con bloqueo | Revisión del flujo y del panel de gasto (U5) |
| SEC-U1.8 | Identidad correcta en cada operación contra el repositorio remoto | La cuenta activa es `miguelczz` | Comprobación antes de cada operación, por práctica del equipo |

**Una clave que llegó a un commit se considera comprometida y se rota en el
proveedor**; borrarla del archivo no cierra el incidente. Es regla del proyecto,
no criterio de esta unidad.

## Datos personales

U1 **no guarda datos de personas**. Dos matices que sí le tocan:

- Los casos de golden set contienen valores con forma de dato personal, todos
  ficticios y generados (FR12.3). Aun así se redactan en trazas, como cualquier
  otro dato.
- Las grabaciones de audio de personas reales **nunca entran al repositorio** y
  cada voz registra su consentimiento (BR1.10).

## Lo que no le toca a esta unidad

El aislamiento entre aseguradoras (U2), la redacción de datos personales (U3), la
guardia de salida y los escenarios adversariales (U10 y U21), y los límites de
las superficies públicas (U13 y U17). U1 no puede comprometerlos ni verificarlos.
