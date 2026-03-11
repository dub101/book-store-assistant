from pathlib import Path

from book_store_assistant.config import AIProvider, AppConfig, ExecutionMode


def test_app_config_uses_project_data_directories() -> None:
    config = AppConfig()

    assert config.input_dir == Path("data/input")
    assert config.output_dir == Path("data/output")
    assert config.google_books_api_base_url == "https://www.googleapis.com/books/v1/volumes"
    assert config.google_books_max_retries == 2
    assert config.google_books_backoff_seconds == 1.0
    assert config.open_library_api_base_url == "https://openlibrary.org/api/books"
    assert config.execution_mode == ExecutionMode.RULES_ONLY
    assert config.ai_provider == AIProvider.OPENAI
    assert config.openai_api_base_url == "https://api.openai.com/v1"
    assert config.openai_model == "gpt-4o-mini"


def test_app_config_reads_runtime_overrides_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_MAX_RETRIES", "4")
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_BACKOFF_SECONDS", "0.25")
    monkeypatch.setenv("BSA_REQUEST_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("BSA_EXECUTION_MODE", "ai-enriched")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")

    config = AppConfig()

    assert config.google_books_max_retries == 4
    assert config.google_books_backoff_seconds == 0.25
    assert config.request_timeout_seconds == 3.5
    assert config.execution_mode == ExecutionMode.AI_ENRICHED
    assert config.openai_model == "gpt-4.1-mini"


def test_app_config_falls_back_when_environment_overrides_are_invalid(monkeypatch) -> None:
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_MAX_RETRIES", "not-an-int")
    monkeypatch.setenv("BSA_GOOGLE_BOOKS_BACKOFF_SECONDS", "not-a-float")
    monkeypatch.setenv("BSA_REQUEST_TIMEOUT_SECONDS", "still-not-a-float")
    monkeypatch.setenv("BSA_EXECUTION_MODE", "not-a-real-mode")

    config = AppConfig()

    assert config.google_books_max_retries == 2
    assert config.google_books_backoff_seconds == 1.0
    assert config.request_timeout_seconds == 10.0
    assert config.execution_mode == ExecutionMode.RULES_ONLY
