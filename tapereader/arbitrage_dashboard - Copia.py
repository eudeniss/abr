#!/usr/bin/env python
"""
Analisador de Arbitragem WDO/DOL - Versão 5.2 com Perfis de Trading

Sistema com suporte a múltiplos perfis de trading configuráveis via YAML
Corrigido: Ordem de inicialização e imports
"""
import asyncio
import sys
import os
import hashlib
from datetime import datetime
from collections import deque
import statistics
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# Logger integrado já garante estrutura de logs
from src.core.logger import get_logger, ensure_log_structure

# Importações do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.core.config import ConfigManager
from src.core.cache import CacheManager
from src.data.excel_provider import ExcelDataProvider
from src.analysis.flow_analyzer import FlowAnalyzer
from src.analysis.liquidity_analyzer import LiquidityAnalyzer
from src.ui.rich_display import RichEnhancedDisplay
from src.strategies.dynamic_parameters import DynamicParameterManager
from src.analysis.arbitrage_validator import ArbitrageValidator, SignalFormatter
from src.logging.signal_logger import SignalLogger, SignalHistoryManager, create_signal_log_entry
from src.behaviors.behaviors_simplified import SimplifiedBehaviorManager
from src.monitoring.position_monitor import PositionMonitor
from src.analysis.tape_reading_analyzer import TapeReadingAnalyzer
from src.analysis.volume_normalizer import VolumeNormalizer

# Para alertas sonoros no Windows
try:
    import winsound
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = get_logger(__name__)
logging.getLogger('src.data.excel_provider').setLevel(logging.ERROR)
logging.getLogger('src.core.config').setLevel(logging.ERROR)
logging.getLogger('src.core.cache').setLevel(logging.ERROR)

# ======================== DATACLASSES ========================
@dataclass
class MarketData:
    """Dados de mercado estruturados"""
    wdo_book: Dict
    dol_book: Dict
    wdo_trades: List[Dict]
    dol_trades: List[Dict]
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class SpreadStatistics:
    """Estatísticas do spread"""
    current: float
    mean: float
    std: float
    z_score: float
    min: float
    max: float
    volatility: float

    @property
    def percentile(self) -> int:
        """Calcula percentil aproximado baseado no z-score"""
        return int(abs(self.z_score) * 33.3)

@dataclass
class SessionStatistics:
    """Estatísticas da sessão"""
    start_time: datetime = field(default_factory=datetime.now)
    total_signals: int = 0
    signals_60_70: int = 0
    signals_70_plus: int = 0
    total_pnl: float = 0.0
    total_wins: int = 0
    total_losses: int = 0

# ======================== CLASSES ========================
class ArbitrageAnalyzer:
    """Analisador de arbitragem com suporte a perfis de trading"""

    def __init__(self, config: Dict, param_manager: Optional[DynamicParameterManager] = None):
        self.config = config
        self.param_manager = param_manager
        self._load_config()
        self._init_history()
        self._init_components()

    def _load_config(self):
        """Carrega configuração de forma estruturada com suporte a perfis"""
        arb_config = self.config.get('arbitrage', {})
        
        # Detecta perfil ativo (pode vir de variável de ambiente)
        active_profile = os.getenv('ARBITRAGE_PROFILE', 
                                  arb_config.get('active_profile', 'default'))
        profiles = arb_config.get('trading_profiles', {})
        
        # Carrega configurações do perfil ativo
        if active_profile in profiles:
            profile_config = profiles[active_profile]
            logger.info(f"📊 Usando perfil de trading: {active_profile}")
            logger.info(f"   - Threshold: {profile_config.get('spread_std_devs')}σ")
            logger.info(f"   - Amostras: {profile_config.get('min_samples_for_signal')}")
            logger.info(f"   - Lucro mínimo: R$ {profile_config.get('min_profit_reais')}")
            
            # Aplica configurações do perfil
            self.STD_THRESHOLD = profile_config.get('spread_std_devs', 
                                arb_config.get('alerts', {}).get('spread_std_devs', 1.5))
            self.MIN_SAMPLES = profile_config.get('min_samples_for_signal',
                              arb_config.get('statistics', {}).get('min_samples_for_signal', 20))
            self.MIN_PROFIT_REAIS = profile_config.get('min_profit_reais',
                                   arb_config.get('detection', {}).get('min_profit_reais', 20.0))
        else:
            # Usa valores padrão se perfil não existir
            logger.warning(f"Perfil '{active_profile}' não encontrado. Usando valores padrão.")
            self.STD_THRESHOLD = arb_config.get('alerts', {}).get('spread_std_devs', 1.5)
            self.MIN_SAMPLES = arb_config.get('statistics', {}).get('min_samples_for_signal', 20)
            self.MIN_PROFIT_REAIS = arb_config.get('detection', {}).get('min_profit_reais', 20.0)
        
        # Resto das configurações
        self.history_size = arb_config.get('statistics', {}).get('history_size', 100)
        self.leader_history_size = arb_config.get('statistics', {}).get('leader_analysis_history_size', 50)

        # Configurações de análise de liderança
        leadership_config = self.config.get('arbitrage_enhanced', {}).get('leadership_analysis', {})
        self.leader_lookback = leadership_config.get('lookback_period', 5)
        self.leader_ratio = leadership_config.get('imbalance_ratio', 1.2)

        # Configurações de integração de comportamento
        behavior_config = self.config.get('arbitrage_enhanced', {}).get('behavior_integration', {})
        self.behavior_strength_threshold = behavior_config.get('min_strength_for_confirmation', 50)
        self.behavior_confidence_bonus = behavior_config.get('confidence_bonus_per_confirmation', 5)
        
        # Debug: mostrar análise de spread se habilitado
        debug_config = self.config.get('arbitrage_enhanced', {}).get('debug', {})
        self.show_spread_analysis = debug_config.get('show_spread_analysis', False)

    def _init_history(self):
        """Inicializa históricos e estatísticas"""
        self.spread_history = deque(maxlen=self.history_size)
        self.wdo_price_history = deque(maxlen=self.leader_history_size)
        self.dol_price_history = deque(maxlen=self.leader_history_size)
        self.stats = {'signals_generated': 0}

    def _init_components(self):
        """Inicializa componentes relacionados"""
        enhanced_config = self.config.get('arbitrage_enhanced', {})
        self.validator = ArbitrageValidator(enhanced_config.get('validation', {}))
        self.signal_formatter = SignalFormatter()
        if 'arbitrage' not in self.config or 'alerts' not in self.config['arbitrage']:
            validation_config = enhanced_config.get('validation', {})
            self.STD_THRESHOLD = validation_config.get('threshold_medium', 1.5)

    def calculate_real_spread(self, wdo_price: float, dol_price: float) -> float:
        """Calcula spread real entre WDO e DOL"""
        return wdo_price - dol_price

    def update_spread_history(self, spread: float, wdo_mid: float, dol_mid: float):
        """Atualiza histórico de spreads e preços"""
        self.spread_history.append(spread)
        self.wdo_price_history.append(wdo_mid)
        self.dol_price_history.append(dol_mid)

    def calculate_spread_statistics(self) -> SpreadStatistics:
        """Calcula estatísticas do spread"""
        if len(self.spread_history) < self.MIN_SAMPLES:
            return SpreadStatistics(current=self.spread_history[-1] if self.spread_history else 0, 
                                  mean=0, std=0, z_score=0, min=0, max=0, volatility=0)
        
        current = self.spread_history[-1]
        mean = statistics.mean(self.spread_history)
        std = statistics.stdev(self.spread_history)
        z_score = (current - mean) / std if std > 0 else 0
        
        # Debug: mostrar análise se habilitado
        if self.show_spread_analysis and len(self.spread_history) % 10 == 0:
            print(f"\r[SPREAD] Current: {current:+.2f} | Mean: {mean:+.2f} | "
                  f"Std: {std:.2f} | Z-Score: {z_score:+.2f} | "
                  f"Threshold: ±{self.STD_THRESHOLD}σ | "
                  f"Samples: {len(self.spread_history)}/{self.MIN_SAMPLES}", end="")
        
        return SpreadStatistics(current=current, mean=mean, std=std, z_score=z_score, 
                              min=min(self.spread_history), max=max(self.spread_history), 
                              volatility=std)

    def generate_trading_signal(self, market_data: MarketData, behaviors: Dict = None) -> Tuple[Optional[Dict], str]:
        """Gera sinal de trading baseado nas condições de mercado"""
        wdo_book, dol_book = market_data.wdo_book, market_data.dol_book
        if not (wdo_book.get('bids') and wdo_book.get('asks') and dol_book.get('bids') and dol_book.get('asks')):
            return None, "Book de ofertas incompleto"

        wdo_mid = (wdo_book['bids'][0]['price'] + wdo_book['asks'][0]['price']) / 2
        dol_mid = (dol_book['bids'][0]['price'] + dol_book['asks'][0]['price']) / 2
        current_spread = self.calculate_real_spread(wdo_mid, dol_mid)

        self.update_spread_history(current_spread, wdo_mid, dol_mid)

        if self.param_manager:
            self.param_manager.update_market_data(current_spread)
            params = self.param_manager.adjust_parameters()
            self.STD_THRESHOLD = params.get('STD_THRESHOLD', self.STD_THRESHOLD)
            self.MIN_PROFIT_REAIS = params.get('MIN_PROFIT_REAIS', self.MIN_PROFIT_REAIS)

        if len(self.spread_history) < self.MIN_SAMPLES:
            return None, f"Aguardando amostras: {len(self.spread_history)}/{self.MIN_SAMPLES}"

        stats = self.calculate_spread_statistics()
        is_valid, validation_result, reason = self.validator.validate_opportunity(
            entry_spread=current_spread, mean_spread=stats.mean, std_spread=stats.std,
            z_score=stats.z_score, spread_history=list(self.spread_history),
            active_threshold=self.STD_THRESHOLD  # CORREÇÃO: Passa o threshold do perfil ativo
        )

        if not is_valid:
            return None, reason

        entry_price = dol_book['asks'][0]['price'] if validation_result.direction == 'COMPRA' else dol_book['bids'][0]['price']
        signal_data = self.signal_formatter.format_signal(validation_result, entry_price)
        
        signal_data.update({
            'spread': current_spread, 'z_score': stats.z_score,
            'spread_mean': stats.mean, 'spread_std': stats.std, 'source': 'ARBITRAGEM'
        })

        self._add_leadership_analysis(signal_data)
        if behaviors:
            self._add_behavior_confirmations(signal_data, behaviors)
        
        self.stats['signals_generated'] += 1
        return signal_data, f"Sinal gerado: {reason}"

    def _add_leadership_analysis(self, signal_data: Dict):
        """Adiciona análise de liderança ao sinal"""
        if len(self.wdo_price_history) >= self.leader_lookback and len(self.dol_price_history) >= self.leader_lookback:
            wdo_move = self.wdo_price_history[-1] - self.wdo_price_history[-self.leader_lookback]
            dol_move = self.dol_price_history[-1] - self.dol_price_history[-self.leader_lookback]
            if abs(wdo_move) > abs(dol_move) * self.leader_ratio:
                signal_data['leader'] = 'WDOFUT'
            elif abs(dol_move) > abs(wdo_move) * self.leader_ratio:
                signal_data['leader'] = 'DOLFUT'
            else:
                signal_data['leader'] = 'NEUTRO'

    def _add_behavior_confirmations(self, signal_data: Dict, behaviors: Dict):
        """Adiciona confirmações de behaviors ao sinal"""
        confirmations = [b['description'] for b in behaviors.values() if b and b.get('strength', 0) > self.behavior_strength_threshold]
        if confirmations:
            signal_data['gatilhos'].extend(confirmations)
            signal_data['confidence'] = min(95, signal_data.get('confidence', 60) + len(confirmations) * self.behavior_confidence_bonus)


class ArbitrageApplication:
    """Aplicação principal de arbitragem - Arquitetura refatorada com Rich Display"""

    def __init__(self):
        # Inicializa todos os atributos como None
        self.config_manager = None
        self.data_provider = None
        self.analyzer = None
        self.flow_analyzer = None
        self.liquidity_analyzer = None
        self.param_manager = None
        self.signal_logger = None
        self.signal_history = None
        self.behavior_manager = None
        self.position_monitor = None
        self.tape_analyzer = None
        self.rich_display = None
        self.session_stats = SessionStatistics()
        self.last_signal = None
        self.last_data_hash = None
        self.wdo_volume = 0
        self.dol_volume = 0
        self.normalizer = VolumeNormalizer()
        self.alert_config = {}
        self.main_loop_sleep = 0.1  # Valor padrão
        
        self.metrics = {
            'data_errors': 0
        }

    async def initialize_components(self):
        """Inicializa todos os componentes da aplicação"""
        logger.info("Inicializando componentes...")
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config')
        self.config_manager = ConfigManager(config_dir=config_dir, env='production')
        config = self.config_manager.get_all()

        # Carregar configurações específicas
        self.main_loop_sleep = self.config_manager.get('arbitrage.operation.main_loop_sleep', 0.1)
        self.alert_config = self.config_manager.get('arbitrage_enhanced.alerts', {})

        excel_config = self.config_manager.get('excel', {})
        self.data_provider = ExcelDataProvider(excel_config, None)
        await self.data_provider.initialize()

        enhanced_config = config.get('arbitrage_enhanced', {})
        self.flow_analyzer = FlowAnalyzer(enhanced_config.get('flow_analysis', {}))
        self.liquidity_analyzer = LiquidityAnalyzer(enhanced_config.get('liquidity_analysis', {}))
        self.param_manager = DynamicParameterManager(config.get('arbitrage', {}))
        self.analyzer = ArbitrageAnalyzer(config, self.param_manager)
        self.signal_logger = SignalLogger(enhanced_config.get('logging', {}).get('signal_logger', {}))
        self.signal_history = SignalHistoryManager(enhanced_config.get('logging', {}).get('history_manager', {}))
        self.behavior_manager = SimplifiedBehaviorManager(config.get('behaviors', {}))
        
        pm_config = enhanced_config.get('position_monitor', {})
        pm_config['point_value'] = self.config_manager.get('arbitrage.contracts.dol.tick_value', 10.0)
        self.position_monitor = PositionMonitor(pm_config)

        self.tape_analyzer = TapeReadingAnalyzer(config.get('tape_reading', {}))
        self.rich_display = RichEnhancedDisplay()
        logger.info("Todos os componentes inicializados com sucesso")
    
    async def _get_market_data(self) -> Optional[MarketData]:
        """Obtém dados de mercado usando método público e com tratamento de erro."""
        try:
            snapshot = await self.data_provider.get_market_snapshot()
            if not snapshot:
                logger.warning("Snapshot vazio recebido do provider")
                return None

            wdo_book = snapshot['wdofut']['book']
            dol_book = snapshot['dolfut']['book']

            if not (wdo_book.get('bids') and wdo_book.get('asks') and dol_book.get('bids') and dol_book.get('asks')):
                return None
            
            wdo_trades_normalized = self.normalizer.normalize_trades(snapshot['wdofut']['trades'])
            dol_trades_normalized = self.normalizer.normalize_trades(snapshot['dolfut']['trades'])
            
            self.wdo_volume = sum(trade.get('normalized_volume', 0) for trade in wdo_trades_normalized)
            self.dol_volume = sum(trade.get('normalized_volume', 0) for trade in dol_trades_normalized)

            return MarketData(
                wdo_book=wdo_book,
                dol_book=dol_book,
                wdo_trades=wdo_trades_normalized,
                dol_trades=dol_trades_normalized
            )
        except Exception as e:
            logger.error(f"Erro ao obter dados de mercado do provider: {e}", exc_info=False)
            self.metrics['data_errors'] += 1
            return None
    
    def _calculate_data_hash(self, market_data: MarketData) -> str:
        """Calcula um hash eficiente do estado do topo do book e dos últimos trades."""
        if not market_data:
            return ""
        
        try:
            # Inclui o topo do book
            key_data = [
                market_data.wdo_book['bids'][0]['price'],
                market_data.wdo_book['asks'][0]['price'],
                market_data.dol_book['bids'][0]['price'],
                market_data.dol_book['asks'][0]['price']
            ]
            # CORREÇÃO: Inclui o timestamp do último trade de WDO, se houver
            if market_data.wdo_trades:
                key_data.append(market_data.wdo_trades[0]['timestamp'])
            # CORREÇÃO: Inclui o timestamp do último trade de DOL, se houver
            if market_data.dol_trades:
                key_data.append(market_data.dol_trades[0]['timestamp'])

            return hashlib.md5(str(tuple(key_data)).encode()).hexdigest()
        except (IndexError, KeyError):
            return ""

    def _analyze_behaviors(self, market_data: MarketData) -> Dict:
        """Analisa comportamentos de mercado"""
        behaviors = {}
        if not self.behavior_manager:
            return behaviors
        
        all_trades = market_data.wdo_trades + market_data.dol_trades
        
        dol_behaviors = self.behavior_manager.analyze_symbol(all_trades, 'DOLFUT')
        wdo_behaviors = self.behavior_manager.analyze_symbol(all_trades, 'WDOFUT')
        
        if dol_behaviors: behaviors.update({f'dol_{k}': v for k, v in dol_behaviors.items() if v})
        if wdo_behaviors: behaviors.update({f'wdo_{k}': v for k, v in wdo_behaviors.items() if v})
            
        wdo_defense = self.behavior_manager.detect_price_defense(market_data.wdo_book, 'WDOFUT')
        if wdo_defense: behaviors['price_defense_wdo'] = wdo_defense
        
        dol_defense = self.behavior_manager.detect_price_defense(market_data.dol_book, 'DOLFUT')
        if dol_defense: behaviors['price_defense_dol'] = dol_defense
            
        return behaviors

    async def _update_position(self, market_data: MarketData, spread_stats: SpreadStatistics) -> Optional[Dict]:
        """Atualiza posição ativa e executa saída se necessário."""
        if not self.position_monitor.has_active_position():
            return None
        
        pos_summary = self.position_monitor.get_first_position_summary()
        current_dol_price = (market_data.dol_book['bids'][0]['price'] + market_data.dol_book['asks'][0]['price']) / 2
        
        update_result = self.position_monitor.update_position(None, current_dol_price, spread_stats.current, spread_stats.z_score)
        
        for alert in update_result.get('alerts', []):
            self._play_alert_sound(alert.get('sound'))
            if alert.get('severity') == 'HIGH':
                logger.critical(f"⛔ ALERTA CRÍTICO POSIÇÃO: {alert.get('message')}")
        
        if update_result.get('should_exit', False):
            logger.warning(f"Sinal de saída recebido do monitor: {update_result.get('status')}. Fechando posição.")
            exit_result = self.position_monitor.remove_position(None, current_dol_price, update_result.get('status'))
            
            if exit_result and exit_result.get('success'):
                pnl = exit_result['summary']['pnl']
                logger.critical(f"POSIÇÃO FECHADA: {exit_result['summary']['reason']} | P&L: R$ {pnl:.2f}")

                if pnl > 0:
                    self.session_stats.total_wins += 1
                else:
                    self.session_stats.total_losses += 1
                self.session_stats.total_pnl += pnl
                
                self.signal_history.update_last_signal_status(
                    'success' if pnl > 0 else 'failed', abs(pnl)
                )
            else:
                logger.error("Falha ao tentar remover a posição do monitor.")

        return update_result
        
    def _play_alert_sound(self, sound_type: str):
        """Toca som de alerta com base na configuração"""
        if not SOUND_AVAILABLE or sys.platform != 'win32' or not self.alert_config.get('sound_enabled'):
            return
            
        freqs = self.alert_config.get('sound_frequencies', {})
        duration = self.alert_config.get('sound_duration_ms', 300)

        sound_map = {
            'alert_critical': (freqs.get('alert_critical', 2000), 3),
            'alert_warning': (freqs.get('alert_warning', 1500), 2),
            'alert_success': (freqs.get('alert_success', 1000), 1)
        }
        
        if sound_type in sound_map:
            freq, count = sound_map[sound_type]
            for _ in range(count):
                winsound.Beep(freq, duration // count)

    async def _analyze_tape_reading(self, market_data: MarketData) -> Tuple[Optional[Dict], str]:
        """Analisa tape reading no DOL"""
        # CORREÇÃO: Verifica se há trades em qualquer um dos ativos
        if not (market_data.wdo_trades or market_data.dol_trades) or not self.tape_analyzer:
            return None, ""
        if self.position_monitor.has_active_position():
            return None, "Posição ativa - aguardando finalização"

        dol_mid_price = (market_data.dol_book['bids'][0]['price'] + market_data.dol_book['asks'][0]['price']) / 2
        all_trades = market_data.wdo_trades + market_data.dol_trades
        tape_signal, tape_reason = self.tape_analyzer.analyze_trades(all_trades, dol_mid_price)
        
        if tape_signal:
            tape_signal['gatilhos'].insert(0, "📊 Tape Reading Direcional")
            tape_signal['source'] = 'TAPE_READING'
        return tape_signal, tape_reason

    async def _process_signal(self, signal: Dict, behaviors: Dict) -> bool:
        """Processa e registra um sinal"""
        if not all(k in signal for k in ['action', 'asset', 'entry', 'confidence', 'contracts']):
            logger.error(f"Sinal inválido recebido, faltando chaves essenciais: {signal}")
            return False

        log_entry = create_signal_log_entry(
            action=signal['action'], asset=signal['asset'], price=signal['entry'], confidence=signal['confidence'],
            spread=signal.get('spread', 0), z_score=signal.get('z_score', 0), gatilhos=signal.get('gatilhos', []),
            alvos=signal.get('targets', []), stop=signal.get('stop', 0), contratos=signal['contracts'],
            expected_profit=signal.get('expected_profit', 0), risk=signal.get('risk', 0),
            leadership={'leader': signal.get('leader', 'NEUTRO')}, behaviors=list(behaviors.values())
        )
        
        signal_id = self.signal_logger.log_signal(log_entry)
        signal['signal_id'] = signal_id
        
        position_id, msg = self.position_monitor.add_position(signal)
        if position_id:
            self.signal_history.add_signal(signal)
            self.session_stats.total_signals += 1
            if signal['confidence'] >= 70: self.session_stats.signals_70_plus += 1
            else: self.session_stats.signals_60_70 += 1
            
            if SOUND_AVAILABLE and self.alert_config.get('sound_enabled'):
                freqs = self.alert_config.get('sound_frequencies', {})
                duration = self.alert_config.get('sound_duration_ms', 300)
                freq = freqs.get('premium_signal', 2000) if signal['confidence'] >= 85 else freqs.get('normal_signal', 1500)
                winsound.Beep(freq, duration)
            
            self.last_signal = signal
            return True
        return False
        
    def _update_display(self, market_data: MarketData, spread_stats: SpreadStatistics,
                       signal: Optional[Dict], behaviors: Dict, 
                       update_result: Optional[Dict]):
        """Atualiza o display Rich com todas as informações"""
        wdo_mid = (market_data.wdo_book['bids'][0]['price'] + market_data.wdo_book['asks'][0]['price']) / 2
        dol_mid = (market_data.dol_book['bids'][0]['price'] + market_data.dol_book['asks'][0]['price']) / 2
        
        display_data = {
            'signals_today': self.session_stats.total_signals,
            'market': {
                'wdo_price': wdo_mid, 'wdo_change': wdo_mid - (self.analyzer.wdo_price_history[-2] if len(self.analyzer.wdo_price_history) > 1 else wdo_mid),
                'wdo_volume': self.wdo_volume, 'dol_price': dol_mid,
                'dol_change': dol_mid - (self.analyzer.dol_price_history[-2] if len(self.analyzer.dol_price_history) > 1 else dol_mid),
                'dol_volume': self.dol_volume, 'spread': spread_stats.current, 'z_score': spread_stats.z_score,
                'mean': spread_stats.mean, 'std': spread_stats.std, 'min': spread_stats.min, 'max': spread_stats.max
            },
            'signal': signal,
            'positions': self.position_monitor.get_active_positions_summary(),
            'tape': self.tape_analyzer.get_statistics() if self.tape_analyzer else {},
            'behaviors': [b for b in behaviors.values() if b and b.get('strength', 0) >= 60],
            'history': self.signal_history.get_formatted_history(),
            'stats': self.position_monitor.get_statistics(),
            'system_health': {'data_errors': self.metrics['data_errors']}
        }
        self.rich_display.update(display_data)
        self.rich_display.render()

    async def _tick(self):
        """Executa uma iteração do loop principal"""
        market_data = await self._get_market_data()
        if not market_data: return

        current_hash = self._calculate_data_hash(market_data)
        if current_hash == self.last_data_hash:
            return 
        self.last_data_hash = current_hash
        
        spread_stats = self.analyzer.calculate_spread_statistics()
        
        behaviors = self._analyze_behaviors(market_data)
        update_result = await self._update_position(market_data, spread_stats)
        
        signal = None
        if not self.position_monitor.has_active_position():
            tape_signal, _ = await self._analyze_tape_reading(market_data)
            if tape_signal:
                signal = tape_signal
            else:
                arbitrage_signal, _ = self.analyzer.generate_trading_signal(market_data, behaviors)
                signal = arbitrage_signal
        
        if signal:
            await self._process_signal(signal, behaviors)
            
        self._update_display(market_data, spread_stats, signal, behaviors, update_result)

    async def run(self):
        """Loop principal da aplicação"""
        print("=== ANALISADOR DE ARBITRAGEM WDO/DOL v5.2 COM PERFIS ===")
        print("Interface visual aprimorada com Rich\n")
        
        try:
            # PRIMEIRO: Inicializar componentes
            await self.initialize_components()
            print("✅ Sistema inicializado - v5.2")
            
            # AGORA sim podemos usar config_manager
            if self.config_manager:
                config = self.config_manager.get_all()
                active_profile = os.getenv('ARBITRAGE_PROFILE', 
                                          config.get('arbitrage', {}).get('active_profile', 'default'))
                print(f"📊 Perfil ativo: {active_profile}")
                print("💡 Para mudar: set ARBITRAGE_PROFILE=small_spreads && python arbitrage_dashboard.py\n")
            
            # Loop principal
            while True:
                try:
                    await self._tick()
                    await asyncio.sleep(self.main_loop_sleep)
                except Exception as e:
                    logger.error(f"Erro no loop principal: {e}", exc_info=True)
                    await asyncio.sleep(2)
                    
        except KeyboardInterrupt:
            logger.info("Análise interrompida pelo usuário.")
            print("\n\nAnálise interrompida.")
        except Exception as e:
            logger.error(f"Erro fatal: {e}", exc_info=True)
            print(f"\n❌ Erro fatal: {e}")
        finally:
            await self._cleanup()

    async def _cleanup(self):
        """Limpeza e finalização"""
        logger.info("Finalizando sistema de arbitragem")
        if self.signal_logger:
            print("\nSalvando logs pendentes...")
            self.signal_logger.flush_buffer()
        if self.data_provider:
            await self.data_provider.close()
        if self.rich_display:
            self.rich_display.stop()
        logger.info("Sistema finalizado.")

async def main():
    ensure_log_structure()
    app = ArbitrageApplication()
    await app.run()

if __name__ == "__main__":
    if sys.platform == "win32":
        os.system("color")
    asyncio.run(main())