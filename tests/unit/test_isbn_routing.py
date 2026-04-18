from book_store_assistant.config import AppConfig
from book_store_assistant.isbn import registration_group
from book_store_assistant.sources.bne import BneSruSource
from book_store_assistant.sources.isbn_routing import get_national_source
from book_store_assistant.sources.national.argentina import ArgentinaISBNSource
from book_store_assistant.sources.national.base import StubNationalSource
from book_store_assistant.sources.national.brazil import BrazilISBNSource
from book_store_assistant.sources.national.chile import ChileISBNSource
from book_store_assistant.sources.national.colombia import ColombiaISBNSource
from book_store_assistant.sources.national.ecuador import EcuadorISBNSource
from book_store_assistant.sources.national.mexico import MexicoISBNSource
from book_store_assistant.sources.national.peru import PeruISBNSource
from book_store_assistant.sources.national.uruguay import UruguayISBNSource


def _make_config() -> AppConfig:
    return AppConfig(source_request_pause_seconds=0.0)


# ---- registration_group tests ----


def test_registration_group_es() -> None:
    # 978 + 84 prefix -> ES
    assert registration_group("9788408273691") == "ES"


def test_registration_group_mx_607() -> None:
    # 978 + 607 prefix -> MX
    assert registration_group("9786071600011") == "MX"


def test_registration_group_mx_968() -> None:
    # 978 + 968 prefix -> MX
    assert registration_group("9789681105150") == "MX"


def test_registration_group_mx_970() -> None:
    # 978 + 970 prefix -> MX
    assert registration_group("9789701050927") == "MX"


def test_registration_group_ar_950() -> None:
    # 978 + 950 prefix -> AR
    assert registration_group("9789500286442") == "AR"


def test_registration_group_ar_987() -> None:
    # 978 + 987 prefix -> AR
    assert registration_group("9789871234567") == "AR"


def test_registration_group_co() -> None:
    # 978 + 958 prefix -> CO
    assert registration_group("9789581234567") == "CO"


def test_registration_group_cl() -> None:
    # 978 + 956 prefix -> CL
    assert registration_group("9789561234567") == "CL"


def test_registration_group_br_85() -> None:
    # 978 + 85 prefix -> BR
    assert registration_group("9788535914849") == "BR"


def test_registration_group_br_65() -> None:
    # 978 + 65 prefix -> BR
    assert registration_group("9786500000017") == "BR"


def test_registration_group_pe_612() -> None:
    # 978 + 612 prefix -> PE
    assert registration_group("9786121234567") == "PE"


def test_registration_group_pe_9972() -> None:
    # 978 + 9972 prefix -> PE
    assert registration_group("9789972123456") == "PE"


def test_registration_group_ve() -> None:
    # 978 + 980 prefix -> VE
    assert registration_group("9789801234567") == "VE"


def test_registration_group_uy() -> None:
    # 978 + 9974 prefix -> UY
    assert registration_group("9789974123456") == "UY"


def test_registration_group_ec() -> None:
    # 978 + 9978 prefix -> EC
    assert registration_group("9789978123456") == "EC"


def test_registration_group_bo() -> None:
    # 978 + 99954 prefix -> BO
    assert registration_group("9789995412345") == "BO"


def test_registration_group_gt() -> None:
    # 978 + 99922 prefix -> GT
    assert registration_group("9789992212345") == "GT"


def test_registration_group_cr() -> None:
    # 978 + 9968 prefix -> CR
    assert registration_group("9789968123456") == "CR"


def test_registration_group_pa() -> None:
    # 978 + 9962 prefix -> PA
    assert registration_group("9789962123456") == "PA"


def test_registration_group_unknown_prefix_returns_none() -> None:
    # 978 + 0 prefix (English-speaking group) -> None
    assert registration_group("9780306406157") is None


def test_registration_group_isbn10_returns_none() -> None:
    assert registration_group("0306406152") is None


def test_registration_group_invalid_input_returns_none() -> None:
    assert registration_group("not-an-isbn") is None


def test_registration_group_empty_string_returns_none() -> None:
    assert registration_group("") is None


def test_registration_group_strips_hyphens() -> None:
    assert registration_group("978-84-08-27369-1") == "ES"


def test_registration_group_invalid_ean_prefix_returns_none() -> None:
    # Valid 13-digit number but wrong EAN prefix
    assert registration_group("1234567890123") is None


# ---- get_national_source tests ----


def test_get_national_source_es_returns_bne() -> None:
    config = _make_config()
    source = get_national_source("9788408273691", config)

    assert isinstance(source, BneSruSource)


def test_get_national_source_co_returns_colombia() -> None:
    config = _make_config()
    source = get_national_source("9789581234567", config)

    assert isinstance(source, ColombiaISBNSource)


def test_get_national_source_mx_returns_mexico() -> None:
    config = _make_config()
    source = get_national_source("9786071600011", config)

    assert isinstance(source, MexicoISBNSource)


def test_get_national_source_ar_returns_argentina() -> None:
    config = _make_config()
    source = get_national_source("9789500286442", config)

    assert isinstance(source, ArgentinaISBNSource)


def test_get_national_source_cl_returns_chile() -> None:
    config = _make_config()
    source = get_national_source("9789561234567", config)

    assert isinstance(source, ChileISBNSource)


def test_get_national_source_br_returns_brazil() -> None:
    config = _make_config()
    source = get_national_source("9788535914849", config)

    assert isinstance(source, BrazilISBNSource)


def test_get_national_source_pe_returns_peru() -> None:
    config = _make_config()
    source = get_national_source("9786121234567", config)

    assert isinstance(source, PeruISBNSource)


def test_get_national_source_ve_returns_stub_to_avoid_plaintext_http() -> None:
    """Venezuela agency endpoint is HTTP-only; we route 980 ISBNs to the stub."""
    config = _make_config()
    source = get_national_source("9789801234567", config)

    assert isinstance(source, StubNationalSource)
    assert source.country_code == "VE"


def test_get_national_source_uy_returns_uruguay() -> None:
    config = _make_config()
    source = get_national_source("9789974123456", config)

    assert isinstance(source, UruguayISBNSource)


def test_get_national_source_ec_returns_ecuador() -> None:
    config = _make_config()
    source = get_national_source("9789978123456", config)

    assert isinstance(source, EcuadorISBNSource)


def test_get_national_source_bo_returns_stub() -> None:
    config = _make_config()
    source = get_national_source("9789995412345", config)

    assert isinstance(source, StubNationalSource)
    assert source.country_code == "BO"


def test_get_national_source_gt_returns_stub() -> None:
    config = _make_config()
    source = get_national_source("9789992212345", config)

    assert isinstance(source, StubNationalSource)
    assert source.country_code == "GT"


def test_get_national_source_cr_returns_stub() -> None:
    config = _make_config()
    source = get_national_source("9789968123456", config)

    assert isinstance(source, StubNationalSource)
    assert source.country_code == "CR"


def test_get_national_source_pa_returns_stub() -> None:
    config = _make_config()
    source = get_national_source("9789962123456", config)

    assert isinstance(source, StubNationalSource)
    assert source.country_code == "PA"


def test_get_national_source_unknown_returns_none() -> None:
    config = _make_config()
    result = get_national_source("9780306406157", config)

    assert result is None


def test_get_national_source_isbn10_returns_none() -> None:
    config = _make_config()
    result = get_national_source("0306406152", config)

    assert result is None
