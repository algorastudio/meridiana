from dataclasses import dataclass, field
from typing import Optional, Any, List
from datetime import datetime

@dataclass
class Possessore:
    id: int
    nome_completo: str
    cognome_nome: str
    attivo: bool = True
    paternita: Optional[str] = None
    comune_id: Optional[int] = None
    comune_nome: Optional[str] = None
    
    # Campi accessori recuperati dalle JOIN
    num_partite: Optional[int] = None
    comune_riferimento_id: Optional[int] = None
    comune_riferimento_nome: Optional[str] = None
    
    # Date di sistema
    data_creazione: Optional[datetime] = None
    data_modifica: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Possessore':
        """Crea un'istanza di Possessore da un dizionario (es. da DictCursor)."""
        valid_keys = cls.__dataclass_fields__.keys()
        
        # Mappa alcune chiavi che potrebbero avere nomi diversi nelle query
        if 'comune_riferimento_id' in data and 'comune_id' not in data:
            data['comune_id'] = data['comune_riferimento_id']
        if 'comune_riferimento_nome' in data and 'comune_nome' not in data:
            data['comune_nome'] = data['comune_riferimento_nome']

        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        
        return cls(**filtered_data)
