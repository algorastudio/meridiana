class DictCompatMixin:
    """Aggiunge compatibilità dict ai Dataclass.

    Permette di usare .get(), [] e 'in' come su un dizionario,
    rendendo i Dataclass compatibili con codice che si aspettava dict.
    """
    def get(self, key, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __contains__(self, key):
        return hasattr(self, key)
