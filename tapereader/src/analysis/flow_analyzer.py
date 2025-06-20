"""
Analisador de fluxo de ordens - Versão Híbrida
Mantém funcionalidades essenciais com código otimizado
"""
import logging
from typing import Dict, List, Optional
from collections import deque, defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

class FlowAnalyzer:
    """Analisa fluxo de agressão com suporte a múltiplos símbolos"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.trade_window_size = config.get('trade_window_size', 200)
        self.absorption_threshold = config.get('absorption_threshold', 1000)
        self.divergence_threshold = config.get('divergence_threshold', 0.6)
        
        # Janelas separadas por símbolo (essencial para arbitragem)
        self.symbol_windows = {
            'WDOFUT': deque(maxlen=self.trade_window_size),
            'DOLFUT': deque(maxlen=self.trade_window_size)
        }
        
        # Delta cumulativo por símbolo
        self.cumulative_delta = {'WDOFUT': 0, 'DOLFUT': 0}
        
        # Importa normalizador se disponível
        try:
            from .volume_normalizer import VolumeNormalizer
            self.normalizer = VolumeNormalizer()
            self.use_normalizer = True
        except ImportError:
            self.normalizer = None
            self.use_normalizer = False
            logger.warning("VolumeNormalizer não disponível, usando volumes brutos")
    
    def analyze_trades(self, trades: List[Dict]) -> Dict:
        """Analisa trades mantendo separação por símbolo"""
        if not trades:
            return self._empty_analysis()
        
        # Normaliza volumes se disponível
        if self.use_normalizer:
            trades = self.normalizer.normalize_trades(trades)
            volume_key = 'normalized_volume'
        else:
            volume_key = 'volume'
        
        # Processa trades por símbolo
        for trade in trades:
            symbol = trade.get('symbol')
            if symbol in self.symbol_windows:
                self.symbol_windows[symbol].append(trade)
                
                # Atualiza delta
                delta = trade[volume_key] if trade['side'] == 'BUY' else -trade[volume_key]
                self.cumulative_delta[symbol] += delta
        
        # Calcula métricas
        wdo_pressure = self._calculate_pressure('WDOFUT', volume_key)
        dol_pressure = self._calculate_pressure('DOLFUT', volume_key)
        
        # Detecta padrões importantes
        flow_divergence = abs(wdo_pressure - dol_pressure) > self.divergence_threshold
        absorption = self._detect_absorption(volume_key)
        
        # Análise geral
        avg_pressure = (wdo_pressure + dol_pressure) / 2
        dominant_side = self._get_dominant_side(avg_pressure)
        flow_strength = self._get_flow_strength(avg_pressure, absorption)
        
        return {
            'timestamp': datetime.now(),
            'wdo_pressure': wdo_pressure,
            'dol_pressure': dol_pressure,
            'flow_divergence': flow_divergence,
            'absorption_detected': absorption,
            'dominant_side': dominant_side,
            'flow_strength': flow_strength,
            'delta_wdo': self.cumulative_delta['WDOFUT'],
            'delta_dol': self.cumulative_delta['DOLFUT'],
            'avg_pressure': avg_pressure
        }
    
    def _calculate_pressure(self, symbol: str, volume_key: str) -> float:
        """Calcula pressão normalizada (-1 a +1) para um símbolo"""
        trades = list(self.symbol_windows[symbol])
        if len(trades) < 10:
            return 0.0
        
        buy_volume = sum(t[volume_key] for t in trades if t['side'] == 'BUY')
        sell_volume = sum(t[volume_key] for t in trades if t['side'] == 'SELL')
        total_volume = buy_volume + sell_volume
        
        if total_volume == 0:
            return 0.0
        
        return (buy_volume - sell_volume) / total_volume
    
    def _detect_absorption(self, volume_key: str) -> bool:
        """Detecta absorção simplificada mas funcional"""
        for symbol, trades in self.symbol_windows.items():
            if len(trades) < 20:
                continue
            
            recent = list(trades)[-20:]
            total_volume = sum(t[volume_key] for t in recent)
            
            if total_volume < self.absorption_threshold:
                continue
            
            # Verifica variação de preço
            prices = [t['price'] for t in recent]
            if not prices:
                continue
                
            price_range = max(prices) - min(prices)
            avg_price = sum(prices) / len(prices)
            
            # Absorção: alto volume, baixa variação
            if avg_price > 0:
                variation = price_range / avg_price
                if variation < 0.001:  # Menos de 0.1% de variação
                    return True
        
        return False
    
    def _get_dominant_side(self, avg_pressure: float) -> str:
        """Determina lado dominante"""
        if avg_pressure > 0.3:
            return 'BUY'
        elif avg_pressure < -0.3:
            return 'SELL'
        return 'NEUTRAL'
    
    def _get_flow_strength(self, avg_pressure: float, absorption: bool) -> str:
        """Determina força do fluxo"""
        if absorption:
            return 'ABSORPTION'
        elif abs(avg_pressure) > 0.7:
            return 'STRONG'
        elif abs(avg_pressure) > 0.4:
            return 'MODERATE'
        return 'WEAK'
    
    def _empty_analysis(self) -> Dict:
        """Retorna análise vazia com estrutura completa"""
        return {
            'timestamp': datetime.now(),
            'wdo_pressure': 0.0,
            'dol_pressure': 0.0,
            'flow_divergence': False,
            'absorption_detected': False,
            'dominant_side': 'NEUTRAL',
            'flow_strength': 'WEAK',
            'delta_wdo': 0,
            'delta_dol': 0,
            'avg_pressure': 0.0
        }
    
    def reset_session_delta(self):
        """Reseta deltas da sessão"""
        self.cumulative_delta = {'WDOFUT': 0, 'DOLFUT': 0}
        logger.info("Delta cumulativo resetado")
    
    def get_symbol_metrics(self, symbol: str) -> Dict:
        """Retorna métricas específicas de um símbolo"""
        if symbol not in self.symbol_windows:
            return {}
        
        trades = list(self.symbol_windows[symbol])
        if not trades:
            return {}
        
        return {
            'trade_count': len(trades),
            'cumulative_delta': self.cumulative_delta[symbol],
            'last_trade': trades[-1] if trades else None
        }