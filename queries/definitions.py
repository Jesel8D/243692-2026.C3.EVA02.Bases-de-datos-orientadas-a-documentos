"""Immutable workload files and validated per-operation options."""
from dataclasses import dataclass
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VARIANTS = json.loads((ROOT / 'variants.json').read_text())


class QueryBlocked(ValueError):
    """Missing evidence, incompatible data/configuration or unavailable engine."""


@dataclass(frozen=True)
class QuerySpec:
    engine: str
    query: str
    variant: str
    timeout_ms: int = 120000

    def __post_init__(self):
        if self.engine not in VARIANTS or self.query not in VARIANTS[self.engine]:
            raise QueryBlocked('Unknown engine/query')
        if self.variant not in VARIANTS[self.engine][self.query]:
            raise QueryBlocked('Variant must be explicit and valid for engine/query')
        if type(self.timeout_ms) is not int or not 1 <= self.timeout_ms <= 3600000:
            raise QueryBlocked('timeout-ms must be 1..3600000')

    @property
    def options(self):
        return dict(VARIANTS[self.engine][self.query][self.variant])

    @property
    def pipeline(self):
        return json.loads((ROOT / 'mongodb' / f'{self.query.lower()}.json').read_text())

    @property
    def sql(self):
        return (ROOT / 'postgresql' / f'{self.query.lower()}.sql').read_text().strip().removesuffix(';')
