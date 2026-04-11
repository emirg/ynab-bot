# HTTP Expense Endpoint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Exponer un endpoint HTTP autenticado para registrar gastos por texto reutilizando el pipeline actual de `ExpenseService`, incluyendo preview opcional según la configuración de confirmación del usuario.

**Architecture:** Se agregará una capa `presentation/http` separada del servidor de health/OAuth actual. El endpoint `POST /api/v1/expenses/text` validará API key, parseará JSON y delegará a `ExpenseService` y `UserConfigService` sin duplicar lógica de negocio. La implementación debe soportar `expense` y `shared_expense`, rechazar `query` y devolver respuestas JSON estables para `preview`, `committed` y `error`.

**Tech Stack:** Python stdlib HTTP server, DIContainer existente, `ExpenseService`, pytest, `unittest.mock`

---

### Task 1: Extender configuración para la API HTTP

**Files:**
- Modify: `src/infrastructure/config/app_config.py`
- Modify: `config/.env.example`
- Test: `tests/test_app_config.py`

**Step 1: Write the failing test**

Agregar tests que verifiquen que:
- `HTTP_API_KEY` se carga correctamente desde env
- falta de `HTTP_API_KEY` produce error de configuración

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_config.py -v`
Expected: FAIL porque `HTTP_API_KEY` todavía no existe en `AppConfig`

**Step 3: Write minimal implementation**

Agregar `http_api_key` a `AppConfig` y cargarlo como env requerido. Documentarlo en `config/.env.example`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/infrastructure/config/app_config.py config/.env.example tests/test_app_config.py
git commit -m "feat: add http api key config"
```

### Task 2: Definir contrato HTTP y helpers de serialización

**Files:**
- Create: `src/presentation/http/__init__.py`
- Create: `src/presentation/http/serializers.py`
- Test: `tests/test_http_serializers.py`

**Step 1: Write the failing test**

Agregar tests para funciones que serialicen:
- respuesta `preview`
- respuesta `committed`
- respuesta `error`

Verificar campos: `status`, `intent`, `message`, `transaction_id`, `requires_confirmation`, `expense.amount` como string humana, fecha serializada.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_http_serializers.py -v`
Expected: FAIL porque el módulo no existe

**Step 3: Write minimal implementation**

Crear helpers puros que transformen `ExpenseResult`/`Expense` a dict JSON-friendly sin exponer milliunits ni objetos `datetime`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_http_serializers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/presentation/http/__init__.py src/presentation/http/serializers.py tests/test_http_serializers.py
git commit -m "feat: add http response serializers"
```

### Task 3: Implementar autenticación bearer para la API

**Files:**
- Create: `src/presentation/http/auth.py`
- Test: `tests/test_http_auth.py`

**Step 1: Write the failing test**

Agregar tests para validar:
- header ausente
- esquema no Bearer
- token inválido
- token válido

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_http_auth.py -v`
Expected: FAIL porque el módulo no existe

**Step 3: Write minimal implementation**

Crear helper puro que reciba headers esperados y el valor configurado de API key, y devuelva resultado booleano o excepción controlada.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_http_auth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/presentation/http/auth.py tests/test_http_auth.py
git commit -m "feat: add bearer auth for http api"
```

### Task 4: Implementar el handler del endpoint de gastos

**Files:**
- Create: `src/presentation/http/handlers/__init__.py`
- Create: `src/presentation/http/handlers/expense_api_handler.py`
- Test: `tests/test_expense_api_handler.py`

**Step 1: Write the failing test**

Agregar tests unitarios del handler para:
- `400` por JSON inválido
- `400` por campos faltantes o tipos inválidos
- `404` por usuario inexistente
- `409` por usuario no configurado
- `422` por mensaje no parseable
- `422` por intent `query`
- `502` por error esperado de YNAB/OAuth
- `500` por error inesperado

Mockear `ExpenseService`, `UserConfigService` y serializadores. No iniciar servidor real todavía.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_expense_api_handler.py -v`
Expected: FAIL porque el handler no existe

**Step 3: Write minimal implementation**

Crear un handler/controlador que:
- valide auth
- parsee el JSON
- verifique el usuario y su estado
- decida entre preview y commit
- use `prepare_shared_expense()` / `prepare_expense()` para preview
- use `process_message()` para commit directo cuando aplique
- rechace `query`
- convierta resultados a JSON y status code

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_expense_api_handler.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/presentation/http/handlers/__init__.py src/presentation/http/handlers/expense_api_handler.py tests/test_expense_api_handler.py
git commit -m "feat: add expense api handler"
```

### Task 5: Implementar el servidor HTTP dedicado

**Files:**
- Create: `src/presentation/http/server.py`
- Test: `tests/test_http_server.py`

**Step 1: Write the failing test**

Agregar tests para el router/servidor que verifiquen:
- `POST /api/v1/expenses/text` enruta al handler correcto
- rutas desconocidas devuelven `404`
- métodos no soportados devuelven `405` o `404` según la implementación elegida

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_http_server.py -v`
Expected: FAIL porque el servidor no existe

**Step 3: Write minimal implementation**

Crear el servidor HTTP usando stdlib y registrarlo separado de `infrastructure/health.py`. Debe aceptar el contenedor por cierre o dependencia explícita.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_http_server.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/presentation/http/server.py tests/test_http_server.py
git commit -m "feat: add dedicated http api server"
```

### Task 6: Integrar arranque en `main.py`

**Files:**
- Modify: `main.py`
- Modify: `docs/ARCHITECTURE.md`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

Agregar tests que verifiquen que `main()`:
- crea el contenedor
- inicia el health server existente
- inicia el nuevo servidor API HTTP con la misma configuración base

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL porque `main.py` todavía no inicia el nuevo servidor

**Step 3: Write minimal implementation**

Actualizar `main.py` para arrancar el nuevo servidor HTTP sin romper health/OAuth. Documentar la arquitectura actualizada en `docs/ARCHITECTURE.md`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add main.py docs/ARCHITECTURE.md tests/test_main.py
git commit -m "feat: wire http expense api into main"
```

### Task 7: Cubrir flujos de negocio end-to-end del endpoint

**Files:**
- Modify: `tests/test_expense_api_handler.py`
- Modify: `tests/test_http_server.py`
- Test: `tests/test_expense_api_handler.py`

**Step 1: Write the failing test**

Agregar escenarios completos para:
- preview cuando `confirm_before_create=True`
- commit cuando `confirm_before_create=False`
- `force_commit=true` overrideando confirmación
- shared expense exitoso

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_expense_api_handler.py tests/test_http_server.py -v`
Expected: FAIL hasta que el handler implemente correctamente la decisión preview/commit

**Step 3: Write minimal implementation**

Completar la lógica faltante del handler y/o servidor para soportar los escenarios reales del milestone.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_expense_api_handler.py tests/test_http_server.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_expense_api_handler.py tests/test_http_server.py src/presentation/http/handlers/expense_api_handler.py
git commit -m "test: cover preview and commit flows for http expense endpoint"
```

### Task 8: Verificación final y handoff

**Files:**
- Modify: `docs/wip_state.md`

**Step 1: Run focused test suite**

Run:

```bash
pytest tests/test_app_config.py tests/test_http_auth.py tests/test_http_serializers.py tests/test_expense_api_handler.py tests/test_http_server.py tests/test_main.py -v
```

Expected: PASS

**Step 2: Run broader regression suite**

Run:

```bash
pytest tests/test_expense_service.py tests/test_main.py -v
```

Expected: PASS y sin regresiones en el pipeline actual de gastos

**Step 3: Update handoff state**

Sobrescribir `docs/wip_state.md` con:
- último worker
- objetivo actual
- último avance
- archivos modificados
- blocker actual o estado
- siguiente paso exacto

**Step 4: Commit**

```bash
git add docs/wip_state.md
git commit -m "docs: update handoff after http expense endpoint"
```

## Constraints & Architecture

- Reutilizar `ExpenseService`; no duplicar parsing, aprendizaje ni creación de transacciones.
- Mantener `YNABRepositoryFactory` por usuario; nunca singleton de repositorio YNAB.
- Todo mensaje user-facing debe seguir en español.
- No agregar migraciones de DB para este milestone.
- No mezclar la nueva API con `src/infrastructure/health.py`; crear capa HTTP separada.
- El endpoint debe rechazar `query`; este milestone es solo para registro.
- `expense.amount` en respuestas HTTP debe ser humano-legible, no milliunits.
- Si el usuario tiene confirmación activada y `force_commit` no es `true`, responder preview sin persistencia de estado.

## Verification

- [ ] Llamar `POST /api/v1/expenses/text` con bearer token válido y usuario con confirmación activada devuelve `200` + `status=preview`
- [ ] Llamar el mismo endpoint con `force_commit=true` devuelve `200` + `status=committed` + `transaction_id`
- [ ] Un request con token inválido devuelve `401`
- [ ] Un mensaje que clasifica como query devuelve `422`
- [ ] Un split expense válido sigue funcionando vía endpoint
