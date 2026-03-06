from __future__ import annotations

from typing import ClassVar

import fast_app
from fast_app import ASC, DESC, Index, Model


class Invoice(Model):
    indexes: ClassVar[list[Index]] = [
        Index(
            keys=[("business_id", ASC), ("created_at", DESC)],
            name="invoice_business_created_at",
        )
    ]


def test_model_indexes_are_declared_and_not_fillable_fields() -> None:
    assert Invoice.indexes[0].name == "invoice_business_created_at"
    assert "indexes" not in Invoice.model_fields()
    assert "indexes" not in Invoice.fillable_fields()


def test_fast_app_exports_index_symbols() -> None:
    assert fast_app.ASC == 1
    assert fast_app.DESC == -1
    assert fast_app.Index is Index
