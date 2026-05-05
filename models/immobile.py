from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime
from models.base import DictCompatMixin

@dataclass
class Immobile(DictCompatMixin):
    id: int
    natura: str
    partita_id: Optional[int] = None
    localita_id: Optional[int] = None
    classificazione: Optional[str] = None
    consistenza: Optional[str] = None
    numero_piani: Optional[str] = None
    numero_vani: Optional[str] = None
    
    # Campi accessori da JOIN
    localita_nome: Optional[str] = None
    localita_tipo: Optional[str] = None
    tipo_localita: Optional[str] = None  # Alias per localita_tipo
    numero_partita: Optional[int] = None
    suffisso_partita: Optional[str] = None
    comune_nome: Optional[str] = None
    id_immobile: Optional[int] = None  # Usato a volte in viste esportazione
    possessori_attuali: Optional[str] = None  # Da ricerca_avanzata_immobili_gui
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Immobile':
        """Crea un'istanza di Immobile da un dizionario restituito dal DB."""
        valid_keys = cls.__dataclass_fields__.keys()
        
        # Mappa alcune chiavi che potrebbero avere nomi diversi
        if 'id_immobile' in data and 'id' not in data:
            data['id'] = data['id_immobile']
        if 'tipo_localita' in data and 'localita_tipo' not in data:
            data['localita_tipo'] = data['tipo_localita']
        elif 'localita_tipo' in data and 'tipo_localita' not in data:
            data['tipo_localita'] = data['localita_tipo']

        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        
        return cls(**filtered_data)
