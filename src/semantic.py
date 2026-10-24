"""Minimal semantic layer: reads dbt-MetricFlow-style YAML and compiles governed metric queries.

Supports simple metrics (sum, count, count_distinct, average, min, max), ratio metrics, time grouping
(day, week, month, quarter, year) on the model's aggregation time dimension, and categorical
dimensions reached through a shared entity (e.g. country, via the customer entity).
It is NOT MetricFlow: no cumulative or derived metrics, no multi-hop joins, only a date-range filter.
Identifiers come from the YAML; user input is validated against it or passed as bound parameters.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import yaml
from sqlalchemy import text

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "semantic" / "semantic_layer.yml"
GRANULARITIES = ("day", "week", "month", "quarter", "year")
AGGS = {"sum": "sum({e})", "count": "count({e})", "count_distinct": "count(distinct {e})",
        "average": "avg({e})", "min": "min({e})", "max": "max({e})"}
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_ROWS = 50


class SemanticLayer:
    def __init__(self, path=DEFAULT_PATH, schema: str = "analytics"):
        cfg = yaml.safe_load(Path(path).read_text())
        self.schema = schema
        self.models = {m["name"]: m for m in cfg["semantic_models"]}
        self.metrics = {m["name"]: m for m in cfg["metrics"]}
        self.measures = {meas["name"]: (mn, meas) for mn, m in self.models.items() for meas in m.get("measures", [])}
        for m in self.models.values():
            for ident in [self._table_name(m)] + [self._col(e) for e in m.get("entities", [])]:
                if not IDENT.match(ident):
                    raise ValueError(f"Unsafe identifier in semantic layer: {ident!r}")

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _table_name(model: dict) -> str:
        return re.search(r"ref\('([^']+)'\)", model["model"]).group(1)

    @staticmethod
    def _col(item: dict) -> str:
        return item.get("expr") or item["name"]

    def _time_dim(self, model: dict) -> str:
        name = model["defaults"]["agg_time_dimension"]
        dim = next(d for d in model["dimensions"] if d["name"] == name)
        return self._col(dim)

    def _resolve(self, metric: str):
        """Returns (owner model, aggregate SQL fragment using alias m)."""
        m = self.metrics[metric]
        if m["type"] == "simple":
            owner, meas = self.measures[m["type_params"]["measure"]]
            return self.models[owner], AGGS[meas["agg"]].format(e=f"m.{self._col(meas)}")
        if m["type"] == "ratio":
            (o1, n), (o2, d) = (self._resolve(m["type_params"][k]) for k in ("numerator", "denominator"))
            if o1["name"] != o2["name"]:
                raise ValueError("Ratio metrics must use measures from one semantic model.")
            return o1, f"({n})::float / nullif(({d}), 0)"
        raise ValueError(f"Unsupported metric type: {m['type']}")

    def _categorical(self, owner: dict, name: str):
        """Returns (select expression, join clause or '')."""
        for mn, model in self.models.items():
            dim = next((d for d in model.get("dimensions", []) if d["name"] == name and d["type"] == "categorical"), None)
            if not dim:
                continue
            if mn == owner["name"]:
                return f"m.{self._col(dim)}", ""
            for e in owner.get("entities", []):
                match = next((x for x in model["entities"] if x["name"] == e["name"] and x["type"] == "primary"), None)
                if match:
                    table = f"{self.schema}.{self._table_name(model)}"
                    return f"d.{self._col(dim)}", f"join {table} d on m.{self._col(e)} = d.{self._col(match)}"
        raise ValueError(f"Dimension {name!r} is not reachable from this metric.")

    # -- public API ------------------------------------------------------
    def dimensions_for(self, metric: str) -> list[str]:
        owner, _ = self._resolve(metric)
        cats = []
        for model in self.models.values():
            for d in model.get("dimensions", []):
                if d["type"] == "categorical":
                    try:
                        self._categorical(owner, d["name"])
                        cats.append(d["name"])
                    except ValueError:
                        pass
        return list(GRANULARITIES) + cats

    def list_metrics(self) -> list[dict]:
        out = []
        for name, m in self.metrics.items():
            owner, _ = self._resolve(name)
            out.append({"metric": name, "description": m.get("description", ""),
                        "group_by": self.dimensions_for(name),
                        "date_filter_applies_to": self._time_dim(owner)})
        return out

    def compile(self, metric: str, group_by: str | None = None, start: str | None = None, end: str | None = None):
        if metric not in self.metrics:
            raise ValueError(f"Unknown metric {metric!r}. Known: {sorted(self.metrics)}")
        owner, agg = self._resolve(metric)
        if group_by and group_by not in self.dimensions_for(metric):
            raise ValueError(f"Cannot group {metric!r} by {group_by!r}. Options: {self.dimensions_for(metric)}")
        tcol = self._time_dim(owner)
        join, grp = "", "'all'"
        if group_by in GRANULARITIES:
            grp = f"date_trunc('{group_by}', m.{tcol})::date"
        elif group_by:
            grp, join = self._categorical(owner, group_by)
        where, params = [], {}
        for key, val, op in (("s", start, ">="), ("e", end, "<")):
            if val:
                params[key] = dt.date.fromisoformat(val)
                where.append(f"m.{tcol} {op} :{key}")
        sql = (f"select {grp} as grp, {agg} as value from {self.schema}.{self._table_name(owner)} m {join} "
               f"{'where ' + ' and '.join(where) if where else ''} group by 1 order by 1 limit {MAX_ROWS}")
        return " ".join(sql.split()), params

    def query(self, engine, metric: str, group_by: str | None = None, start: str | None = None, end: str | None = None):
        sql, params = self.compile(metric, group_by, start, end)
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        return [{"group": str(r[0]), "value": None if r[1] is None else round(float(r[1]), 2)} for r in rows]
