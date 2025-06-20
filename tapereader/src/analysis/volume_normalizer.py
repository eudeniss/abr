from typing import Dict, List

class VolumeNormalizer:
    """Normaliza o volume de diferentes contratos para uma base comparável."""
    
    # Proporção de 5 WDO para 1 DOL
    VOLUME_WEIGHTS = {
        'WDOFUT': 0.2,
        'DOLFUT': 1.0
    }

    def get_weight(self, symbol: str) -> float:
        """Retorna o peso para um determinado símbolo."""
        return self.VOLUME_WEIGHTS.get(symbol, 1.0)

    def normalize_trades(self, trades: List[Dict]) -> List[Dict]:
        """
        Adiciona um campo 'normalized_volume' a cada trade na lista.
        Retorna uma nova lista de trades com o campo adicionado.
        """
        normalized_list = []
        for trade in trades:
            new_trade = trade.copy()
            weight = self.get_weight(new_trade.get('symbol'))
            new_trade['normalized_volume'] = new_trade.get('volume', 0) * weight
            normalized_list.append(new_trade)
        return normalized_list