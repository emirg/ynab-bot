# Spec: Fix Voice Audio Transcription

## Metadata
- **Status:** Implemented
- **Owner:** Codex
- **Related Roadmap Item:** Bugfix: critical voice expense capture regression
- **Related ADRs:** None

## Summary
Voice messages sent to the Telegram bot currently fail because the transcription returned to the expense flow is always or frequently `Mas informacion www.alimmenta.com`. That text is unrelated to the user's audio and may indicate model hallucination, contaminated input, a prompt failure, or misuse of a non-speech artifact. The bot must reject suspicious transcription output, surface a safe Spanish error, and provide enough diagnostics to identify whether the root cause is audio download/encoding, OpenAI transcription behavior, or downstream handling.

## Problem
- Users cannot create expenses by voice because the bot processes a fixed unrelated transcription instead of the spoken expense.
- The fixed URL-like phrase is suspicious and should not be passed into expense parsing as if it were user intent.
- The current voice path accepts any non-empty transcription longer than five characters and does not distinguish transcription quality failures from valid short expense messages.

## Goals
- Restore reliable voice expense processing for valid Spanish Telegram voice notes.
- Prevent unrelated URLs, website boilerplate, or transcription artifacts from entering the expense parser.
- Capture non-sensitive diagnostics that make the root cause auditable without logging raw audio or leaking user financial details.
- Keep all user-facing error messages in Spanish.

## Non-Goals
- Replacing the speech provider or changing the whole expense parsing pipeline.
- Persisting audio files or storing complete voice transcripts in the database.
- Supporting arbitrary audio formats beyond Telegram voice/audio files already handled by the bot.

## Users / Consumers
- Telegram users who send voice notes to record expenses.
- Maintainers debugging live transcription failures.
- The expense parsing flow that consumes voice transcripts as text.

## Expected Behavior
- A valid Spanish voice note such as "gasté veinticinco mil en Carulla con Nu" is transcribed into equivalent text and processed through the existing expense flow.
- A transcription that is empty, too short, mostly URL/domain text, or matches known unrelated boilerplate such as `Mas informacion www.alimmenta.com` is rejected before expense parsing.
- When transcription is rejected, the user receives a Spanish message explaining that the bot could not understand the audio and should try again with a shorter/clearer recording.
- The logs include the speech provider/model, audio metadata available from Telegram or the temporary file, failure class, and a redacted transcript preview.
- Temporary audio files are still cleaned up on every path.

## Inputs and Outputs
- **Inputs:** Telegram voice messages, downloaded temporary `.ogg` files, OpenAI speech transcription responses
- **Outputs:** Spanish Telegram responses, expense processing calls for valid transcripts, structured logs for transcription failures
- **Public Interfaces:** Telegram voice message handling; no command syntax changes

## Business Rules and Constraints
- User-facing strings must remain Spanish.
- Do not treat a speech transcript as authoritative if it fails sanity checks.
- Do not log raw audio or full sensitive financial speech content.
- Preserve per-user isolation and existing authentication middleware.
- Keep downstream expense amount semantics unchanged: YNAB amounts are milliunits and expenses are negative.

## Edge Cases and Failure Handling
- Empty transcription: reject with a speech-processing error.
- Transcript shorter than the minimum meaningful expense phrase: reject with a speech-processing error.
- Transcript containing only or mostly URLs/domains: reject with a suspicious-transcript error.
- Known unrelated boilerplate phrase: reject explicitly and log a diagnostic marker.
- OpenAI timeout/rate-limit/provider errors: keep current safe Spanish fallback behavior.
- Telegram download failure: keep current generic voice-processing fallback.
- Valid short phrase with a real amount, such as "Uber diez mil": should not be rejected only because it is brief.

## Acceptance Criteria
- [x] Voice handler tests cover a valid transcript reaching the expense service.
- [x] Speech processor tests reject `Mas informacion www.alimmenta.com` before expense parsing.
- [x] Speech processor tests reject mostly URL/domain transcripts and accept normal Spanish expense phrases.
- [x] User-facing voice transcription failures are Spanish and do not expose provider exception details.
- [x] Logs identify suspicious transcript failures without storing raw audio or full transcript content.
- [x] Temporary file cleanup remains covered by the handler tests.

## Open Questions
- Does the production failure happen with every Telegram voice note or only after a specific audio duration/format?
- Should the implementation move from `whisper-1` to the current OpenAI transcription model after confirming official support and response format behavior?
- Are audio files being downloaded as the expected Telegram voice content in production, or could a stale/corrupt temporary file be sent to OpenAI?

## References
- `src/integrations/speech_to_text.py`
- `src/presentation/telegram/handlers/expense_handler.py`
- `tests/presentation/telegram/test_expense_handler.py`
- `docs/ARCHITECTURE.md`
