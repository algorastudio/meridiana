from dataclasses import dataclass, field
from typing import Optional, Any
from models.base import DictCompatMixin

@dataclass
class Localita(DictCompatMixin):
    id: int
    nome: str
    comune_id: Optional[int] = None
    tipo: Optional[str] = None
    tipo_id: Optional[int] = None
    comune_nome: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Localita':
        """Crea un'istanza di Localita da un dizionario restituito dal DB."""
        valid_keys = cls.__dataclass_fields__.keys()
        
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        
        return cls(**filtered_data)
