from dataclasses import dataclass, field
from typing import Optional, Any, List
from datetime import date, datetime

@dataclass
class Partita:
    id: int
    comune_id: int
    numero_partita: int
    suffisso_partita: Optional[str] = None
    tipo: Optional[str] = None
    stato: Optional[str] = None
    data_impianto: Optional[date] = None
    data_chiusura: Optional[date] = None
    numero_provenienza: Optional[int] = None
    data_creazione: Optional[datetime] = None
    data_modifica: Optional[datetime] = None
    
    # Extra fields that might come from joins or aggregations
    comune_nome: Optional[str] = None
    num_possessori: Optional[int] = None
    num_immobili: Optional[int] = None
    num_documenti_allegati: Optional[int] = None
    
    # Nested related lists (dicts for now, later Dataclasses)
    possessori: List[dict] = field(default_factory=list)
    immobili: List[dict] = field(default_factory=list)
    variazioni: List[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Partita':
        """Crea un'istanza di Partita da un dizionario (es. da DictCursor)."""
        valid_keys = cls.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        
        return cls(**filtered_data)
