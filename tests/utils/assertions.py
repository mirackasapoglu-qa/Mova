"""Testlerde tekrar eden dogrulama yardimcilari."""
from jsonschema import validate, ValidationError


def assert_status(response, expected):
    """Beklenen HTTP status kodunu dogrular, hata halinde govdeyi gosterir."""
    assert response.status_code == expected, (
        f"Beklenen {expected}, gelen {response.status_code}. "
        f"Govde: {response.text[:500]}"
    )


def assert_schema(payload, schema):
    """JSON payload'i verilen semaya gore dogrular."""
    try:
        validate(instance=payload, schema=schema)
    except ValidationError as e:
        raise AssertionError(f"Sema dogrulama hatasi: {e.message}\nYol: {list(e.path)}")


def assert_response_time(response, max_seconds):
    """Yanit suresinin esik altinda kaldigini dogrular."""
    elapsed = response.elapsed.total_seconds()
    assert elapsed <= max_seconds, f"Yanit {elapsed:.2f}s surdu, esik {max_seconds}s"
