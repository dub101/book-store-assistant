from book_store_assistant.sources.results import FetchResult


class StubNationalSource:
    def __init__(self, country_code: str) -> None:
        self.source_name = f"national_{country_code.lower()}"
        self.country_code = country_code

    def fetch(self, isbn: str) -> FetchResult:
        return FetchResult(
            isbn=isbn,
            record=None,
            errors=[],
            issue_codes=[f"{self.source_name.upper()}_NOT_IMPLEMENTED"],
        )
