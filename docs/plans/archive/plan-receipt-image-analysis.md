# Plan: Análisis de Imágenes de Recibos/Tickets

## Objective & Context
- **Status:** Completed
- **Goal:** Permitir que el usuario envíe una foto de un recibo/ticket y el bot extraiga automáticamente la información del gasto (monto, lugar, categoría) para cargarlo en YNAB.
- **Why:** Actualmente el bot solo acepta texto y voz. Muchos gastos generan un ticket físico — poder fotografiarlo y que se cargue automáticamente reduce la fricción de registro.

## Design Decisions

1. **Modelo de visión:** GPT-4o-mini (ya en uso, soporta visión, bajo costo). Si la precisión no es suficiente, cambiar a `gpt-4o` es un cambio de una línea.
2. **Ubicación:** Nuevo método `parse_receipt_image()` en `LLMExpenseParser` — ya tiene el cliente OpenAI, las categorías/cuentas YNAB, y la lógica de validación JSON. No se justifica un módulo separado como `speech_to_text.py` porque usa el mismo endpoint `chat.completions.create()`.
3. **Flujo single-pass:** La API de visión extrae datos estructurados directamente de la imagen (no OCR → texto → parse). Retorna el mismo formato dict que `parse_expense()`.
4. **Una transacción por recibo:** El monto total del ticket se carga como una transacción. Los items individuales van al campo memo.
5. **Soporte para caption:** El usuario puede agregar un comentario a la foto (ej: "almuerzo con amigos") que se incluye como contexto adicional.
6. **No requiere dependencias nuevas:** `openai` v2.26.0 ya soporta visión, `base64` es stdlib. Sin cambios en `requirements.txt`.

## Prerequisites (Manual)
- [ ] Ninguno — OpenAI API key ya configurada, GPT-4o-mini ya soporta visión

## Implementation Steps

### [x] Step 1: Domain Exception
- **Files:** `src/domain/exceptions.py`
- **Action:** Agregar `ImageProcessingException(YNABBotException)` siguiendo el patrón de `SpeechProcessingException` (línea 53-57). Campos: `message`, `file_size`.
- **Tests:** `tests/test_domain_exceptions.py` — test básico de instanciación y herencia

### [x] Step 2: LLMExpenseParser — método `parse_receipt_image()`
- **Files:** `src/parsers/llm_expense_parser.py`
- **Action:**
  - Agregar método privado `_generate_receipt_system_prompt()` que:
    - Reutiliza las secciones de categorías/cuentas de `_generate_system_prompt()`
    - Instrucciones específicas para recibos: extraer monto total, nombre del local/tienda, fecha si es visible, listar items para memo
    - Contexto colombiano (pesos, formatos de recibo locales)
    - Retorna el mismo JSON: `{amount, category, payee, account, memo, confidence}`
    - Instrucción de retornar `confidence: 0.0` si la imagen no es un recibo o es ilegible
  - Agregar método público `parse_receipt_image(image_base64: str, caption: str = None) -> Optional[Dict]`:
    - Construye mensaje multi-contenido: `[{"type": "image_url", ...}, {"type": "text", ...}]`
    - El texto del usuario es: "Analiza este recibo/ticket y extrae la información del gasto." + caption si existe
    - Usa `client.chat.completions.create()` con el prompt de recibo
    - `max_tokens=500` (más que texto, los recibos pueden tener más items en memo)
    - Valida JSON con la misma lógica que `parse_expense()` (amount > 0, confidence in range, campos requeridos)
- **Tests:** `tests/test_llm_expense_parser.py` — agregar tests al archivo existente:
  - `test_parse_receipt_image_success` — mock OpenAI retorna JSON válido
  - `test_parse_receipt_image_with_caption` — verifica que caption se incluye en el mensaje
  - `test_parse_receipt_image_not_a_receipt` — confidence 0.0 para imagen no-recibo
  - `test_parse_receipt_image_api_error` — OpenAI lanza excepción → retorna None
  - `test_parse_receipt_image_invalid_json` — respuesta no-JSON → retorna None
  - `test_parse_receipt_image_includes_categories` — categorías incluidas en prompt

### [x] Step 3: ExpenseService — método `process_receipt_image()`
- **Files:** `src/application/services/expense_service.py`
- **Action:**
  - Agregar método público `process_receipt_image(telegram_user_id: int, image_base64: str, caption: str = None) -> ExpenseResult`
  - Sigue el mismo pipeline que `process_expense_message()` (líneas 167-225):
    1. Obtener user config + validar
    2. Obtener YNAB repository per-user
    3. Cargar categorías y cuentas
    4. Actualizar LLM parser con datos YNAB
    5. Llamar `self.llm_parser.parse_receipt_image(image_base64, caption)` en vez de `parse_expense()`
    6. Construir Expense con `_build_expense_from_parsed()` — usar `parser_source='receipt'`
    7. Enhance con learning, set default account, crear transacción YNAB, registrar learning
  - Reutilizar `_build_expense_from_parsed()` y el pipeline existente al máximo. Agregar parámetro opcional `parser_source` a `_build_expense_from_parsed()` (default `'llm'` para no romper lo existente).
  - Import `ImageProcessingException` en las excepciones manejadas
- **Tests:** `tests/test_expense_service.py` — agregar tests al archivo existente:
  - `test_process_receipt_image_success` — happy path completo
  - `test_process_receipt_image_with_caption` — caption pasa al parser
  - `test_process_receipt_image_parse_failure` — parser retorna None → error
  - `test_process_receipt_image_user_not_configured` — error apropiado
  - `test_process_receipt_image_parser_source` — verificar `expense.parser_source == 'receipt'`

### [x] Step 4: ExpenseHandler — método `handle_photo_message()`
- **Files:** `src/presentation/telegram/handlers/expense_handler.py`
- **Action:**
  - Agregar import de `base64` y `ImageProcessingException`
  - Agregar método `handle_photo_message()` con decorador `@require_authentication`, siguiendo el patrón de `handle_voice_message()` (líneas 54-112):
    1. Log handler start
    2. Obtener user_id
    3. Obtener foto de mayor resolución: `photo = update.message.photo[-1]`
    4. Descargar file info: `photo_file = await photo.get_file()`
    5. Validar tamaño (máximo 5MB): `if photo_file.file_size > 5 * 1024 * 1024: raise ImageProcessingException(...)`
    6. Enviar indicador de procesamiento: `await update.message.reply_text("📸 Analizando recibo...")`
    7. Descargar a temp file: `tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)`
    8. Leer y codificar en base64
    9. Obtener caption: `caption = update.message.caption`
    10. Llamar `expense_service.process_receipt_image(user_id, image_base64, caption)`
    11. Formatear respuesta: si success → `"📸 *Recibo analizado*\n\n" + formatter.format_success(result)`, si error → `formatter.format_error(result)`
    12. Cleanup temp file en `finally` block
  - Actualizar `handle()` para despachar a `handle_photo_message` cuando `update.message.photo` exista
- **Tests:** Nuevo archivo `tests/test_expense_handler_photo.py`:
  - `test_handle_photo_message_success` — mock update con photo, verificar flujo completo
  - `test_handle_photo_message_with_caption` — caption se pasa al servicio
  - `test_handle_photo_message_too_large` — file_size > 5MB → error
  - `test_handle_photo_message_processing_error` — excepción del servicio → mensaje de error

### [x] Step 5: Registrar handler de foto en bot.py
- **Files:** `src/presentation/telegram/bot.py`
- **Action:** En `_register_handlers()`, agregar handler de foto junto a los otros message handlers (línea 72):
  ```python
  self.application.add_handler(MessageHandler(filters.PHOTO, self.expense_handler.handle_photo_message))
  ```
  Ubicar antes del handler de TEXT, después de VOICE.
- **Tests:** No requiere tests unitarios adicionales (es solo registro de handler)

### [x] Step 6: Actualizar textos de ayuda en formatters
- **Files:** `src/presentation/telegram/formatters.py`
- **Action:**
  - En `format_help_message()`: agregar sección de recibos/tickets:
    ```
    📸 *Recibos/Tickets:*
    - Envía una foto de un recibo o ticket
    - El bot extraerá monto, lugar y categoría automáticamente
    - Puedes agregar un comentario a la foto (ej: "almuerzo con amigos")
    ```
  - En `format_welcome_message()`: mencionar la capacidad de lectura de recibos en features
- **Tests:** `tests/test_formatters.py` — verificar que los nuevos textos aparecen en la salida

## Constraints & Architecture
- Sigue la arquitectura por capas existente: handler → service → parser → domain
- No se crean nuevos módulos de integración — `LLMExpenseParser` ya encapsula toda la interacción con OpenAI
- YNAB milliunits (×1000, negado para gastos) se maneja en `Expense.to_ynab_format()` — sin cambios
- No requiere migración de base de datos
- `parser_source='receipt'` distingue transacciones creadas desde foto vs texto/voz

## Verification
- [x] Enviar foto de un recibo real en Telegram → verificar que se crea la transacción en YNAB con monto, payee y categoría correctos
- [x] Enviar foto de recibo con caption → verificar que el caption influye en la categorización
- [x] Enviar foto de algo que no es un recibo → verificar mensaje de error amigable
- [x] Enviar foto de muy baja calidad/borrosa → verificar manejo graceful
- [x] `pytest` — todos los tests pasan (~349 existentes + nuevos)
- [x] Verificar que voice y text siguen funcionando sin regresiones
