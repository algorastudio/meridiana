from dataclasses import dataclass, field
from typing import Optional, Any
from models.base import DictCompatMixin

@dataclass
class Documento(DictCompatMixin):
    id: int
    titolo: str
    tipo_documento: str
    descrizione: Optional[str] = None
    anno: Optional[int] = None
    periodo_nome: Optional[str] = None
    percorso_file: Optional[str] = None
    partite_correlate: Optional[str] = None
    rilevanza: Optional[str] = None
    note_legame: Optional[str] = None
    rel_documento_id: Optional[int] = None
    rel_partita_id: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Documento':
        """Crea un'istanza di Documento da un dizionario restituito dal DB."""
        
        mapped_data = {}
        
        mapped_data['id'] = data.get('id') or data.get('documento_id')
        mapped_data['titolo'] = data.get('titolo')
        mapped_data['tipo_documento'] = data.get('tipo_documento')
        mapped_data['descrizione'] = data.get('descrizione')
        mapped_data['anno'] = data.get('anno')
        mapped_data['periodo_nome'] = data.get('periodo_nome') or data.get('nome_periodo')
        mapped_data['percorso_file'] = data.get('percorso_file')
        mapped_data['partite_correlate'] = data.get('partite_correlate')
        mapped_data['rilevanza'] = data.get('rilevanza')
        mapped_data['note_legame'] = data.get('note_legame')
        mapped_data['rel_documento_id'] = data.get('rel_documento_id')
        mapped_data['rel_partita_id'] = data.get('rel_partita_id')
        
        valid_keys = cls.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in mapped_data.items() if k in valid_keys}
        
        return cls(**filtered_data)
