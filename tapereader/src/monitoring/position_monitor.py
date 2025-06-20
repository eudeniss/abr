"""
Monitor de Posições para Arbitragem - Versão Otimizada
Mantém simplicidade mas preserva funcionalidades críticas
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class ActivePosition:
    """Representa uma posição ativa"""
    signal_id: str
    signal_type: str  # 'ARBITRAGE' ou 'TAPE_READING'
    entry_time: datetime
    action: str
    entry_price: float
    stop_price: float
    target1: float
    target2: float
    contracts: int
    direction: int  # 1 para COMPRA, -1 para VENDA
    z_score_entry: float = 0.0
    status: str = 'ACTIVE'
    pnl: float = 0.0
    current_price: float = 0.0
    time_in_position: int = 0
    max_favorable: float = 0.0
    max_adverse: float = 0.0
    alerts_sent: List[str] = field(default_factory=list)
    
class PositionMonitor:
    """
    Monitora posições ativas com validações essenciais
    Versão otimizada mantendo funcionalidades críticas
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.active_positions: Dict[str, ActivePosition] = {}
        
        # Configurações
        self.single_position_mode = self.config.get('single_position_mode', True)
        self.max_time_minutes = self.config.get('max_time_minutes', 5)
        self.adverse_threshold = self.config.get('adverse_threshold', 0.5)
        self.tape_adverse_threshold = self.config.get('tape_reading_adverse_threshold', 3.0)
        self.favorable_threshold = self.config.get('favorable_threshold', 0.3)
        self.spread_invalidation = self.config.get('spread_invalidation', 0.5)
        self.no_progress_time = self.config.get('no_progress_time', 120)
        self.point_value = self.config.get('point_value', 10.0)
        
        # Estatísticas
        self.stats = {
            'total_positions': 0,
            'successful_exits': 0,
            'stopped_positions': 0,
            'invalidated_positions': 0,
            'total_pnl': 0.0
        }
        
        mode = "SINGLE" if self.single_position_mode else "MÚLTIPLO"
        logger.info(f"PositionMonitor inicializado - Modo: {mode}")
    
    def has_active_position(self) -> bool:
        """Verifica se há posição ativa"""
        return len(self.active_positions) > 0

    def add_position(self, signal: Dict) -> Tuple[Optional[str], str]:
        """Adiciona nova posição para monitoramento"""
        if self.single_position_mode and self.has_active_position():
            return None, "Modo single: já existe posição ativa."
        
        position = ActivePosition(
            signal_id=signal['signal_id'],
            signal_type=signal.get('source', 'ARBITRAGE'),
            entry_time=datetime.now(),
            action=signal['action'],
            entry_price=signal['entry'],
            stop_price=signal['stop'],
            target1=signal['targets'][0],
            target2=signal['targets'][1],
            contracts=signal['contracts'],
            direction=1 if signal['action'] == 'COMPRA' else -1,
            z_score_entry=signal.get('z_score', 0.0)
        )
        
        self.active_positions[position.signal_id] = position
        self.stats['total_positions'] += 1
        
        logger.info(f"Posição {signal['action']} aberta @ {signal['entry']:.2f}")
        return position.signal_id, f"Posição {signal['action']} DÓLAR aberta @ {signal['entry']}"
    
    def update_position(self, signal_id: Optional[str], current_price: float, 
                       current_spread: float, current_z_score: float) -> Dict:
        """Atualiza posição e verifica invalidações"""
        # Em modo single, pegar primeira posição
        if self.single_position_mode and signal_id is None:
            signal_id = next(iter(self.active_positions), None)
            
        if not signal_id or signal_id not in self.active_positions:
            return {'status': 'NOT_FOUND', 'alerts': [], 'should_exit': False}

        pos = self.active_positions[signal_id]
        pos.current_price = current_price
        pos.time_in_position = int((datetime.now() - pos.entry_time).total_seconds())
        
        # Calcular movimento e P&L
        movement = (current_price - pos.entry_price) * pos.direction
        pos.pnl = movement * pos.contracts * self.point_value
        
        # Atualizar máximos
        pos.max_favorable = max(pos.max_favorable, movement)
        pos.max_adverse = min(pos.max_adverse, movement)
        
        alerts = []
        should_exit = False
        
        # 1. Verificar Stop Loss
        stop_movement = (pos.stop_price - pos.entry_price) * pos.direction
        if movement <= stop_movement:
            pos.status = 'STOPPED'
            should_exit = True
            alerts.append({
                'type': 'STOP_LOSS',
                'severity': 'HIGH',
                'message': f'⛔ STOP LOSS @ {current_price:.2f}!',
                'sound': 'alert_critical'
            })
        
        # 2. Verificar Alvos (se ainda ativo)
        elif pos.status == 'ACTIVE':
            target1_movement = (pos.target1 - pos.entry_price) * pos.direction
            target2_movement = (pos.target2 - pos.entry_price) * pos.direction
            
            if movement >= target2_movement:
                pos.status = 'TARGET2'
                alerts.append({
                    'type': 'TARGET2_REACHED',
                    'severity': 'LOW',
                    'message': f'🎯 Alvo 2 atingido @ {current_price:.2f}!',
                    'sound': 'alert_success'
                })
            elif movement >= target1_movement:
                pos.status = 'TARGET1'
                if 'TARGET1' not in pos.alerts_sent:
                    alerts.append({
                        'type': 'TARGET1_REACHED',
                        'severity': 'LOW',
                        'message': f'✅ Alvo 1 atingido @ {current_price:.2f}!',
                        'sound': 'alert_success'
                    })
                    pos.alerts_sent.append('TARGET1')
        
        # 3. Verificar Invalidações (apenas se ainda ativo)
        if pos.status == 'ACTIVE':
            # Tempo máximo
            if pos.time_in_position > self.max_time_minutes * 60:
                pos.status = 'INVALIDATED'
                should_exit = True
                alerts.append({
                    'type': 'TIME_EXCEEDED',
                    'severity': 'MEDIUM',
                    'message': f'⏰ Tempo máximo ({self.max_time_minutes}min) excedido!',
                    'sound': 'alert_warning'
                })
            
            # Movimento adverso (threshold por tipo)
            adverse_limit = (self.tape_adverse_threshold if pos.signal_type == 'TAPE_READING' 
                           else self.adverse_threshold)
            if abs(pos.max_adverse) > adverse_limit:
                pos.status = 'INVALIDATED'
                should_exit = True
                alerts.append({
                    'type': 'ADVERSE_MOVEMENT',
                    'severity': 'HIGH',
                    'message': f'📉 Movimento adverso: {abs(pos.max_adverse):.2f} pts!',
                    'sound': 'alert_critical'
                })
            
            # Sem progresso
            elif (pos.time_in_position > self.no_progress_time and 
                  pos.max_favorable < self.favorable_threshold and
                  'NO_PROGRESS' not in pos.alerts_sent):
                alerts.append({
                    'type': 'NO_PROGRESS',
                    'severity': 'MEDIUM',
                    'message': f'😴 Sem evolução após {self.no_progress_time}s',
                    'sound': 'alert_warning'
                })
                pos.alerts_sent.append('NO_PROGRESS')
            
            # Spread convergiu (apenas arbitragem)
            if pos.signal_type == 'ARBITRAGE' and 'SPREAD_CONV' not in pos.alerts_sent:
                if ((pos.direction > 0 and current_z_score > -self.spread_invalidation) or
                    (pos.direction < 0 and current_z_score < self.spread_invalidation)):
                    alerts.append({
                        'type': 'SPREAD_CONVERGED',
                        'severity': 'MEDIUM',
                        'message': f'📊 Spread convergiu! Z: {current_z_score:.2f}',
                        'sound': 'alert_warning'
                    })
                    pos.alerts_sent.append('SPREAD_CONV')
        
        # Retornar resultado
        return {
            'position': self._position_to_dict(pos),
            'status': pos.status,
            'pnl': pos.pnl,
            'alerts': alerts,
            'should_exit': should_exit
        }

    def remove_position(self, signal_id: Optional[str], exit_price: float, 
                       reason: str = 'MANUAL') -> Dict:
        """Remove posição e atualiza estatísticas"""
        if self.single_position_mode:
            signal_id = next(iter(self.active_positions), None)
            
        if not signal_id or signal_id not in self.active_positions:
            return {'success': False, 'message': 'Posição não encontrada'}

        pos = self.active_positions.pop(signal_id)
        
        # P&L final
        final_pnl = (exit_price - pos.entry_price) * pos.direction * pos.contracts * self.point_value
        self.stats['total_pnl'] += final_pnl
        
        # Categorizar saída
        if final_pnl > 0:
            self.stats['successful_exits'] += 1
        elif pos.status == 'STOPPED':
            self.stats['stopped_positions'] += 1
        else:
            self.stats['invalidated_positions'] += 1
        
        logger.info(f"Posição fechada: {reason} - P&L: R$ {final_pnl:.2f}")
        
        return {
            'success': True,
            'message': f'Posição fechada: {reason}',
            'summary': {
                'signal_id': pos.signal_id,
                'action': pos.action,
                'entry_price': pos.entry_price,
                'exit_price': exit_price,
                'duration_minutes': pos.time_in_position // 60,
                'pnl': final_pnl,
                'status': pos.status,
                'reason': reason
            }
        }

    def get_first_position_summary(self) -> Optional[Dict]:
        """Retorna resumo da primeira posição ativa"""
        if not self.has_active_position():
            return None
            
        pos = next(iter(self.active_positions.values()))
        return self._position_to_dict(pos)
    
    def get_active_positions_summary(self) -> List[Dict]:
        """Retorna lista com resumo das posições"""
        return [self._position_to_dict(pos) for pos in self.active_positions.values()]
    
    def _position_to_dict(self, pos: ActivePosition) -> Dict:
        """Converte posição para dicionário"""
        return {
            'signal_id': pos.signal_id,
            'action': pos.action,
            'entry_price': pos.entry_price,
            'current_price': pos.current_price,
            'pnl': pos.pnl,
            'time_minutes': pos.time_in_position // 60,
            'time_seconds': pos.time_in_position,
            'status': pos.status,
            'max_favorable': pos.max_favorable,
            'max_adverse': pos.max_adverse
        }

    def get_statistics(self) -> Dict:
        """Retorna estatísticas do monitor"""
        total_closed = (self.stats['successful_exits'] + 
                       self.stats['stopped_positions'] + 
                       self.stats['invalidated_positions'])
        
        return {
            **self.stats,
            'active_positions': len(self.active_positions),
            'has_active_position': self.has_active_position(),
            'win_rate': (self.stats['successful_exits'] / total_closed * 100) if total_closed > 0 else 0,
            'mode': 'SINGLE' if self.single_position_mode else 'MULTIPLE'
        }