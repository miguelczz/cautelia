# Evaluación: ¿hacen falta historias de usuario?

**Decisión:** Ejecutar.

## Razón

Untangle tiene cuatro superficies que una persona usa en vivo (la llamada de
voz, el chat, la bandeja a la que se entra con enlace firmado y la evidencia
pública que lee quien contrata), varias personas con objetivos distintos y a
veces opuestos, y lógica de negocio con fronteras duras: quién decide la
cobertura, qué se puede citar, cuándo se deriva, cuánto se puede gastar.

Los requisitos (`../requirements-analysis/requirements.md`) dicen qué debe
cumplir el sistema, con criterio de aprobado o fallido. No dicen desde el punto
de vista de quién se comprueba cada cosa, ni cómo se recorre un caso de punta a
punta. El asegurado quiere una respuesta; la aseguradora exige que la
inteligencia artificial no la dé; el evaluador quiere comprobar que ambas cosas
son verdad en treinta minutos. Esa tensión solo se ve cuando cada requisito
tiene dueño, y es la brecha que cierran las historias.

## Factores considerados

| Factor | Qué se observó | Qué indica |
| --- | --- | --- |
| Tipo de proyecto | Brownfield de marketing, greenfield de aplicación: no hay código del aplicativo ni historias previas (`codekb/untangle/business-overview.md`) | Todo el comportamiento se define desde cero |
| Alcance de cara a personas | Voz y chat públicos, bandeja por enlace firmado, README, video, reporte de evaluación y landing | Ejecutar |
| Personas | Ocho roles en el PRD 9.3 y tres compradores del lado de quien contrata en el PRD 3.1 | Ejecutar: hay que decidir cuáles escriben historias |
| Complejidad de negocio | Grafo de cuatro nodos con dos ritmos, derivación obligatoria, citación verificada, reglas por aseguradora, límites y techo de gasto | Ejecutar |
| Coordinación | Una sola persona construye, pero diseño, desarrollo y calidad revisan, y Construcción recorre el trabajo por componente | Las historias deben llevar los módulos que tocan |
| Contrapeso | 84 requisitos funcionales y 21 no funcionales ya son verificables | Las historias no repiten los requisitos: les dan dueño, recorrido y criterios Dado/Cuando/Entonces |

## Dónde aportan más valor

- **Criterios que el golden set puede convertir en casos.** La práctica de
  pruebas afirmada escribe el caso de evaluación antes de implementar todo
  comportamiento que el PRD mide; un criterio Dado/Cuando/Entonces por idioma es
  la materia prima de ese caso.
- **Las fronteras de honestidad de la agente** (las personas deciden cobertura y
  dinero, ninguna cita sin cláusula, no prometer lo que no existe, no fingir ser
  humana) escritas como conducta observable en los dos idiomas, y no como
  principios que cada componente interpreta a su manera.
- **El recorrido de quien evalúa** (caso de uso UC-5 del PRD), que el PRD pone en
  el centro y los requisitos reparten en entregables sueltos.
- **Las tres observaciones aceptadas como riesgo en Requirements Analysis**: las
  funcionalidades Should que desaparecieron, la agente que nunca finge ser una
  persona y el objetivo de costo escrito para una llamada más larga que el
  límite.
- **Contradicciones entre documentos aprobados** que las historias deben
  resolver en lugar de heredar; se listan en el plan
  (`user-stories-questions.md`).
