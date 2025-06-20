"""
Detector Simplificado de Defesa de Preço/Renovação
Detecta quando alguém está segurando preço em região
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

class PriceDefenseDetector:
    """
    Detecta defesa de preço e renovação de ordens
    Simplificado para uso em arbitragem
    """
    
    def __init__(self, config: Dict = None):
        config = config or {}
        self.config = config
        
        # Configurações gerais
        self.track_levels = config.get('track_levels', 3)
        self.time_window = config.get('time_window_seconds', 30)
        self.min_renovations = config.get('min_renovations', 3)
        self.significant_size_dol = config.get('significant_size_dol', 100)
        self.significant_size_wdo = config.get('significant_size_wdo', 400)
        
        # Sub-configurações
        self.rules = config.get('classification_rules', {})
        self.strength_config = config.get('strength_calculation', {})
        self.renovation_config = config.get('renovation_detection', {})
        
        self.level_history = defaultdict(lambda: defaultdict(deque))
        self.defense_zones = defaultdict(dict)
        
    def detect(self, book: Dict, symbol: str) -> Optional[Dict]:
        """Detecta defesa de preço no book"""
        if not book or not book.get('bids') or not book.get('asks'):
            return None
            
        current_time = datetime.now()
        defenses = []
        
        for i, bid in enumerate(book['bids'][:self.track_levels]):
            if self._is_significant_level(bid, symbol):
                defense = self._check_price_defense(symbol, bid['price'], bid['volume'], 'bid', current_time)
                if defense: defenses.append(defense)
                    
        for i, ask in enumerate(book['asks'][:self.track_levels]):
            if self._is_significant_level(ask, symbol):
                defense = self._check_price_defense(symbol, ask['price'], ask['volume'], 'ask', current_time)
                if defense: defenses.append(defense)
                    
        self._cleanup_old_data(symbol, current_time)
        
        if defenses:
            strongest = max(defenses, key=lambda d: d['strength'])
            strongest['type'] = 'price_defense'
            return strongest
            
        return None
        
    def _is_significant_level(self, level: Dict, symbol: str) -> bool:
        min_size = self.significant_size_dol if 'DOL' in symbol else self.significant_size_wdo
        return level.get('volume', 0) >= min_size
        
    def _check_price_defense(self, symbol: str, price: float, volume: int, 
                           side: str, current_time: datetime) -> Optional[Dict]:
        """Verifica se há defesa de preço neste nível"""
        history = self.level_history[symbol][price]
        history.append({'time': current_time, 'volume': volume, 'side': side})
        
        cutoff = current_time - timedelta(seconds=self.time_window)
        while history and history[0]['time'] < cutoff:
            history.popleft()
            
        if len(history) < 3: return None
            
        renovations = self._count_renovations(history, symbol)
        
        if renovations >= self.min_renovations:
            total_volume = sum(h['volume'] for h in history)
            avg_volume = total_volume / len(history)
            persistence = (history[-1]['time'] - history[0]['time']).total_seconds()
            defense_type = self._classify_defense(renovations, persistence)
            strength = self._calculate_strength(renovations, persistence, avg_volume, symbol)
            
            return {
                'price_level': price, 'side': 'COMPRA' if side == 'bid' else 'VENDA',
                'defense_type': defense_type, 'renovations': renovations,
                'avg_volume': avg_volume, 'total_volume': total_volume,
                'persistence_seconds': persistence, 'strength': strength,
                'direction': 'support' if side == 'bid' else 'resistance',
                'symbol': symbol,
                'description': self._format_description(defense_type, symbol, price, side)
            }
        return None
        
    def _count_renovations(self, history: deque, symbol: str) -> int:
        """Conta renovações/reposições de volume"""
        if len(history) < 2: return 0
        renovations = 0
        min_size = self.significant_size_dol if 'DOL' in symbol else self.significant_size_wdo
        quick_replacement_time = self.renovation_config.get('quick_replacement_time_sec', 5)

        for i in range(1, len(history)):
            prev, curr = history[i-1], history[i]
            if curr['volume'] > prev['volume'] + (min_size * 0.5):
                renovations += 1
            elif prev['volume'] > min_size and curr['volume'] > min_size * 0.8:
                if (curr['time'] - prev['time']).total_seconds() < quick_replacement_time:
                    renovations += 1
        return renovations
        
    def _classify_defense(self, renovations: int, persistence: float) -> str:
        """Classifica o tipo de defesa com base nas regras da config"""
        if renovations >= self.rules.get('aggressive_renovations', 5) and persistence < self.rules.get('aggressive_persistence_sec', 20):
            return "aggressive_defense"
        elif renovations >= self.rules.get('active_renovations', 3) and persistence < self.rules.get('active_persistence_sec', 30):
            return "active_defense"
        elif persistence > self.rules.get('passive_persistence_sec', 20):
            return "passive_accumulation"
        return "position_holding"
            
    def _calculate_strength(self, renovations: int, persistence: float, 
                          avg_volume: float, symbol: str) -> float:
        """Calcula força da defesa de preço com pesos da config"""
        score = 0.0
        
        w_reno = self.strength_config.get('renovation_weight', 40)
        w_pers = self.strength_config.get('persistence_weight', 30)
        w_vol = self.strength_config.get('volume_weight', 30)
        
        reno_div = self.strength_config.get('renovation_divisor_factor', 2.0)
        vol_div = self.strength_config.get('volume_divisor_factor', 2.0)

        reno_score = min(renovations / (self.min_renovations * reno_div), 1.0)
        score += reno_score * w_reno
        
        if persistence > 0:
            persist_score = min(persistence / self.time_window, 1.0)
            score += persist_score * w_pers
            
        expected_vol = self.significant_size_dol if 'DOL' in symbol else self.significant_size_wdo
        vol_score = min(avg_volume / (expected_vol * vol_div), 1.0)
        score += vol_score * w_vol
        
        return min(score, 100)
        
    def _format_description(self, defense_type: str, symbol: str, price: float, side: str) -> str:
        """Formata descrição da defesa"""
        level_type = "suporte" if side == 'bid' else "resistência"
        descriptions = {
            'aggressive_defense': f"Defesa agressiva de {level_type} em {symbol} @ {price:.2f}",
            'active_defense': f"Defesa ativa de {level_type} em {symbol} @ {price:.2f}",
            'passive_accumulation': f"Acumulação passiva em {symbol} @ {price:.2f}",
            'position_holding': f"Manutenção de posição em {symbol} @ {price:.2f}"
        }
        return descriptions.get(defense_type, f"Defesa em {symbol} @ {price:.2f}")
        
    def _cleanup_old_data(self, symbol: str, current_time: datetime):
        """Remove dados antigos"""
        cutoff = current_time - timedelta(seconds=self.time_window * 2)
        
        prices_to_remove = [
            price for price, history in list(self.level_history[symbol].items())
            if not history or history[-1]['time'] < cutoff
        ]
        for price in prices_to_remove:
            del self.level_history[symbol][price]