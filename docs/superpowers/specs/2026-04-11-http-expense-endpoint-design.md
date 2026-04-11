# HTTP Expense Endpoint Design

## Resumen

Se agregará una API HTTP dedicada para registrar gastos por texto reutilizando el pipeline actual del bot de Telegram. El primer endpoint será `POST /api/v1/expenses/text` y aceptará un `telegram_user_id`, un texto en lenguaje natural y un flag opcional `force_commit`.

El objetivo es exponer la misma lógica de negocio que hoy usa Telegram sin reimplementar parsing, aprendizaje, matching de payees, split expenses ni creación en YNAB. La capa HTTP será delgada: autenticación, validación del request, traducción a JSON y delegación a `ExpenseService`.

## Enfoque arquitectónico

Se usará una capa HTTP nueva y separada a nivel de router/handler, pero servida en producción por el mismo servidor público de `src/infrastructure/health.py` para compatibilidad con Railway y su puerto único expuesto.

Arquitectura elegida:

- `main.py` seguirá iniciando el proceso principal y construyendo el `DIContainer`.
- `src/presentation/http/server.py` contendrá el router puro de rutas API bajo `/api/v1/` y podrá ofrecer un transporte HTTP opcional para pruebas o reutilización futura.
- `src/infrastructure/health.py` seguirá siendo el servidor público en `$PORT` y delegará `/api/v1/*` al router HTTP.
- Un handler/controlador HTTP resolverá `ExpenseService` y `UserConfigService` desde el contenedor.
- Toda lógica de negocio continuará en `ExpenseService`, respetando DI, aislamiento por usuario y `YNABRepositoryFactory`.

Esto mantiene una base limpia para futuros endpoints sin romper el modelo de despliegue de Railway.

## Endpoint

### `POST /api/v1/expenses/text`

Headers requeridos:

- `Authorization: Bearer <HTTP_API_KEY>`
- `Content-Type: application/json`

Body:

```json
{
  "telegram_user_id": 7321506689,
  "text": "Gaste 25k en Carulla",
  "force_commit": false
}
```

Campos:

- `telegram_user_id` — obligatorio, entero.
- `text` — obligatorio, string no vacío, mismo input libre que hoy procesa Telegram.
- `force_commit` — opcional, booleano.

## Semántica de negocio

El endpoint debe soportar dos comportamientos:

1. **Commit directo**
   - Si `force_commit=true`, siempre crea la transacción.
   - Si `force_commit` no viene y el usuario tiene confirmación desactivada, también crea la transacción.

2. **Preview**
   - Si `force_commit` no viene o es `false` y el usuario tiene `confirm_before_create=true`, el endpoint devuelve preview sin escribir en YNAB.

Reglas:

- El endpoint es solo para registro de gastos.
- Si el texto clasifica como `query`, se rechaza como error funcional.
- Debe soportar tanto `expense` como `shared_expense` reutilizando el pipeline existente.
- El endpoint no persistirá estados pendientes de confirmación. Solo devolverá un preview estructurado.

## Reutilización del pipeline actual

La capa HTTP debe reutilizar exactamente estas rutas de servicio:

- `ExpenseService.process_message()` para el caso de commit directo.
- `ExpenseService.prepare_shared_expense()` y `ExpenseService.prepare_expense()` para generar preview.
- `ExpenseService.commit_expense()` para completar un gasto preparado cuando el request requiera commit.

El orden recomendado para la rama preview es:

1. intentar `prepare_shared_expense()`
2. si no aplica, intentar `prepare_expense()`
3. si ambos fallan, caer al mismo manejo de error funcional que ya existe en `process_message()`

Esto replica la estrategia actual del `ExpenseHandler` y evita bifurcar la lógica.

## Contrato de respuesta

Respuesta exitosa con preview:

```json
{
  "status": "preview",
  "intent": "expense",
  "message": "Voy a registrar: Carulla $25.000 en Mercado.",
  "requires_confirmation": true,
  "transaction_id": null,
  "expense": {
    "payee": "Carulla",
    "amount": "25000",
    "category_name": "Mercado",
    "account_name": "Cuenta principal",
    "date": "2026-04-11"
  }
}
```

Respuesta exitosa con commit:

```json
{
  "status": "committed",
  "intent": "shared_expense",
  "message": "Registrado: Carulla $25.000.",
  "requires_confirmation": false,
  "transaction_id": "ynab-tx-123",
  "expense": {
    "payee": "Carulla",
    "amount": "25000",
    "category_name": "Mercado",
    "account_name": "Cuenta principal",
    "date": "2026-04-11"
  }
}
```

Respuesta de error:

```json
{
  "status": "error",
  "error_code": "USER_NOT_CONFIGURED",
  "message": "Tu cuenta aún no tiene presupuesto o cuenta por defecto configurados."
}
```

Reglas del payload:

- `status`: `preview` | `committed` | `error`
- `intent`: `expense` | `shared_expense`
- `message`: texto en español, estable y apto para consumidores humanos
- `expense.amount`: string en unidades humanas, no milliunits
- `transaction_id`: `null` en preview

## Seguridad

Se agregará una API key de servicio cargada desde configuración.

Reglas:

- Toda request al endpoint debe validar `Authorization: Bearer <HTTP_API_KEY>`.
- Si falta o no coincide, responder `401 Unauthorized`.
- No se expone ningún endpoint público sin autenticación.
- No se reutilizan credenciales de Telegram ni de YNAB para esta API.

## Manejo de errores

Mapeo propuesto:

- `400 Bad Request` — JSON inválido, request mal formado, tipos inválidos.
- `401 Unauthorized` — bearer token faltante o inválido.
- `404 Not Found` — `telegram_user_id` inexistente.
- `409 Conflict` — usuario existe pero no está configurado para registrar en YNAB.
- `422 Unprocessable Entity` — texto no parseable, intent `query`, split sin configuración requerida, o cualquier error funcional del mensaje.
- `502 Bad Gateway` — fallos esperados de YNAB/OAuth aguas abajo.
- `500 Internal Server Error` — error inesperado.

Se deben mapear excepciones de dominio a `error_code` estables. No se deben devolver trazas ni mensajes internos crudos.

## Componentes propuestos

- `src/presentation/http/` — nueva capa HTTP
- `src/presentation/http/server.py` — router puro de la API y transporte opcional
- `src/presentation/http/handlers/expense_api_handler.py` — endpoint `POST /api/v1/expenses/text`
- `src/presentation/http/auth.py` o equivalente — validación del bearer token
- `src/presentation/http/serializers.py` o equivalente — serialización de respuestas JSON
- `src/infrastructure/config/app_config.py` — nuevo env var para `HTTP_API_KEY`
- `src/infrastructure/health.py` — delegación pública de `/api/v1/*`
- `main.py` — wiring del router HTTP junto con el servidor público existente

No se requieren migraciones de base de datos.

## Testing

Cobertura mínima requerida:

- auth válido/inválido/faltante
- request mal formado
- usuario inexistente
- usuario no configurado
- preview cuando el usuario tiene confirmación activada
- commit cuando la confirmación está desactivada
- `force_commit=true` overrideando confirmación
- rechazo de `query`
- gasto compartido exitoso
- fallo de YNAB mapeado a `502`

También deben mantenerse los invariantes del proyecto:

- YNAB en milliunits solo internamente
- DI con `YNABRepositoryFactory` por usuario
- aislamiento per-user por `telegram_user_id`
- mensajes user-facing en español
- tests para todo módulo nuevo

## Scope excluido

Este milestone no incluye:

- endpoint separado de confirmación diferida
- persistencia de previews pendientes
- nuevos endpoints de consulta o estado
- cambio de framework HTTP
