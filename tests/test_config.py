from pathlib import Path

from book_store_assistant.config import AppConfig


def test_app_config_uses_project_data_directories() -> None:
    config = AppConfig()

    assert config.input_dir == Path("data/input")
    assert config.output_dir == Path("data/output")
    assert config.google_books_api_base_url == "https://www.googleapis.com/books/v1/volumes"
    assert config.open_library_api_base_url == "https://openlibrary.org/api/books"
