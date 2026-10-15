from app.services.memory_pipeline import safe_exception_frames


def _raise_private_error() -> None:
    raise TypeError("patient text must never appear in telemetry")


def test_safe_exception_frames_report_code_location_without_exception_message():
    try:
        _raise_private_error()
    except TypeError as exc:
        rendered = safe_exception_frames(exc)
    else:  # pragma: no cover - the helper must be reached through an exception
        raise AssertionError("expected TypeError")

    assert "_raise_private_error" in rendered
    assert "test_safe_exception_frames.py" in rendered
    assert "patient text must never appear in telemetry" not in rendered
