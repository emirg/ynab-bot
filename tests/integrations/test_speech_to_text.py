import logging

import pytest

from integrations.speech_to_text import SpeechToTextProcessor


@pytest.fixture
def processor():
    return object.__new__(SpeechToTextProcessor)


@pytest.mark.parametrize(
    "transcript",
    [
        "Mas informacion www.alimmenta.com",
        "Más información en www.alimmenta.com",
        "www.alimmenta.com",
        "https://example.com/info",
    ],
)
def test_process_telegram_audio_rejects_suspicious_transcripts(processor, transcript, caplog):
    processor.transcribe_audio = lambda audio_file_path, language="es": transcript

    with caplog.at_level(logging.WARNING):
        result = processor.process_telegram_audio("/tmp/fake.ogg")

    assert result is None
    assert "Rejected suspicious transcription" in caplog.text
    assert transcript not in caplog.text


def test_process_telegram_audio_accepts_normal_expense_text(processor):
    processor.transcribe_audio = (
        lambda audio_file_path, language="es": "Gasté veinticinco mil en Carulla con Nu"
    )

    result = processor.process_telegram_audio("/tmp/fake.ogg")

    assert result == "Gasté veinticinco 000 en Carulla con Nu"


def test_process_telegram_audio_accepts_short_expense_with_amount(processor):
    processor.transcribe_audio = lambda audio_file_path, language="es": "Uber diez mil"

    result = processor.process_telegram_audio("/tmp/fake.ogg")

    assert result == "Uber diez 000"
