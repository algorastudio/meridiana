from dataclasses import dataclass
from typing import Optional, Any
from datetime import date, datetime
from models.base import DictCompatMixin

@dataclass
class Comune(DictCompatMixin):
    id: int
    nome_comune: str
    provincia: str
    regione: str
    codice_catastale: Optional[str] = None
    periodo_id: Optional[int] = None
    data_istituzione: Optional[date] = None
    data_soppressione: Optional[date] = None
    note: Optional[str] = None
    data_creazione: Optional[datetime] = None
    data_modifica: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Comune':
        """Crea un'istanza di Comune da un dizionario (es. da DictCursor)."""
        # Filtra le chiavi extra non presenti nella dataclass per evitare errori
        valid_keys = cls.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        
        # Mappa il campo 'nome' restituito dal database a 'nome_comune'
        if 'nome' in data and 'nome_comune' not in filtered_data:
            filtered_data['nome_comune'] = data['nome']
            
        return cls(**filtered_data)
