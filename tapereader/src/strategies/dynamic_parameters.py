"""
Gerenciador de parâmetros dinâmicos
"""
import logging
from typing import Dict, Optional
from datetime import datetime, time
from collections import deque
import statistics

logger = logging.getLogger(__name__)

class DynamicParameterManager:
    """Ajusta parâmetros baseado em condições de mercado"""
    
    def __init__(self, base_config: Dict):
        self.base_config = base_config.get('arbitrage_enhanced', {}).get('dynamic_parameters', {})
        self.strategy_base_config = base_config.get('arbitrage', {})
        self.current_params = self._get_initial_params()
        
        self.volatility_window = deque(maxlen=200)
        self.volume_window = deque(maxlen=100)
        self.signal_success_window = deque(maxlen=50)
        
        self.last_adjustment = datetime.now()
        self.adjustment_interval = self.base_config.get('adjustment_interval_sec', 300)
        
        self.current_regime = 'NORMAL'
        
        self.time_based_params = self._parse_time_params()
        
        logger.info("Gerenciador de parâmetros dinâmicos inicializado")

    def _get_initial_params(self) -> Dict:
        """Pega os parâmetros iniciais da configuração principal da estratégia"""
        return {
            'STD_THRESHOLD': self.strategy_base_config.get('alerts', {}).get('spread_std_devs', 1.5),
            'MIN_PROFIT_REAIS': self.strategy_base_config.get('detection', {}).get('min_profit_reais', 20.0),
            'SLIPPAGE': self.strategy_base_config.get('detection', {}).get('slippage', 0.5)
        }

    def _parse_time_params(self):
        """Converte strings de tempo da config para objetos time"""
        parsed = {}
        time_config = self.base_config.get('time_based_multipliers', {})
        for name, values in time_config.items():
            if 'start' in values and 'end' in values:
                try:
                    parsed[name] = {
                        'start': time.fromisoformat(values['start']),
                        'end': time.fromisoformat(values['end']),
                        'multiplier': values.get('multiplier', 1.0)
                    }
                except (ValueError, TypeError):
                    logger.error(f"Formato de tempo inválido para {name} na configuração.")
            elif 'multiplier' in values: # Para o 'normal'
                parsed[name] = values
        return parsed
        
    def update_market_data(self, spread: float, volume: int = 0):
        """Atualiza dados de mercado para análise"""
        self.volatility_window.append(spread)
        if volume > 0:
            self.volume_window.append(volume)
            
    def register_signal_result(self, success: bool):
        """Registra resultado de um sinal para aprendizado"""
        self.signal_success_window.append(1 if success else 0)
        
    def should_adjust(self) -> bool:
        """Verifica se deve ajustar parâmetros"""
        if not self.base_config.get('enabled', False) or len(self.volatility_window) < 50:
            return False
        return (datetime.now() - self.last_adjustment).seconds >= self.adjustment_interval
        
    def adjust_parameters(self) -> Dict:
        """Ajusta parâmetros baseado nas condições atuais"""
        if not self.should_adjust():
            return self.current_params
            
        self._detect_market_regime()
        adjustments = self._calculate_adjustments()
        
        gradual_weight = self.base_config.get('gradual_adjustment_weight', 0.3)
        for param, value in adjustments.items():
            if param in self.current_params:
                self.current_params[param] = (self.current_params[param] * (1 - gradual_weight) + value * gradual_weight)
                
        time_multiplier = self._get_time_multiplier()
        for param in self.current_params:
            self.current_params[param] *= time_multiplier
            
        self.last_adjustment = datetime.now()
        logger.info(f"Parâmetros ajustados. Regime: {self.current_regime}")
        
        return self.current_params
        
    def _detect_market_regime(self):
        """Detecta o regime atual do mercado"""
        if len(self.volatility_window) < 100: return

        thresholds = self.base_config.get('regime_detection_thresholds', {})
        recent_vol = statistics.stdev(list(self.volatility_window)[-30:])
        historical_vol = statistics.stdev(self.volatility_window)
        vol_ratio = recent_vol / historical_vol if historical_vol > 0 else 1.0
        
        if vol_ratio > thresholds.get('high_vol_ratio', 1.5):
            self.current_regime = 'high_volatility'
        elif vol_ratio < thresholds.get('low_vol_ratio', 0.7):
            self.current_regime = 'low_volatility'
        else:
            self.current_regime = 'normal'
            
    def _calculate_adjustments(self) -> Dict:
        """Calcula ajustes baseados no regime"""
        initial_params = self._get_initial_params()
        regime_adjustments = self.base_config.get('regime_adjustments', {}).get(self.current_regime, {})
        
        if not regime_adjustments:
            return initial_params # Retorna aos padrões se não houver ajuste de regime

        adjusted_params = {}
        for param, base_value in initial_params.items():
            multiplier = regime_adjustments.get(param, 1.0)
            adjusted_params[param] = base_value * multiplier
            
        return adjusted_params
        
    def _get_time_multiplier(self) -> float:
        """Retorna multiplicador baseado no horário"""
        current_time = datetime.now().time()
        for period in self.time_based_params.values():
            if 'start' in period and period['start'] <= current_time <= period['end']:
                return period['multiplier']
        return self.time_based_params.get('normal', {}).get('multiplier', 1.0)
        
    def get_status(self) -> Dict:
        """Retorna status atual do gerenciador"""
        return {
            'current_regime': self.current_regime,
            'current_parameters': self.current_params.copy(),
            'last_adjustment': self.last_adjustment,
        }