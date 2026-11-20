"""``pab cache`` header auth for the LINZ Data Service (mocked HTTP, no network)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Self

import pytest

from pab import cache
from pab import io as pio

URL = (
    "https://data.linz.govt.nz/services/wfs?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=layer-52181&outputFormat=json&count=1000&startIndex=0"
)
SRC = {
    "source_id": "niu-linz-island-polygons-topo",
    "auth": {
        "type": "header",
        "name": "Authorization",
        "value_env": "LINZ_API_KEY",
        "prefix": "key ",
    },
}


class _Resp:
    status_code = 200
    headers: ClassVar[dict[str, str]] = {
        "Content-Length": "2",
        "Content-Type": "application/json",
    }

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, _chunk: int) -> list[bytes]:
        return [b"{}"]


@pytest.fixture
def no_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("LINZ_API_KEY", raising=False)
    monkeypatch.setattr(pio, "ROOT", str(tmp_path))  # no .env here
    return tmp_path


def test_linz_header_sent_and_file_named(
    no_env: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("LINZ_API_KEY", "s3cret")
    seen: dict[str, Any] = {}

    def fake_get(url: str, **kw: Any) -> _Resp:  # noqa: ANN401
        seen.update(url=url, headers=kw["headers"])
        return _Resp()

    monkeypatch.setattr(cache.requests, "get", fake_get)
    headers = cache.auth_headers(SRC, URL)
    path, _ = cache._download(URL, no_env, headers)
    assert seen["headers"]["Authorization"] == "key s3cret"
    assert seen["url"] == URL  # the key is never put in the URL
    assert path.name == "layer-52181.geojson"
    assert "s3cret" not in caplog.text


def test_linz_host_gets_default_auth_without_register_block(
    no_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (no_env / ".env").write_text('# local secrets\nLINZ_API_KEY="from-dotenv"\n')
    assert cache.auth_headers({"source_id": "x"}, URL) == {
        "Authorization": "key from-dotenv"
    }
    assert cache.auth_headers({"source_id": "x"}, "https://example.org/a.zip") == {}


def test_missing_key_fails_clearly(no_env: Path) -> None:
    with pytest.raises(RuntimeError, match="LINZ_API_KEY"):
        cache.auth_headers(SRC, URL)


def test_linz_registers_declare_auth() -> None:
    from pab import registry

    for iso3, sid in (
        ("COK", "cok-linz-island-polygons-topo"),
        ("NIU", "niu-linz-island-polygons-topo"),
        ("TKL", "tkl-linz-island-polygons-topo"),
    ):
        src = next(
            s for s in registry.load_register(iso3)["sources"] if s["source_id"] == sid
        )
        assert src["auth"]["value_env"] == "LINZ_API_KEY"
