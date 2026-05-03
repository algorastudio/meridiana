from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import date

@dataclass
class Variazione:
    id: int
    tipo: str
    data_variazione: Optional[date] = None
    partita_origine_id: Optional[int] = None
    partita_origine_numero: Optional[int] = None
    comune_origine: Optional[str] = None
    possessori_origine: Optional[str] = None
    
    partita_destinazione_id: Optional[int] = None
    partita_destinazione_numero: Optional[int] = None
    comune_destinazione: Optional[str] = None
    possessori_destinazione: Optional[str] = None
    
    numero_riferimento: Optional[str] = None
    nominativo_riferimento: Optional[str] = None
    
    tipo_contratto: Optional[str] = None
    data_contratto: Optional[date] = None
    notaio: Optional[str] = None
    repertorio: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Variazione':
        """Crea un'istanza di Variazione da un dizionario restituito dal DB."""
        
        # Mappatura dei campi con nomi diversi nelle viste/query SQL
        mapped_data = {}
        
        # ID variazione
        mapped_data['id'] = data.get('id') or data.get('variazione_id')
        
        # Tipo variazione
        mapped_data['tipo'] = data.get('tipo') or data.get('tipo_variazione')
        
        # Dati base
        mapped_data['data_variazione'] = data.get('data_variazione')
        mapped_data['numero_riferimento'] = data.get('numero_riferimento')
        mapped_data['nominativo_riferimento'] = data.get('nominativo_riferimento')
        
        # Origine
        mapped_data['partita_origine_id'] = data.get('partita_origine_id')
        mapped_data['partita_origine_numero'] = data.get('partita_origine_numero')
        mapped_data['comune_origine'] = data.get('comune_origine') or data.get('partita_origine_comune') or data.get('comune_nome')
        mapped_data['possessori_origine'] = data.get('possessori_origine')
        
        # Destinazione
        mapped_data['partita_destinazione_id'] = data.get('partita_destinazione_id')
        mapped_data['partita_destinazione_numero'] = data.get('partita_destinazione_numero') or data.get('partita_dest_numero')
        mapped_data['comune_destinazione'] = data.get('comune_destinazione') or data.get('partita_dest_comune') or data.get('comune_dest')
        mapped_data['possessori_destinazione'] = data.get('possessori_destinazione') or data.get('possessori_dest')
        
        # Contratto
        mapped_data['tipo_contratto'] = data.get('tipo_contratto') or data.get('contratto_tipo')
        mapped_data['data_contratto'] = data.get('data_contratto')
        mapped_data['notaio'] = data.get('notaio')
        mapped_data['repertorio'] = data.get('repertorio')
        
        valid_keys = cls.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in mapped_data.items() if k in valid_keys}
        
        return cls(**filtered_data)
