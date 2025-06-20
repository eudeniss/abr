# src/data/provider.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class DataProvider(ABC):
    """Classe base abstrata para todos os provedores de dados."""
    def __init__(self, config: Dict[str, Any], cache: Any = None):
        self.config = config
        self.cache = cache
    @abstractmethod
    def initialize(self) -> None: pass
    @abstractmethod
    def close(self) -> None: pass
    @abstractmethod
    def get_market_snapshot(self) -> Optional[Dict[str, Any]]: pass