from __future__ import annotations

import copy

import r3_e11_xmla_live_executor as frozen_e11
from r3_e14_xmla_physical_mdx_compat import physicalize_frozen_adventureworks_mdx


_ORIGINAL_POST_JSON = frozen_e11.post_json


def _post_json_with_physical_xmla_compat(
    url: str,
    payload: dict,
    timeout_s: float = 180.0,
) -> dict:
    # Keep all MCAD gate/session traffic byte-for-byte logical.
    # Translate only the physical XMLA full-execute request.
    if str(url).rstrip("/").endswith(str(frozen_e11.FULL_PATH)):
        outbound = copy.deepcopy(payload)
        logical = str(outbound.get("mdx") or "")
        physical, _meta = physicalize_frozen_adventureworks_mdx(logical)
        outbound["mdx"] = physical
        return _ORIGINAL_POST_JSON(url, outbound, timeout_s=timeout_s)

    return _ORIGINAL_POST_JSON(url, payload, timeout_s=timeout_s)


# Monkeypatch only the frozen executor's POST transport symbol.
# All planning, arm order, timing, accounting, restart policy, receipts,
# validation, and gate semantics remain owned by the frozen E11 executor.
frozen_e11.post_json = _post_json_with_physical_xmla_compat


def main() -> None:
    frozen_e11.main()


if __name__ == "__main__":
    main()
