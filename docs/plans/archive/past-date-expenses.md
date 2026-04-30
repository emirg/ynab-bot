# Plan: Soporte de fechas en gastos (pasadas y futuras)

## Objective & Context
- **Status:** Completed
- **Harness Roadmap Marker:** E.3
- **Goal:** Permitir que el bot detecte fechas en mensajes de gasto (ej. "ayer gasté 20k en Carulla", "el 24/07 gasté 30k en Wok") y registre la transacción en YNAB con esa fecha en lugar de la fecha actual.
- **Why:** Actualmente todos los gastos se registran con `datetime.now()`, ignorando cualquier referencia temporal en el mensaje del usuario.

## Affected Components
- `src/parsers/llm_expense_parser.py` — Agregar campo `date` a los tres prompts del LLM y pasar la fecha actual como contexto
- `src/application/services/expense_service.py` — Leer el campo `date` del resultado parseado y asignarlo al `Expense`
- `src/presentation/telegram/formatters.py` — Mostrar la fecha en la respuesta cuando difiere de hoy
- `tests/test_llm_expense_parser.py` — Tests para validación del campo `date` en resultados parseados
- `tests/test_expense_service.py` — Tests para propagación de fecha al dominio
- `tests/test_formatters.py` — Tests para formato condicional de fecha

## Prerequisites (Manual)
- Ninguno

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Agregar soporte de fecha en el parser LLM y en la construcción del Expense -->

#### [x] Step 1: Agregar campo `date` a los prompts del LLM parser
- **Files:** `src/parsers/llm_expense_parser.py`
- **Action:**
  1. En `_generate_message_system_prompt()`: agregar al prompt la fecha actual del sistema (`datetime.now().strftime("%Y-%m-%d")` y el día de la semana en español) como contexto para que el LLM pueda resolver fechas relativas. Agregar el campo `"date": "<YYYY-MM-DD_o_null>"` a las tres estructuras JSON de respuesta (expense, shared_expense, query no lo necesita). Agregar instrucciones claras:
     - Si el mensaje menciona una fecha (relativa como "ayer", "anteayer", "el lunes", "la semana pasada" o absoluta como "24/07", "el 5 de marzo", "el 3"), resolver a formato `YYYY-MM-DD`.
     - Para fechas absolutas sin año (ej. "24/07"): usar la ocurrencia más reciente en el pasado respecto a la fecha actual. Si la fecha aún no ha pasado este año, usar el año anterior.
     - Para fechas futuras explícitas (ej. "mañana", "el viernes"): resolver normalmente.
     - Si no hay mención de fecha, devolver `null`.
  2. En `_generate_system_prompt()` (usado por `parse_expense()` / voz): misma lógica — inyectar fecha actual, agregar campo `"date"` al JSON de respuesta con las mismas instrucciones.
  3. En `_generate_receipt_system_prompt()`: la fecha ya se maneja como parte del memo. Agregar campo `"date": "<YYYY-MM-DD_o_null>"` al JSON. Si la fecha es visible en el recibo, extraerla en formato `YYYY-MM-DD` además de incluirla en el memo.
- **Tests:** `tests/test_llm_expense_parser.py` — Verificar que el resultado parseado puede incluir un campo `date` como string o null. No se testea el LLM directamente, pero sí la validación del campo en los métodos `parse_message()`, `parse_expense()`, y `parse_receipt_image()` (mock del LLM response).

#### [x] Step 2: Propagar campo `date` del resultado parseado al modelo `Expense`
- **Files:** `src/application/services/expense_service.py`
- **Action:**
  1. En `_build_expense_from_parsed()`: leer `result.get('date')`. Si es un string no nulo, parsearlo con `datetime.strptime(date_str, "%Y-%m-%d")` y asignarlo al `Expense`. Si es `null` o falla el parseo, no hacer nada (se usará el default `datetime.now()`).
  2. No se necesitan cambios en el modelo `Expense` — ya tiene `date: datetime = field(default_factory=datetime.now)`.
- **Tests:** `tests/test_expense_service.py` — Verificar que:
  - Un resultado parseado con `"date": "2026-03-17"` produce un `Expense` con `date` = `datetime(2026, 3, 17)`.
  - Un resultado parseado con `"date": null` produce un `Expense` con `date` ≈ `datetime.now()`.
  - Un resultado parseado con `"date": "invalid"` produce un `Expense` con `date` ≈ `datetime.now()` (graceful fallback).

### Group 2 (depends on: Group 1)
<!-- Mostrar la fecha en la respuesta al usuario -->

#### [x] Step 3: Mostrar fecha en la respuesta de Telegram cuando difiere de hoy
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:**
  1. En `format_success()`: comparar `expense.date.date()` con `date.today()`. Si difieren, agregar una línea `📅 *Fecha:* {expense.date.strftime("%d/%m/%Y")}` en cada una de las tres variantes del mensaje (other-paid split, regular split, regular expense). Insertar después de la línea de lugar (🏪). Si la fecha es hoy, no mostrar nada (comportamiento actual).
  2. Importar `from datetime import date` al inicio del archivo.
- **Tests:** `tests/test_formatters.py` — Verificar que:
  - Un gasto con fecha de hoy NO muestra la línea de fecha.
  - Un gasto con fecha distinta a hoy SÍ muestra `📅 *Fecha:*` con el formato correcto.
  - Funciona para los tres tipos de mensaje (regular, split, other-paid split).

## Constraints & Architecture
- El campo `date` ya existe en el modelo `Expense` y ya se usa en `to_ynab_format()` con `self.date.strftime("%Y-%m-%d")`, así que la fecha se propagará automáticamente a YNAB sin cambios adicionales.
- No se requiere migración de base de datos.
- El LLM necesita la fecha actual como contexto para resolver fechas relativas — esto se inyecta dinámicamente en el prompt, no se hardcodea.
- Todos los strings UI deben estar en español.

## Verification
- [x] Enviar "ayer gasté 20k en Carulla" → la transacción se registra con fecha de ayer en YNAB, y la respuesta muestra `📅 *Fecha:* DD/MM/YYYY`.
- [x] Enviar "gasté 30k en Wok" (sin fecha) → comportamiento actual, sin línea de fecha en la respuesta.
- [x] Enviar "el 24/07 gasté 15k en cine" → se registra con fecha 24/07 del año más reciente en el pasado.
- [x] Enviar "mañana gasto 10k en uber" → se registra con fecha de mañana.
- [x] Enviar un audio diciendo "ayer almorcé por 25k" → funciona igual que texto.
- [x] Gasto compartido con fecha: "ayer compartimos 50k en restaurante con Juan" → fecha correcta en YNAB.
