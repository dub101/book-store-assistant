import httpx


def classify_http_issue(source_name: str, exc: httpx.HTTPError) -> list[str]:
    normalized_source = source_name.upper()

    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        codes = [f"{normalized_source}_HTTP_{status_code}"]
        if status_code == 429:
            codes.append(f"{normalized_source}_RATE_LIMITED")
        return codes

    if isinstance(exc, httpx.TimeoutException):
        return [f"{normalized_source}_TIMEOUT"]

    if isinstance(exc, httpx.RequestError):
        return [f"{normalized_source}_REQUEST_ERROR"]

    return [f"{normalized_source}_FETCH_ERROR"]


def no_match_issue_code(source_name: str) -> str:
    return f"{source_name.upper()}_NO_MATCH"


def format_issue_detail(issue_code: str) -> str:
    return f"Source issue: {issue_code}."
