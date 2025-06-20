"""
Analisador de Tape Reading - Versão Híbrida
Mantém simplicidade com funcionalidades essenciais
CORREÇÃO: Adiciona contador total de trades processados
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time
from collections import deque

logger = logging.getLogger(__name__)

class TapeReadingAnalyzer:
    """Analisa tape reading para gerar sinais direcionais seguindo o fluxo"""
    
    def __init__(self, config: Dict = None):
        config = config or {}
        self.config = config
        
        # MUDANÇA: Armazenamento acumulativo em vez de janela deslizante
        self.all_trades = []  # TODOS os trades da sessão
        self.analysis_window = config.get('analysis_window', 200)  # Últimos N para análise de pressão
        self.min_trades_for_signal = config.get('min_trades_for_signal', 50)  # Aumentado de 20
        self.min_pressure_ratio = config.get('min_pressure_ratio', 1.5)
        
        self.time_context_config = config.get('time_context', {})
        self.use_time_context = self.time_context_config.get('enabled', True)
        
        try:
            from .volume_normalizer import VolumeNormalizer
            self.normalizer = VolumeNormalizer()
            self.use_normalizer = True
        except ImportError:
            self.normalizer = None
            self.use_normalizer = False
            
        self.metrics = {
            'last_signal_time': None,
            'signal_cooldown': config.get('signal_cooldown_sec', 60),
            'total_signals': 0,
            'session_start': datetime.now()
        }
        
        logger.info(f"TapeReadingAnalyzer inicializado - Modo ACUMULATIVO - Janela análise: {self.analysis_window}")
    
    def analyze_trades(self, all_trades: List[Dict], current_price: float) -> Tuple[Optional[Dict], str]:
        """Analisa trades com abordagem ACUMULATIVA"""
        if not all_trades:
            return None, "Sem trades para análise"
        
        if self.use_normalizer:
            trades = self.normalizer.normalize_trades(all_trades)
            volume_key = 'normalized_volume'
        else:
            trades = all_trades
            volume_key = 'volume'
        
        # MUDANÇA: Adiciona NOVOS trades ao acumulativo
        for trade in trades:
            # Evita duplicatas verificando se já existe
            trade_key = (trade.get('timestamp'), trade.get('symbol'), trade.get('side'), trade.get('price'))
            if not any(
                (t.get('timestamp'), t.get('symbol'), t.get('side'), t.get('price')) == trade_key 
                for t in self.all_trades[-10:]  # Verifica apenas últimos 10 para performance
            ):
                self.all_trades.append(trade)
            
        total_trades = len(self.all_trades)
        
        if total_trades < self.min_trades_for_signal:
            return None, f"Aguardando trades: {total_trades}/{self.min_trades_for_signal}"
        
        if self._in_cooldown():
            remaining = self._cooldown_remaining()
            return None, f"Em cooldown ({remaining}s)"
        
        # ANÁLISE: Usa últimos N trades para pressão, mas considera contexto total
        analysis_trades = self.all_trades[-self.analysis_window:] if len(self.all_trades) > self.analysis_window else self.all_trades
        analysis = self._analyze_market_pressure(analysis_trades, volume_key)
        
        # CONTEXTO: Também analisa tendência geral da sessão
        session_context = self._analyze_session_context(self.all_trades, volume_key)
        analysis.update(session_context)
        
        time_context = self._get_time_context() if self.use_time_context else {'multiplier': 1.0}
        min_ratio = self.min_pressure_ratio * time_context.get('multiplier', 1.0)
        
        if analysis['count_ratio'] < min_ratio:
            return None, f"Pressão insuficiente: {analysis['count_ratio']:.1f}x < {min_ratio:.1f}x (Sessão: {analysis.get('session_bias', 'NEUTRO')})"
        
        signal = self._generate_signal(analysis, current_price, time_context)
        if signal:
            self.metrics['last_signal_time'] = datetime.now()
            self.metrics['total_signals'] += 1
            reason = self._format_reason(analysis, signal)
            return signal, reason
            
        return None, "Condições não atendidas"
    
    def _analyze_market_pressure(self, trades: List[Dict], volume_key: str) -> Dict:
        """Analisa pressão dos últimos N trades (mais responsivo)"""
        if not trades: 
            return {}

        buy_count = sum(1 for t in trades if self._is_buy_aggression(t))
        sell_count = sum(1 for t in trades if self._is_sell_aggression(t))
        
        dominant = 'BUY' if buy_count > sell_count else 'SELL'
        count_ratio = buy_count / max(sell_count, 1) if dominant == 'BUY' else sell_count / max(buy_count, 1)
        
        buy_volume = sum(t.get(volume_key, 0) for t in trades if self._is_buy_aggression(t))
        sell_volume = sum(t.get(volume_key, 0) for t in trades if self._is_sell_aggression(t))
        
        return {
            'dominant_side': dominant,
            'count_ratio': count_ratio,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'analysis_period': 'RECENT'
        }
    
    def _analyze_session_context(self, all_trades: List[Dict], volume_key: str) -> Dict:
        """Analisa contexto geral da sessão (tendência maior)"""
        if len(all_trades) < 100:  # Mínimo para análise de sessão
            return {'session_bias': 'INSUFICIENTE', 'session_strength': 0}
        
        # Analisa TODA a sessão
        total_buy_vol = sum(t.get(volume_key, 0) for t in all_trades if self._is_buy_aggression(t))
        total_sell_vol = sum(t.get(volume_key, 0) for t in all_trades if self._is_sell_aggression(t))
        
        total_vol = total_buy_vol + total_sell_vol
        if total_vol == 0:
            return {'session_bias': 'NEUTRO', 'session_strength': 0}
        
        buy_pct = (total_buy_vol / total_vol) * 100
        sell_pct = (total_sell_vol / total_vol) * 100
        
        # Determina viés da sessão
        if buy_pct > 60:
            bias = 'BULLISH'
            strength = buy_pct - 50  # 0-50 scale
        elif sell_pct > 60:
            bias = 'BEARISH' 
            strength = sell_pct - 50
        else:
            bias = 'NEUTRO'
            strength = 0
            
        return {
            'session_bias': bias,
            'session_strength': strength,
            'session_buy_pct': buy_pct,
            'session_sell_pct': sell_pct,
            'total_session_volume': total_vol,
            'session_trades_count': len(all_trades)
        }

    def _is_buy_aggression(self, trade: Dict) -> bool:
        return trade.get('side') == 'COMPRADOR' and trade.get('aggressor', True)
    
    def _is_sell_aggression(self, trade: Dict) -> bool:
        return trade.get('side') == 'VENDEDOR' and trade.get('aggressor', True)
    
    def _get_time_context(self) -> Dict:
        """Contexto simplificado de horário com base na configuração"""
        now = datetime.now().time()
        for key, params in self.time_context_config.items():
            if key == 'enabled': continue
            if isinstance(params, dict) and 'start' in params and 'end' in params:
                 if time.fromisoformat(params['start']) <= now <= time.fromisoformat(params['end']):
                     return params
        return self.time_context_config.get('normal_period', {'period': 'NORMAL', 'multiplier': 1.0, 'confidence_adj': 0})
    
    def _generate_signal(self, analysis: Dict, current_price: float, time_context: Dict) -> Optional[Dict]:
        """Gera sinal seguindo o fluxo dominante"""
        conf_logic = self.config.get('confidence_logic', {})
        
        if analysis['count_ratio'] >= conf_logic.get('high_ratio_threshold', 2.5):
            confidence = conf_logic.get('high_confidence_level', 85)
        elif analysis['count_ratio'] >= conf_logic.get('medium_ratio_threshold', 2.0):
            confidence = conf_logic.get('medium_confidence_level', 75)
        elif analysis['count_ratio'] >= conf_logic.get('low_ratio_threshold', 1.5):
            confidence = conf_logic.get('low_confidence_level', 65)
        else:
            confidence = conf_logic.get('base_confidence', 60)
        
        if self.use_time_context:
            confidence += time_context.get('confidence_adj', 0)
        
        contracts = 10 if confidence >= 70 else 5
        direction = 'COMPRA' if analysis['dominant_side'] == 'BUY' else 'VENDA'
        
        risk_mgmt = self.config.get('risk_management', {})
        risk_percent = risk_mgmt.get('risk_percent', 0.15)
        target_percent = risk_mgmt.get('target_percent', 0.25)
        
        entry = current_price
        if direction == 'COMPRA':
            stop = entry * (1 - risk_percent / 100)
            target2 = entry * (1 + target_percent / 100)
        else:
            stop = entry * (1 + risk_percent / 100)
            target2 = entry * (1 - target_percent / 100)
        target1 = entry + (target2 - entry) / 2

        point_value = 10.0
        risk_points = abs(stop - entry)
        profit_points = abs(target2 - entry)
        
        return {
            'action': direction, 'asset': 'DÓLAR', 'entry': entry,
            'targets': [round(target1, 2), round(target2, 2)], 'stop': round(stop, 2),
            'confidence': confidence, 'contracts': contracts,
            'expected_profit': profit_points * point_value * contracts,
            'risk': risk_points * point_value * contracts,
            'risk_reward': profit_points / risk_points if risk_points > 0 else 1.0,
            'source': 'TAPE_READING',
            'gatilhos': [f"Fluxo {analysis['dominant_side']} {analysis['count_ratio']:.1f}x"]
        }
    
    def _format_reason(self, analysis: Dict, signal: Dict) -> str:
        session_info = f"(Sessão: {analysis.get('session_bias', 'N/A')} {analysis.get('session_strength', 0):.0f}%)"
        return f"{signal['action']} por Tape Reading - Pressão {analysis['count_ratio']:.1f}x - Confiança {signal['confidence']}% {session_info}"
    
    def _in_cooldown(self) -> bool:
        if not self.metrics['last_signal_time']: return False
        return (datetime.now() - self.metrics['last_signal_time']).seconds < self.metrics['signal_cooldown']
    
    def _cooldown_remaining(self) -> int:
        if not self.metrics['last_signal_time']: return 0
        elapsed = (datetime.now() - self.metrics['last_signal_time']).seconds
        return max(0, self.metrics['signal_cooldown'] - elapsed)
    
    def cleanup_old_trades(self, max_trades: int = 5000):
        """
        Remove trades muito antigos para evitar uso excessivo de memória
        Mantém os últimos max_trades trades
        """
        if len(self.all_trades) > max_trades:
            trades_to_remove = len(self.all_trades) - max_trades
            self.all_trades = self.all_trades[trades_to_remove:]
            logger.info(f"Limpeza: removidos {trades_to_remove} trades antigos, mantidos {len(self.all_trades)}")
    
    def reset_session(self):
        """Reseta a sessão (útil para novo dia de trading)"""
        self.all_trades.clear()
        self.metrics['session_start'] = datetime.now()
        self.metrics['total_signals'] = 0
        self.metrics['last_signal_time'] = None
        logger.info("Sessão de tape reading resetada")
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas completas da sessão (análise acumulativa)"""
        total_trades = len(self.all_trades)
        
        if total_trades == 0: 
            return {
                'has_data': False,
                'total_trades_session': 0,
                'analysis_window_size': self.analysis_window,
                'mode': 'ACUMULATIVO'
            }
        
        # Análise de toda a sessão
        buy_trades = sum(1 for t in self.all_trades if self._is_buy_aggression(t))
        sell_trades = sum(1 for t in self.all_trades if self._is_sell_aggression(t))
        
        session_duration = (datetime.now() - self.metrics['session_start']).total_seconds() / 60
        
        # Análise dos últimos trades (para pressão atual)
        recent_trades = self.all_trades[-self.analysis_window:] if len(self.all_trades) > self.analysis_window else self.all_trades
        recent_buy = sum(1 for t in recent_trades if self._is_buy_aggression(t))
        recent_sell = sum(1 for t in recent_trades if self._is_sell_aggression(t))
        recent_total = len(recent_trades)
        
        return {
            'has_data': True,
            'mode': 'ACUMULATIVO',
            
            # Estatísticas da sessão completa
            'total_trades_session': total_trades,
            'session_buy_percentage': (buy_trades / total_trades) * 100 if total_trades > 0 else 0,
            'session_sell_percentage': (sell_trades / total_trades) * 100 if total_trades > 0 else 0,
            'session_duration_minutes': session_duration,
            'trades_per_minute': total_trades / max(1, session_duration),
            
            # Análise da janela recente (para sinais)
            'analysis_window_size': self.analysis_window,
            'recent_trades_count': recent_total,
            'buy_percentage': (recent_buy / recent_total) * 100 if recent_total > 0 else 0,
            'sell_percentage': (recent_sell / recent_total) * 100 if recent_total > 0 else 0,
            
            # Sinais gerados
            'total_signals': self.metrics['total_signals'],
            
            # Comparação sessão vs recente
            'session_vs_recent_buy_diff': ((recent_buy / recent_total) - (buy_trades / total_trades)) * 100 if total_trades > 0 and recent_total > 0 else 0
        }