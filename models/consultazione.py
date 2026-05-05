from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import date
from models.base import DictCompatMixin

@dataclass
class Consultazione(DictCompatMixin):
    id: int
    data: Optional[date] = None
    richiedente: Optional[str] = None
    documento_identita: Optional[str] = None
    motivazione: Optional[str] = None
    materiale_consultato: Optional[str] = None
    funzionario_autorizzante: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Consultazione':
        """Crea un'istanza di Consultazione da un dizionario restituito dal DB."""
        
        # Mappatura dei campi con nomi diversi nelle viste/query SQL (se ce ne sono in futuro)
        mapped_data = {}
        
        mapped_data['id'] = data.get('id')
        mapped_data['data'] = data.get('data') or data.get('data_consultazione')
        mapped_data['richiedente'] = data.get('richiedente')
        mapped_data['documento_identita'] = data.get('documento_identita')
        mapped_data['motivazione'] = data.get('motivazione')
        mapped_data['materiale_consultato'] = data.get('materiale_consultato')
        mapped_data['funzionario_autorizzante'] = data.get('funzionario_autorizzante')
        
        valid_keys = cls.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in mapped_data.items() if k in valid_keys}
        
        return cls(**filtered_data)
