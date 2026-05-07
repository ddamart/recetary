"""Tests for the quantity parser."""
from __future__ import annotations

import pytest

from recetary.quantities import parse_quantity


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("400 gramos", (400.0, "g")),
        ("400 g", (400.0, "g")),
        ("1 sobre", (1.0, "sobre")),
        ("2 sobres", (2.0, "sobre")),
        ("1 unidad", (1.0, "ud")),
        ("3 unidades", (3.0, "ud")),
        ("1 cucharadita", (1.0, "cucharadita")),
        ("2 cucharaditas", (2.0, "cucharadita")),
        ("1/2 cucharada", (0.5, "cucharada")),
        ("1,5 litros", (1.5, "l")),
        ("250 ml", (250.0, "ml")),
        ("1 kg", (1.0, "kg")),
        ("2 dientes", (2.0, "diente")),
        ("al gusto", (None, None)),
        ("", (None, None)),
        (None, (None, None)),
    ],
)
def test_parse_quantity(raw, expected):
    assert parse_quantity(raw) == expected
