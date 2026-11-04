"""Read interface metrics with explicit chain roles and ambiguity checks."""

from __future__ import annotations

import math
from pathlib import Path

METRICS = ("ipSAE", "ipSAE_d0chn", "ipSAE_d0dom", "ipTM_af", "ipTM_d0chn",
           "pDockQ", "pDockQ2", "LIS")


def read_interface_metrics(path: str | Path, binder_chains: list[str] | None = None,
                           target_chains: list[str] | None = None,
                           allow_missing: bool = True) -> dict:
    lines = [line.split() for line in Path(path).read_text().splitlines() if line.strip()]
    if not lines:
        if allow_missing:
            return {}
        raise ValueError("Missing interface score table")
    header = lines[0]
    if not {"Chn1", "Chn2", "Type"} <= set(header):
        raise ValueError("Interface table is missing chain or Type columns")
    if any(len(row) != len(header) for row in lines[1:]):
        raise ValueError("Malformed interface score row")
    rows = [dict(zip(header, row)) for row in lines[1:]]
    rows = [row for row in rows if row["Type"] == "min"]
    if bool(binder_chains) != bool(target_chains):
        raise ValueError("Both binder and target chains are required")
    if binder_chains:
        binders, targets = set(binder_chains), set(target_chains)
        if binders & targets:
            raise ValueError("Binder and target chains overlap")
        rows = [row for row in rows if
                (row["Chn1"] in binders and row["Chn2"] in targets) or
                (row["Chn2"] in binders and row["Chn1"] in targets)]
    elif len(rows) > 1:
        raise ValueError("Ambiguous interfaces: provide explicit binder and target chains")
    if not rows:
        if allow_missing:
            return {}
        raise ValueError("Requested binder-target interface is missing")
    pairs = [tuple(sorted((row["Chn1"], row["Chn2"]))) for row in rows]
    if len(pairs) != len(set(pairs)):
        raise ValueError("Duplicate min rows for an interface")
    result = {}
    for metric in METRICS:
        values = []
        for row in rows:
            if metric not in row or row[metric] in ("", "NA", "nan", "None"):
                continue
            try:
                value = float(row[metric])
            except ValueError as exc:
                raise ValueError("Invalid interface metric") from exc
            if not math.isfinite(value):
                raise ValueError("Non-finite interface metric")
            values.append(value)
        if len(values) == len(rows):
            result[metric] = min(values)
    if not allow_missing and "ipSAE" not in result:
        raise ValueError("Requested interface metric is missing")
    result["interface_aggregation"] = "single_pair" if len(rows) == 1 else "pairwise_min_not_union"
    result["interface_pairs"] = ",".join(":".join(pair) for pair in sorted(pairs))
    return result
