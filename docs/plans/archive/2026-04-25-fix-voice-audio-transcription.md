# Plan: Fix Voice Audio Transcription

## Objective & Context
- **Status:** Completed
- **Source Spec:** `docs/specs/archive/2026-04-25-fix-voice-audio-transcription.md`
- **Goal:** Restore voice expense capture and block suspicious hallucinated transcripts such as `Mas informacion www.alimmenta.com` from reaching expense parsing.
- **Approach:** Add test coverage around speech transcription validation, introduce a small transcript sanity-check layer in `SpeechToTextProcessor`, and wire handler behavior so valid transcripts proceed while suspicious output returns a safe Spanish error.

## Affected Components
- `src/integrations/speech_to_text.py` - add transcript classification/sanitization and structured diagnostics.
- `src/presentation/telegram/handlers/expense_handler.py` - route suspicious transcription failures to the existing Spanish voice error path.
- `tests/presentation/telegram/test_expense_handler.py` - cover voice handler valid/suspicious transcript behavior.
- `tests/integrations/test_speech_to_text.py` - create focused unit tests for transcript cleanup and rejection.

## Prerequisites (Manual)
- [ ] Confirm production `OPENAI_API_KEY` points to the intended account/project.
- [ ] Capture one non-sensitive failing Telegram voice sample or provider request log metadata, if available.
- [ ] If changing the speech model, verify current OpenAI speech transcription API behavior from official docs before implementation.

## Implementation Steps
*(Models MUST mark steps with [x] as they are completed and save the file)*

### Group 1
<!-- Characterize current failure and add focused failing tests. -->

#### [x] Step 1: Add suspicious transcript unit tests
- **Files:** `tests/integrations/test_speech_to_text.py`
- **Action:** Add tests that instantiate `SpeechToTextProcessor` without a real OpenAI client by bypassing or patching `__init__`, then assert `_clean_transcription` or the new validation helper rejects `Mas informacion www.alimmenta.com`, URL-only text, and accepts normal expense text.
- **Tests:** `.venv/bin/pytest tests/integrations/test_speech_to_text.py -q` should initially fail because the validation helper does not exist or does not reject the phrase.

#### [x] Step 2: Add voice handler regression tests
- **Files:** `tests/presentation/telegram/test_expense_handler.py`
- **Action:** Add one test where `process_telegram_audio` returns a valid expense and `expense_service.process_expense_message` is called with that transcript. Add another where the validated speech path rejects suspicious output and `expense_service.process_expense_message` is not called.
- **Tests:** `.venv/bin/pytest tests/presentation/telegram/test_expense_handler.py -q` should initially fail on the suspicious transcript expectation.

### Group 2 (depends on: Group 1)
<!-- Implement validation without changing provider architecture. -->

#### [x] Step 3: Implement transcript validation
- **Files:** `src/integrations/speech_to_text.py`
- **Action:** Add a small helper, for example `_is_suspicious_transcription(text: str) -> bool`, that flags known boilerplate, URL/domain-heavy transcripts, and transcripts with no expense-like natural language. Keep `_clean_transcription` focused on normalization and make `process_telegram_audio` return `None` for suspicious output.
- **Tests:** `.venv/bin/pytest tests/integrations/test_speech_to_text.py -q` should pass.

#### [x] Step 4: Use the validated processing path in the voice handler
- **Files:** `src/presentation/telegram/handlers/expense_handler.py`
- **Action:** Replace the direct `transcribe_audio(temp_file_path)` call with the validated `process_telegram_audio(temp_file_path)` path or a new explicit validated transcription method. Preserve timeout/rate-limit handling and temporary cleanup.
- **Tests:** `.venv/bin/pytest tests/presentation/telegram/test_expense_handler.py -q` should pass.

### Group 3 (depends on: Group 2)
<!-- Add observability and regression verification. -->

#### [x] Step 5: Add safe diagnostics
- **Files:** `src/integrations/speech_to_text.py`, `src/presentation/telegram/handlers/expense_handler.py`
- **Action:** Log audio file size, provider model, transcript rejection reason, and a redacted preview capped to a short length. Do not log raw audio or full transcript.
- **Tests:** Add or update tests with `caplog` in `tests/integrations/test_speech_to_text.py` for rejection reason without asserting sensitive full text.

#### [x] Step 6: Run targeted and full verification
- **Files:** No source edits expected.
- **Action:** Run `.venv/bin/pytest tests/integrations/test_speech_to_text.py tests/presentation/telegram/test_expense_handler.py -q`, then `.venv/bin/pytest`.
- **Tests:** All targeted tests and the full suite pass.

## Constraints & Architecture
- All Python commands must use `.venv/bin/python` or `.venv/bin/pytest`.
- Keep all Telegram user-facing strings in Spanish.
- Do not persist audio files or raw transcripts.
- Preserve existing DI: `ExpenseHandler` obtains `SpeechToTextProcessor` through the container.
- No database changes are expected.

## Verification
- [ ] Send a real Telegram voice note with a simple expense and confirm the transcript reflects the spoken content.
- [x] Send or simulate the known bad transcript and confirm the bot rejects it before parsing.
- [x] Confirm temporary files are removed after success and failure.
- [x] Confirm logs contain rejection reason and metadata, not raw audio.
