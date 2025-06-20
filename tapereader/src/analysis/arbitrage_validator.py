"""
Validador de oportunidades de arbitragem
Corrigido para aceitar threshold dinâmico baseado no perfil ativo
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import statistics
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado da validação de uma oportunidade"""
    direction: str  # COMPRA ou VENDA
    confidence: int  # 60-95
    expected_profit: float
    risk: float
    contracts: int
    z_score: float
    entry_spread: float
    target_spread: float
    stop_spread: float
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return {
            'direction': self.direction,
            'confidence': self.confidence,
            'expected_profit': self.expected_profit,
            'risk': self.risk,
            'contracts': self.contracts,
            'z_score': self.z_score,
            'entry_spread': self.entry_spread,
            'target_spread': self.target_spread,
            'stop_spread': self.stop_spread
        }


class SignalFormatter:
    """Formata sinais de trading para o formato esperado pelo sistema"""
    
    def format_signal(self, validation_result: ValidationResult, entry_price: float) -> Dict:
        """Formata o resultado da validação em um sinal completo"""
        # Calcula alvos e stop baseados no spread
        if validation_result.direction == 'COMPRA':
            target1 = entry_price + 0.20  # Alvo 1: +20 cents
            target2 = entry_price + 0.40  # Alvo 2: +40 cents
            stop = entry_price - 0.30     # Stop: -30 cents
        else:
            target1 = entry_price - 0.20  # Alvo 1: -20 cents
            target2 = entry_price - 0.40  # Alvo 2: -40 cents
            stop = entry_price + 0.30     # Stop: +30 cents
        
        return {
            'action': validation_result.direction,
            'asset': 'DÓLAR',
            'entry': entry_price,
            'targets': [target1, target2],
            'stop': stop,
            'confidence': validation_result.confidence,
            'contracts': validation_result.contracts,
            'expected_profit': validation_result.expected_profit,
            'risk': validation_result.risk,
            'gatilhos': [
                f"Z-Score: {validation_result.z_score:+.2f}σ",
                f"Confiança: {validation_result.confidence}%"
            ]
        }


class ArbitrageValidator:
    """Valida oportunidades de arbitragem usando análise estatística"""
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Thresholds de Z-score para diferentes níveis de confiança
        self.THRESHOLD_LOW = config.get('threshold_low', 1.2)
        self.THRESHOLD_MEDIUM = config.get('threshold_medium', 1.5)
        self.THRESHOLD_HIGH = config.get('threshold_high', 2.0)
        self.THRESHOLD_EXTREME = config.get('threshold_extreme', 2.5)
        
        # Parâmetros de validação
        self.MIN_STD_DEV = config.get('min_std_dev', 0.05)
        self.MAX_SPREAD_ABS = config.get('max_spread_abs', 5.0)
        self.MIN_PROFIT_REAIS = config.get('min_profit_reais', 20.0)
        
        # Contratos por nível de confiança
        self.contracts_map = {
            'LOW': config.get('contracts_low', 1),
            'MEDIUM': config.get('contracts_medium', 2),
            'HIGH': config.get('contracts_high', 3),
            'EXTREME': config.get('contracts_extreme', 5)
        }
        
        # Valor do ponto do contrato (para cálculos de P&L)
        self.point_value = config.get('point_value', 10.0)
    
    def _calculate_confidence(self, z_score_abs: float) -> int:
        """Calcula nível de confiança baseado no Z-score"""
        if z_score_abs >= self.THRESHOLD_EXTREME:
            return 95
        elif z_score_abs >= self.THRESHOLD_HIGH:
            return 85
        elif z_score_abs >= self.THRESHOLD_MEDIUM:
            return 75
        else:
            return 65
    
    def _get_contracts(self, z_score_abs: float) -> int:
        """Determina número de contratos baseado no Z-score"""
        if z_score_abs >= self.THRESHOLD_EXTREME:
            return self.contracts_map['EXTREME']
        elif z_score_abs >= self.THRESHOLD_HIGH:
            return self.contracts_map['HIGH']
        elif z_score_abs >= self.THRESHOLD_MEDIUM:
            return self.contracts_map['MEDIUM']
        else:
            return self.contracts_map['LOW']
    
    def validate_opportunity(
        self, 
        entry_spread: float, 
        mean_spread: float, 
        std_spread: float,
        z_score: float, 
        spread_history: List[float],
        active_threshold: Optional[float] = None  # CORREÇÃO: Novo parâmetro
    ) -> Tuple[bool, Optional[ValidationResult], str]:
        """
        Valida uma oportunidade de arbitragem
        
        Args:
            entry_spread: Spread atual
            mean_spread: Média histórica do spread
            std_spread: Desvio padrão do spread
            z_score: Z-score atual
            spread_history: Histórico de spreads
            active_threshold: Threshold do perfil ativo (se fornecido)
            
        Returns:
            (is_valid, result, reason)
        """
        z_score_abs = abs(z_score)
        
        # CORREÇÃO: Usa o threshold do perfil ativo se fornecido
        entry_threshold = active_threshold if active_threshold is not None else self.THRESHOLD_LOW
        
        # Validação 1: Z-score mínimo
        if z_score_abs < entry_threshold:
            return False, None, f"Z-score {z_score:.2f} abaixo do mínimo {entry_threshold:.2f}"
        
        # Validação 2: Volatilidade mínima
        if std_spread < self.MIN_STD_DEV:
            return False, None, f"Volatilidade muito baixa: {std_spread:.4f}"
        
        # Validação 3: Spread absoluto máximo
        if abs(entry_spread) > self.MAX_SPREAD_ABS:
            return False, None, f"Spread absoluto muito alto: {entry_spread:.2f}"
        
        # Determina direção (spread alto = vender DOL, spread baixo = comprar DOL)
        direction = "VENDA" if z_score > 0 else "COMPRA"
        
        # Calcula parâmetros do trade
        confidence = self._calculate_confidence(z_score_abs)
        contracts = self._get_contracts(z_score_abs)
        
        # Calcula lucro esperado e risco
        expected_move = abs(entry_spread - mean_spread)
        expected_profit = expected_move * contracts * self.point_value
        
        # Risco = movimento de 1 desvio padrão contra a posição
        risk = std_spread * contracts * self.point_value
        
        # Validação 4: Lucro mínimo
        if expected_profit < self.MIN_PROFIT_REAIS:
            return False, None, f"Lucro esperado abaixo do mínimo: R$ {expected_profit:.2f}"
        
        # Calcula alvos e stops baseados em estatística
        if direction == "COMPRA":
            target_spread = mean_spread  # Alvo: retorno à média
            stop_spread = entry_spread - (2 * std_spread)  # Stop: 2 std abaixo
        else:
            target_spread = mean_spread  # Alvo: retorno à média
            stop_spread = entry_spread + (2 * std_spread)  # Stop: 2 std acima
        
        result = ValidationResult(
            direction=direction,
            confidence=confidence,
            expected_profit=expected_profit,
            risk=risk,
            contracts=contracts,
            z_score=z_score,
            entry_spread=entry_spread,
            target_spread=target_spread,
            stop_spread=stop_spread
        )
        
        reason = f"Oportunidade de {direction} com Z-score de {z_score:.2f}σ (Confiança: {confidence}%)"
        logger.info(f"✅ Validação aprovada: {reason}")
        
        return True, result, reason