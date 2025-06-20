import logging
from typing import Dict

logger = logging.getLogger(__name__)

class SystemStateValidator:
    """
    Valida a integridade contínua do sistema, verificando a consistência
    entre os diferentes módulos e fluxos de dados.
    (Implementação inicial)
    """

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.error_counts = {}

    def validate_market_data(self, market_data) -> bool:
        """Valida a integridade dos dados de mercado recebidos."""
        if not market_data:
            logger.warning("Validação falhou: MarketData está nulo.")
            return False
        
        if not market_data.wdo_book.get('bids') or not market_data.dol_book.get('bids'):
            logger.warning("Validação falhou: Book de ofertas incompleto.")
            return False
            
        return True

    def validate_signal_integrity(self, signal: Dict) -> bool:
        """Valida se um sinal gerado contém todos os campos necessários."""
        required_keys = ['action', 'asset', 'entry', 'targets', 'stop', 'confidence', 'contracts']
        
        if not all(key in signal for key in required_keys):
            logger.error(f"Sinal com integridade comprometida: {signal}")
            return False
            
        return True