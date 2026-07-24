"""Read-only source-system adapters."""

from evidence_routing.adapters.base import RegulatoryCorpusAdapter
from evidence_routing.adapters.chemical import ChemicalSafetyAdapter
from evidence_routing.adapters.pharma import PharmaceuticalRegulatoryAdapter

__all__ = [
    "ChemicalSafetyAdapter",
    "PharmaceuticalRegulatoryAdapter",
    "RegulatoryCorpusAdapter",
]
