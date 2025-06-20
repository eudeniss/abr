"""
Behaviors simplificados para arbitragem - Versão Funcionalmente Completa

Restaura a lógica dos detectores de Absorção e Institucional de forma
simplificada, mantendo a detecção de Exaustão/Pullback aprimorada.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import statistics

from .price_defense_detector import PriceDefenseDetector

logger = logging.getLogger(__name__)


class SimplifiedAbsorptionDetector:
    """Detecta absorção de forma simplificada mas funcional."""
    
    def __init__(self, config: Dict[str, Any]):
        self.volume_threshold_ratio = config.get('volume_threshold_ratio', 3.0) 
        self.price_impact_max_ticks = config.get('price_impact_max_ticks', 2)
        self.min_trades = config.get('min_trades_for_detection', 15)
        
    def detect(self, trades: List[Dict[str, Any]]) -> Optional[Dict]:
        """Detecta absorção (alto volume, baixo impacto no preço)."""
        if len(trades) < self.min_trades: return None

        buy_vol = sum(t.get('normalized_volume', t['volume']) for t in trades if t['side'] == 'BUY')
        sell_vol = sum(t.get('normalized_volume', t['volume']) for t in trades if t['side'] == 'SELL')
        
        prices = [t['price'] for t in trades]
        price_range = max(prices) - min(prices)

        # Absorção de Compra (muita venda, preço não cai)
        if sell_vol > buy_vol * self.volume_threshold_ratio and price_range <= self.price_impact_max_ticks * 0.5:
            return { 'type': 'absorption', 'direction': 'COMPRA', 'strength': 70, 
                     'description': 'Absorção de venda detectada' }
            
        # Absorção de Venda (muita compra, preço não sobe)
        if buy_vol > sell_vol * self.volume_threshold_ratio and price_range <= self.price_impact_max_ticks * 0.5:
            return { 'type': 'absorption', 'direction': 'VENDA', 'strength': 70,
                     'description': 'Absorção de compra detectada' }

        return None


class SimplifiedExhaustionDetector:
    """Detecta exaustão REAL vs PULLBACK temporário."""
    
    def __init__(self, config: Dict[str, Any]):
        self.trend_lookback = config.get('trend_lookback', 20)
        self.trend_config = config.get('trend_detection', {})
        self.momentum_config = config.get('momentum_analysis', {})
        
    def detect(self, trades: List[Dict[str, Any]]) -> Optional[Dict]:
        """Detecta exaustão diferenciando de pullback."""
        if len(trades) < self.trend_lookback: return None
            
        trend_direction, trend_strength = self._identify_main_trend(trades)
        if trend_direction == 'LATERAL': return None

        recent_movement = self._analyze_recent_movement(trades, trend_direction)

        if trend_strength > 0.6 and 0 < recent_movement['retracement'] < 0.382:
            return {
                'type': 'pullback', 'trend_direction': trend_direction, 'strength': trend_strength * 100,
                'signal': trend_direction, 'description': f"Pullback em tendência de {trend_direction}"
            }
        
        if recent_movement['losing_momentum'] and (recent_movement['retracement'] > 0.618 or recent_movement['divergence_detected']):
            signal_direction = 'VENDA' if trend_direction == 'COMPRA' else 'COMPRA'
            return {
                'type': 'exhaustion', 'direction': trend_direction, 'strength': (1 - trend_strength) * 100,
                'signal': signal_direction, 'description': f"Exaustão de {trend_direction}"
            }
                
        return None
        
    def _identify_main_trend(self, trades: List[Dict]) -> Tuple[str, float]:
        """Identifica tendência principal e sua força."""
        prices = [t['price'] for t in trades]
        fast_ma_period = self.trend_config.get('fast_ma_period', 5)
        slow_ma_period = self.trend_config.get('slow_ma_period', 15)

        if len(prices) < slow_ma_period: return 'LATERAL', 0.0
        
        fast_ma = statistics.mean(prices[-fast_ma_period:])
        slow_ma = statistics.mean(prices[-slow_ma_period:])
        
        buy_mult = self.trend_config.get('buy_threshold_multiplier', 1.0005)
        sell_mult = self.trend_config.get('sell_threshold_multiplier', 0.9995)

        strength = abs(fast_ma - slow_ma) / slow_ma if slow_ma > 0 else 0
        if fast_ma > slow_ma * buy_mult: direction = 'COMPRA'
        elif fast_ma < slow_ma * sell_mult: direction = 'VENDA'
        else: direction = 'LATERAL'
        return direction, min(1.0, strength * 100)
        
    def _analyze_recent_movement(self, trades: List[Dict], trend_direction: str) -> Dict:
        """Analisa movimento recente para detectar perda de momentum."""
        all_prices = [t['price'] for t in trades]
        high, low, current = max(all_prices), min(all_prices), all_prices[-1]
        
        retracement = 0
        if high > low:
            if trend_direction == 'COMPRA': retracement = (high - current) / (high - low)
            else: retracement = (current - low) / (high - low)

        lookback = self.momentum_config.get('lookback_period', 10)
        retracement_threshold = self.momentum_config.get('retracement_threshold', 0.236)
        recent_trades = trades[-lookback:]
        price_moves_up = recent_trades[-1]['price'] > recent_trades[0]['price']
        
        buy_vol = sum(t.get('normalized_volume', t['volume']) for t in recent_trades if t['side']=='BUY')
        sell_vol = sum(t.get('normalized_volume', t['volume']) for t in recent_trades if t['side']=='SELL')
        volume_moves_up = buy_vol > sell_vol
        divergence = price_moves_up != volume_moves_up
        
        return {
            'losing_momentum': retracement > retracement_threshold or divergence,
            'retracement': retracement, 'divergence_detected': divergence
        }


class InstitutionalDetector:
    """Detecta atividade institucional (trades grandes)."""
    
    def __init__(self, config: Dict[str, Any]):
        self.institutional_size = config.get('institutional_size', 500)
        self.dominance_ratio = config.get('dominance_ratio', 1.5)
        self.strength_multiplier = config.get('strength_multiplier', 20)
        
    def detect(self, trades: List[Dict[str, Any]]) -> Optional[Dict]:
        """Detecta lotes grandes e o lado dominante."""
        large_trades = [t for t in trades if t.get('normalized_volume', t['volume']) >= self.institutional_size]
        if not large_trades: return None
        
        buy_vol = sum(t.get('normalized_volume', t['volume']) for t in large_trades if t['side'] == 'BUY')
        sell_vol = sum(t.get('normalized_volume', t['volume']) for t in large_trades if t['side'] == 'SELL')
        
        if buy_vol > sell_vol * self.dominance_ratio:
            direction = 'COMPRA'
            strength = min(100, (buy_vol / (sell_vol + 1)) * self.strength_multiplier)
        elif sell_vol > buy_vol * self.dominance_ratio:
            direction = 'VENDA'
            strength = min(100, (sell_vol / (buy_vol + 1)) * self.strength_multiplier)
        else:
            return None
        
        return { 'type': 'institutional', 'direction': direction, 'strength': strength,
                 'description': f'Atividade institucional de {direction}'}


class SimplifiedBehaviorManager:
    """Gerenciador de behaviors com todos os detectores funcionais."""
    
    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.absorption_detector = SimplifiedAbsorptionDetector(config.get('absorption', {}))
        self.exhaustion_detector = SimplifiedExhaustionDetector(config.get('exhaustion', {}))
        self.institutional_detector = InstitutionalDetector(config.get('institutional', {}))
        self.price_defense_detector = PriceDefenseDetector(config.get('price_defense', {}))
        logger.info("SimplifiedBehaviorManager inicializado com detectores funcionais.")
        
    def analyze_symbol(self, all_trades: List[Dict[str, Any]], symbol: str) -> Dict[str, Optional[Dict]]:
        """Analisa trades de um símbolo e retorna behaviors detectados."""
        results = {}
        symbol_trades = [t for t in all_trades if t.get('symbol') == symbol]
        if not symbol_trades: return results

        absorption = self.absorption_detector.detect(symbol_trades)
        if absorption: results['absorption'] = absorption
            
        institutional = self.institutional_detector.detect(symbol_trades)
        if institutional: results['institutional'] = institutional
            
        exhaustion = self.exhaustion_detector.detect(symbol_trades)
        if exhaustion: results['exhaustion'] = exhaustion
                
        return results
    
    def detect_price_defense(self, book: Dict, symbol: str) -> Optional[Dict]:
        """Detecta defesa de preço no book."""
        return self.price_defense_detector.detect(book, symbol)