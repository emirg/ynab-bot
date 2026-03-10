# Plan: Consultas de Presupuesto por Texto Libre

## 🎯 Metadata
- **Status:** Draft
- **Primary Objective:** Permitir a los usuarios consultar saldos de categorías, cuentas y resumen de presupuesto en lenguaje natural, reutilizando el mismo flujo de texto libre que ya procesa gastos.
- **Risk / Complexity:** Medium

## 📝 Context
Actualmente el bot solo procesa gastos desde mensajes de texto. El usuario quiere poder hacer consultas sobre su presupuesto en lenguaje natural, como "¿Cuánto me queda en Groceries?" o "¿Cuánto debo en mi tarjeta Rappi Card?". Los datos ya están disponibles en la API de YNAB (categorías tienen `balance`/`budgeted`/`activity`, cuentas tienen `balance`/`cleared_balance`/`uncleared_balance`). El reto principal es distinguir entre un gasto y una consulta usando el mismo flujo de texto libre.

## 🛠️ Manual Prerequisites (Outside Code)
1. Ninguno. No se requieren nuevas variables de entorno ni configuración de infraestructura.

## 🏗️ Architectural / Data Model Changes

### Decisión de Diseño: LLM Single-Call con Clasificación de Intent

Modificar el prompt del LLM (GPT-4o-mini) para que en una sola llamada clasifique el intent del mensaje (`expense` vs `query`) y retorne la estructura JSON correspondiente. Esto es preferible a dos llamadas (clasificador + procesador) porque:
- **Costo:** 1 llamada en vez de 2
- **Simplicidad:** la distinción "25 lucas almuerzo" vs "cuánto me queda en restaurantes?" es obvia para el LLM
- **Consistencia:** se mantiene el patrón actual de single-call → JSON response

### Tipos de Consulta

| `query_type` | Ejemplo | Datos |
|---|---|---|
| `category_balance` | "¿Cuánto me queda en Groceries?" | `balance`, `budgeted`, `activity` de la categoría |
| `account_balance` | "¿Cuánto debo en mi Rappi Card?" | `balance`, `cleared_balance`, `uncleared_balance` |
| `budget_summary` | "¿Cómo va mi presupuesto?" | Totales agregados + top categorías por gasto |

### Flujo General

```
Usuario (texto) → ExpenseHandler.handle_text_message()
  → ExpenseService.process_message()           # nuevo método
    → LLMExpenseParser.parse_message()          # nuevo método, prompt extendido
    → if intent == "expense": pipeline existente de gasto
    → if intent == "query":  BudgetQueryService.execute_query()
      → YNABApiRepository (categorías/cuentas cacheadas, 5min TTL)
      → BudgetQueryResult
  → Handler formatea con BudgetQueryFormatter o ExpenseResponseFormatter
```

### Patrones a Reutilizar
- Lógica de fuzzy matching de `ExpenseService._find_category_id_by_name()` (~línea 200) y `_find_account_id_by_name()`
- Patrón `YNABRepositoryFactory.get_repository(user_config)` para acceso per-user
- Cache de 5min del `YNABApiRepository` (no duplicar llamadas API)
- `ExpenseResult` como referencia para `BudgetQueryResult`
- Patrón de formatters con métodos estáticos y Markdown

## 🚀 Implementation Order

### Step 1: Modelo de dominio para consultas
- **File:** `src/domain/models/budget_query.py` (nuevo)
- **Action:** Crear dos dataclasses siguiendo el patrón de `ExpenseResult` en `src/domain/models/expense.py`:
  - `BudgetQueryResult`: `success: bool`, `query_type: str` (`"category_balance"` | `"account_balance"` | `"budget_summary"`), `data: Optional[dict]`, `error_message: Optional[str]`
  - `MessageResult`: `intent: str` (`"expense"` | `"query"`), `expense_result: Optional[ExpenseResult]`, `query_result: Optional[BudgetQueryResult]`
- **Tests:** `tests/test_domain_models.py` — validar construcción de ambos dataclasses, valores por defecto, y que `MessageResult` encapsula correctamente cada tipo de resultado.

### Step 2: Extender el LLM Parser
- **File:** `src/parsers/llm_expense_parser.py` (modificar)
- **Action:**
  - Nuevo método `parse_message(message) -> Optional[Dict]` con prompt extendido que clasifica intent.
  - El prompt agrega detección de consultas con palabras clave: "cuánto", "cómo va", "resumen", "saldo", "debo", "queda", "he gastado", "presupuesto".
  - Response JSON para queries: `{"intent": "query", "query_type": "category_balance", "query_target": "Restaurants", "confidence": 0.9}`
  - Response JSON para expenses: `{"intent": "expense", "amount": 25000, "category": "...", "payee": "...", ...}`
  - El método existente `parse_expense()` NO se modifica (backward compatibility).
  - `max_tokens` puede subir a ~300 para el nuevo método.
- **Tests:** `tests/test_llm_expense_parser.py` — mock de OpenAI para verificar que `parse_message()` retorna correctamente intent `"query"` y `"expense"`, manejo de errores, y que `parse_expense()` sigue funcionando sin cambios.

### Step 3: Servicio de consultas de presupuesto
- **File:** `src/application/services/budget_query_service.py` (nuevo)
- **Action:** Crear `BudgetQueryService` con:
  - Constructor: `__init__(self, user_repository, ynab_factory)`
  - Método público: `execute_query(telegram_user_id, query_type, query_target, categories, accounts) -> BudgetQueryResult` — recibe categories/accounts ya cargados por `ExpenseService` para no duplicar llamadas API.
  - Métodos privados: `_query_category_balance(categories, target_name)`, `_query_account_balance(accounts, target_name)`, `_query_budget_summary(categories)`
  - Búsqueda fuzzy de categoría/cuenta: exact → case-insensitive → partial (misma estrategia que `ExpenseService._find_category_id_by_name()`).
  - Montos en milliunits (÷1000 para mostrar). El servicio retorna datos raw; el formatter convierte.
- **Tests:** `tests/test_budget_query_service.py` (nuevo) — tests de cada `query_type`, fuzzy matching (exact, case-insensitive, partial), categoría/cuenta no encontrada, y `budget_summary` con datos agregados.

### Step 4: Routing en ExpenseService
- **File:** `src/application/services/expense_service.py` (modificar)
- **Action:**
  - Nuevo parámetro de constructor: `budget_query_service: BudgetQueryService`
  - Nuevo método público `process_message(telegram_user_id, message) -> MessageResult`:
    1. Validar longitud del mensaje
    2. Cargar `user_config` + YNAB repo + categories/accounts (código compartido con `process_expense_message`)
    3. Llamar `self.llm_parser.parse_message(message)`
    4. Si `intent == "expense"`: reusar pipeline existente (extraer lógica post-parse de `process_expense_message` a método privado `_process_parsed_expense`)
    5. Si `intent == "query"`: delegar a `self.budget_query_service.execute_query()`
    6. Retornar `MessageResult`
  - `process_expense_message()` se mantiene para backward compatibility (voice handler lo usa).
- **Tests:** `tests/test_expense_service.py` — agregar tests para `process_message()`: routing correcto por intent expense, routing correcto por intent query, manejo de errores de parsing, y validación de longitud.

### Step 5: Formatter de consultas
- **File:** `src/presentation/telegram/formatters.py` (modificar)
- **Action:** Nueva clase `BudgetQueryFormatter` con métodos estáticos:
  - `format_category_balance(data)` → Markdown con presupuestado/gastado/disponible
  - `format_account_balance(data)` → Markdown con saldo/confirmado/pendiente
  - `format_budget_summary(data)` → Markdown con totales + top categorías
  - `format_error(result)` → Mensaje de error (categoría/cuenta no encontrada, etc.)
  - Formato de moneda: `${amount:,.0f}` con separador de miles (patrón existente en `formatters.py`).
- **Tests:** `tests/test_formatters.py` — tests de cada método de formato con datos de ejemplo, verificar formato de moneda correcto, y formato de errores.

### Step 6: Actualizar Handler
- **File:** `src/presentation/telegram/handlers/expense_handler.py` (modificar)
- **Action:** Modificar `handle_text_message()` para usar `process_message()` en vez de `process_expense_message()`:
  ```python
  result = self.expense_service.process_message(user_id, message)
  if result.intent == "expense":
      # formato existente con ExpenseResponseFormatter
  elif result.intent == "query":
      # formato nuevo con BudgetQueryFormatter
  ```
  Opcionalmente actualizar `handle_voice_message()` para también soportar consultas por voz.
- **Tests:** Tests existentes del handler deben seguir pasando. Agregar tests para el caso donde `result.intent == "query"` y se formatea con `BudgetQueryFormatter`.

### Step 7: DI Container
- **File:** `src/infrastructure/container.py` (modificar)
- **Action:**
  - Registrar `BudgetQueryService` como transient
  - Inyectarlo en `ExpenseService`
- **Tests:** Tests existentes del container deben seguir pasando.

### Step 8: Fixtures de test
- **File:** `tests/conftest.py` (modificar)
- **Action:** Agregar fixture `mock_budget_query_service` siguiendo el patrón de los mocks existentes (`mock_ynab_factory`, `mock_user_repository`, etc.).
- **Tests:** N/A — este paso habilita los tests de los pasos anteriores.

## 🔒 Security & Constraints
- Las consultas usan los mismos tokens OAuth per-user que los gastos — no se expone información de un usuario a otro.
- No se envía información sensible del presupuesto al LLM; el LLM solo clasifica el intent y extrae el target. Los datos financieros se consultan directamente de la API de YNAB.
- Se reutiliza el cache de 5min del `YNABApiRepository` para evitar llamadas excesivas a la API de YNAB.
- Validación de longitud de mensaje se mantiene para prevenir abuse del LLM.

## ✅ Verification & Acceptance Criteria
1. `pytest` — todos los tests existentes + nuevos deben pasar sin regresiones.
2. Prueba manual: enviar "¿Cuánto me queda en [categoría]?" → respuesta con balance (presupuestado/gastado/disponible).
3. Prueba manual: enviar "¿Cuánto debo en mi [cuenta]?" → respuesta con saldo (confirmado/pendiente).
4. Prueba manual: enviar "¿Cómo va mi presupuesto?" → resumen general con totales + top categorías.
5. Prueba manual: enviar un gasto normal (ej. "25 lucas almuerzo") → sigue funcionando igual (no hay regresión).
6. Prueba manual por voz (opcional): audio preguntando por presupuesto.
