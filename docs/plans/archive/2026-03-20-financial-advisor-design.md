# OBSOLETE ~~Asesoramiento Financiero Proactivo — Design Spec~~

## Metadata
- **Harness Roadmap:** Ignore

## Resumen

Feature de asesoramiento financiero basado en los datos reales del presupuesto YNAB del usuario. El bot actua como un asesor financiero experto en finanzas personales, aplicando frameworks conocidos (50/30/20, fondo de emergencia, etc.) sobre metricas calculadas a partir de 3 meses de historial de transacciones.

Dos modos de acceso:
- **Comando `/asesoramiento`** — Analisis completo con resumen ejecutivo y secciones navegables via botones inline.
- **Lenguaje natural** — Preguntas sobre habitos, predicciones o reglas financieras detectadas via un nuevo intent `financial_advice`.

## Enfoque arquitectonico

**Hibrido (metricas en codigo + interpretacion por LLM):**
- El calculo numerico (promedios, tendencias, distribuciones, proyecciones) se hace en codigo — confiable y testeable.
- El LLM recibe metricas pre-calculadas y las interpreta como asesor financiero, cruzandolas con frameworks de finanzas personales para generar recomendaciones accionables.

## 1. Nuevo intent: `financial_advice`

El `LLMExpenseParser` gana un cuarto intent. Cuando el usuario escribe algo como "en que estoy gastando de mas?", "estoy cumpliendo la regla 50/30/20?" o "me va a alcanzar este mes?", el parser lo clasifica como `financial_advice` con un sub-tipo:

| Sub-tipo | Ejemplos |
|----------|----------|
| `habits` | "en que gasto mas?", "estoy gastando de mas en algo?" |
| `prediction` | "me va a alcanzar?", "cuanto voy a gastar este mes?" |
| `rules` | "como estoy con la regla 50/30/20?", "tengo fondo de emergencia?" |
| `general` | Asesoramiento general (fallback, y lo que genera `/asesoramiento`) |

**Distincion con intent `query` existente:** `query` pregunta por un dato concreto ("cuanto tengo en restaurantes?"), `financial_advice` pide interpretacion o recomendacion sobre los datos.

**Contrato JSON de respuesta del LLM para este intent:**

```json
{
  "intent": "financial_advice",
  "advice_type": "habits" | "prediction" | "rules" | "general",
  "query_text": "texto original de la pregunta del usuario"
}
```

No se incluyen campos de expense ni de query. `ExpenseService.process_message()` detecta `intent == "financial_advice"` y delega a `FinancialAdvisorService` pasando `advice_type` y `query_text`.

## 2. Capa de metricas: `FinancialMetricsService`

Servicio sin LLM. Recibe transacciones de los ultimos 3 meses + datos del presupuesto actual desde YNAB y produce un objeto `FinancialMetrics`.

### Metricas calculadas

- **Distribucion de gasto** — % del gasto total por categoria, agrupado en necesidades/deseos/ahorro (para la regla 50/30/20).
- **Promedios mensuales** — Gasto promedio por categoria en los ultimos 3 meses.
- **Tendencias** — Variacion % del mes actual vs promedio de los 2 meses anteriores, por categoria.
- **Presupuesto vs real** — Por cada categoria: presupuestado, gastado, % de ejecucion.
- **Proyeccion del mes** — Gasto proyectado al cierre del mes basado en el ritmo actual (gasto actual / dias transcurridos x dias del mes).
- **Ingresos estimados** — Promedio de inflows de los ultimos 3 meses (para calcular ratios ingreso/gasto).
- **Categorias inactivas** — Categorias con presupuesto asignado pero sin actividad en el mes.

### Clasificacion 50/30/20

YNAB no clasifica categorias como "necesidad" o "deseo" nativamente. El LLM infiere la clasificacion a partir de los nombres de las categorias como parte del analisis. En esta implementacion la clasificacion es efimera (solo existe en la respuesta del LLM, no se persiste). Cualquier futura configurabilidad por usuario requeriria una migracion de schema.

### Cache

Metricas cacheadas en memoria con TTL de **20 minutos** por usuario (dict keyed por `telegram_user_id`), para que la navegacion por secciones con botones inline sea instantanea sin recalcular.

**`FinancialMetricsService` debe registrarse como singleton en `DIContainer`** para que el cache persista entre requests.

**Cache miss durante navegacion por botones:** Si el usuario toca un boton despues de que el cache expiro, el handler responde el callback inmediatamente con `callback_query.answer()` (evita timeout de 10s de Telegram), envia un mensaje "Recalculando..." y luego edita/envia el resultado cuando este listo.

## 3. Capa de asesoramiento: `FinancialAdvisorService`

Toma las metricas de `FinancialMetricsService` y las pasa al LLM para generar recomendaciones.

### System prompt

El LLM actua como asesor financiero personal experimentado:
- Conoce frameworks: 50/30/20, fondo de emergencia (3-6 meses de gastos), etc.
- Da recomendaciones accionables y especificas, nunca genericas.
- Respuestas en espanol.
- Basa todo en los datos reales del usuario — nunca inventa numeros.

### Dos modos de operacion

**Comando `/asesoramiento`:**
1. Se pasan todas las metricas → LLM genera resumen ejecutivo (3-4 puntos clave).
2. El resumen se acompana de botones inline:
   - Distribucion de gastos
   - Tendencias y habitos
   - Proyecciones del mes
   - Reglas financieras (50/30/20)
   - Recomendaciones detalladas

**Lenguaje natural (intent `financial_advice`):**
- Segun el sub-tipo, se pasan solo las metricas relevantes a esa area.
- Genera una respuesta directa sin botones inline — es conversacional. El `AdvisoryResult` devuelve `sections: None`.

### Cada llamada al LLM recibe

- Las metricas relevantes (todas para resumen, subset para detalle/pregunta natural).
- El sub-tipo o seccion solicitada.
- El system prompt de asesor financiero.

**Mapeo de secciones a metricas:**

| Seccion (callback data) | Metricas incluidas |
|---|---|
| `advisor_distribution` | Distribucion de gasto, ingresos estimados |
| `advisor_trends` | Tendencias, promedios mensuales |
| `advisor_projections` | Proyeccion del mes, presupuesto vs real, categorias inactivas |
| `advisor_rules` | Distribucion de gasto (para 50/30/20), ingresos estimados, proyeccion del mes |
| `advisor_recommendations` | Todas las metricas (analisis holistic) |
| `advisor_back` | Todas las metricas (regenera resumen ejecutivo) |

Para preguntas en lenguaje natural, el mapeo por `advice_type`: `habits` → mismas que `advisor_trends`, `prediction` → mismas que `advisor_projections`, `rules` → mismas que `advisor_rules`, `general` → todas.

## 4. Presentacion: Handler y flujo de interaccion

### Nuevo handler: `AdvisorHandler`

Registra `/asesoramiento` y maneja callbacks de botones inline.

**Flujo del comando:**
1. Usuario envia `/asesoramiento`
2. Bot envia mensaje "Analizando tu presupuesto..." (indicador de latencia)
3. Handler llama a `FinancialMetricsService` → calcula y cachea metricas
4. Handler llama a `FinancialAdvisorService` con todas las metricas → resumen ejecutivo
5. Bot envia el resumen + teclado inline con las 5 secciones
6. Usuario toca un boton (ej. "Tendencias y habitos")
7. Handler llama a `FinancialAdvisorService` con metricas de esa seccion → respuesta detallada
8. Bot envia mensaje nuevo con el detalle + boton "Volver al resumen"

**Flujo de lenguaje natural:**
- Pasa por `ExpenseHandler` como hoy.
- `process_message()` detecta intent `financial_advice` → redirige a `FinancialAdvisorService`.
- Calcula metricas, pasa subset relevante al LLM, devuelve respuesta directa.

### Formatter: `FinancialAdvisorFormatter`

Estructura los mensajes con formato Telegram (negritas, emojis para secciones, montos formateados en pesos colombianos). El LLM genera el contenido, el formatter da estructura visual consistente.

## 5. Modelo de datos y dependencias

### Nuevos modelos de dominio

- **`FinancialMetrics`** — Dataclass inmutable con todos los campos de metricas calculadas.
- **`AdvisoryResult`** — Dataclass con tipo de respuesta (resumen/seccion/natural), texto generado por el LLM, y opcionalmente secciones disponibles para botones inline. Campo `sections: list[str] | None` con valores exactos para callback data: `"advisor_distribution"`, `"advisor_trends"`, `"advisor_projections"`, `"advisor_rules"`, `"advisor_recommendations"`.

### Sin migracion de base de datos

No se persiste nada nuevo. Metricas calculadas on-the-fly desde YNAB, cacheadas en memoria. Persistencia de clasificacion 50/30/20 y historial de recomendaciones quedan como mejora futura.

### Dependencias en `DIContainer`

```
FinancialMetricsService(ynab_repository_factory)
LLMAdvisorParser(openai_client)  # Nuevo — separado de LLMExpenseParser
FinancialAdvisorService(financial_metrics_service, llm_advisor_parser)
AdvisorHandler(financial_advisor_service, user_config_service)
```

**Nuevo `LLMAdvisorParser`** en `src/parsers/llm_advisor_parser.py`, dedicado y separado de `LLMExpenseParser`, porque el system prompt y formato de respuesta son completamente distintos.

### Impacto en codigo existente

- `LLMExpenseParser` — Agregar intent `financial_advice` al prompt de clasificacion (ver contrato JSON en seccion 1).
- `ExpenseService` — Recibir `FinancialAdvisorService` como dependencia inyectada en constructor (mismo patron que `budget_query_service`). Agregar branch en `process_message()` para el nuevo intent.
- `bot.py` — Registrar `AdvisorHandler`.
- `DIContainer` — Cablear los nuevos servicios. `FinancialMetricsService` como **singleton**.

**Nota sobre datos de presupuesto:** La metrica "presupuesto vs real" requiere los montos presupuestados por categoria. Verificar si `YNABCategory` ya trae `budgeted` y `activity` (del endpoint `/budgets/{id}/categories`). Si no, agregar un metodo `get_month_categories(budget_id, month)` a `YNABRepository` que consulte `/budgets/{id}/months/{month}` para obtener los envelopes del mes.

## 6. Testing y edge cases

### Estrategia de testing

- **`FinancialMetricsService`** — Tests unitarios puros (sin LLM, sin YNAB). Transacciones y presupuesto mockeados, verificar calculos: promedios, porcentajes, tendencias, proyecciones. Capa mas critica.
- **`FinancialAdvisorService`** — Tests con LLM mockeado. Verificar que pase metricas correctas segun modo (resumen vs seccion vs natural) y que construya el prompt adecuado.
- **`LLMAdvisorParser`** — Tests de integracion del prompt: formato de respuesta parseable, respeta espanol.
- **`AdvisorHandler`** — Tests de flujo: comando `/asesoramiento`, callbacks de botones inline, manejo de errores.
- **Intent detection** — Tests de que `financial_advice` se detecta correctamente y no colisiona con `query` existente.

### Edge cases

- **Usuario sin historial suficiente** — Menos de 1 mes de transacciones → mensaje: "Necesito al menos un mes de historial para darte recomendaciones utiles".
- **Pocas categorias** — Regla 50/30/20 puede no aplicar bien → LLM debe adaptarse.
- **Cache expirado mid-sesion** — Recalcular silenciosamente al tocar un boton.
- **Latencia** — Mensaje "Analizando tu presupuesto..." mientras se procesa el primer request.
- **Sin presupuesto configurado** — Redirigir a configuracion como ya hace el bot hoy.

## Scope futuro (excluido de esta implementacion)

- Consultas puntuales de asequibilidad ("puedo comprarme X?")
- Periodo de analisis configurable por usuario (hoy fijo en 3 meses)
- Clasificacion manual de categorias en necesidades/deseos/ahorro
- Persistencia del historial de recomendaciones
- Alertas proactivas basadas en deteccion de patrones negativos
