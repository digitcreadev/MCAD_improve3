from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FrozenTemplatePhysicalSpec:
    template_id: str
    logical_sha256: str
    grain: str
    product_category: str


_SPECS = (
    FrozenTemplatePhysicalSpec(
        "AW_ATOM_COST",
        "071b2b794a255198e80cdfc6637241379abeaf7af54b90e9af59633d418269ce",
        "MONTH",
        "Bikes",
    ),
    FrozenTemplatePhysicalSpec(
        "AW_ATOM_MARGIN",
        "18c1b6f720b21d8df5014848a0f14854dc65dbe2d550656cdc7772fa41225fb1",
        "MONTH",
        "Bikes",
    ),
    FrozenTemplatePhysicalSpec(
        "AW_ATOM_SALES",
        "636f9472760e9dd80366d58b6af3547c9cd1b6c961b33b005d3cf7afb0114bea",
        "MONTH",
        "Bikes",
    ),
    FrozenTemplatePhysicalSpec(
        "AW_BAD_GRAIN_YEAR",
        "149043d18621295ea264cd9da6a58f79affe249cb64d19d6c0b746b03aa22172",
        "YEAR",
        "Bikes",
    ),
    FrozenTemplatePhysicalSpec(
        "AW_DISTRACTOR_ACCESSORIES_SALES",
        "fe1e6f4a076f7e63e0408ee5cb43f923e517046b3aba1bad48e462946497003f",
        "MONTH",
        "Accessories",
    ),
    FrozenTemplatePhysicalSpec(
        "AW_MIX_ACCESSORIES_SALES_COST",
        "b536e8c4f30c69f17c2a87332a5d2c9cf9cd318931548ef10cc989aa7dde4133",
        "MONTH",
        "Accessories",
    ),
    FrozenTemplatePhysicalSpec(
        "AW_PAIR_SALES_COST",
        "f7f79c1b84a526910a423062ff35fd9f0aed5cdd588818e53fa9176cca9c8361",
        "MONTH",
        "Bikes",
    ),
)

_BY_SHA = {s.logical_sha256: s for s in _SPECS}
if len(_BY_SHA) != 7:
    raise RuntimeError("frozen physical mapping cardinality != 7")


def logical_mdx_sha256(mdx: str) -> str:
    return hashlib.sha256(str(mdx).encode("utf-8")).hexdigest()


def physicalize_frozen_adventureworks_mdx(logical_mdx: str) -> tuple[str, dict[str, str]]:
    text = str(logical_mdx)
    digest = logical_mdx_sha256(text)
    spec = _BY_SHA.get(digest)
    if spec is None:
        raise RuntimeError(
            "R3-E14 physical MDX compatibility overlay refuses unknown logical MDX "
            f"sha256={digest}"
        )

    m = re.search(r"(?is)\bselect\s+(?P<measures>.*?)\s+on\s+columns", text)
    if not m:
        raise RuntimeError(f"cannot extract measures for frozen template {spec.template_id}")
    measures = m.group("measures").strip()

    if spec.grain == "MONTH":
        date_rows = "[Date.Calendar].[2013].Children"
    elif spec.grain == "YEAR":
        date_rows = "{[Date.Calendar].[2013]}"
    else:
        raise RuntimeError(f"unsupported frozen grain {spec.grain!r}")

    if spec.product_category not in {"Bikes", "Accessories"}:
        raise RuntimeError(f"unsupported frozen product category {spec.product_category!r}")

    physical = f"""SELECT {measures} ON COLUMNS,
NonEmpty(
  CrossJoin(
    {date_rows},
    Descendants([Sales Territory].[Europe], [Sales Territory].[Sales Territory Region])
  ),
  {measures}
) ON ROWS
FROM [Adventure Works DW]
WHERE ([Product].[{spec.product_category}])"""

    return physical, {
        "template_id": spec.template_id,
        "logical_sha256": digest,
        "grain": spec.grain,
        "product_category": spec.product_category,
    }
