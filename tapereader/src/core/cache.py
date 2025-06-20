"""
Sistema de cache para o Tape Reader
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class CacheManager:
    """Gerenciador de cache"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cache_dir = config.get('cache_dir', './data/cache')
        self.memory_cache = {}
        self._ensure_cache_dir()
        
    def _ensure_cache_dir(self):
        """Garante que o diretório de cache existe"""
        os.makedirs(self.cache_dir, exist_ok=True)
        
    async def initialize(self):
        """Inicializa o cache"""
        logger.info(f"Cache inicializado em {self.cache_dir}")
        
    async def update_market_data(self, data: Dict[str, Any]):
        """Atualiza dados de mercado no cache"""
        self.memory_cache['market_data'] = data
        self.memory_cache['last_update'] = datetime.now()
        
    async def get_market_data(self) -> Optional[Dict[str, Any]]:
        """Obtém dados de mercado do cache"""
        return self.memory_cache.get('market_data')
        
    async def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache"""
        return {
            'memory_items': len(self.memory_cache),
            'memory_size_mb': 0.1,  # Simplificado
            'last_update': self.memory_cache.get('last_update')
        }
        
    async def cleanup(self):
        """Limpa cache antigo"""
        pass
        
    async def close(self):
        """Fecha o cache"""
        logger.info("Cache fechado")