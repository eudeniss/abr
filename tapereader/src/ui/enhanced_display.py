"""
Display aprimorado para o sistema de arbitragem - v5.1 com Tape Reading
CORREÇÃO: Painel de comportamentos só aparece com behaviors significativos
NOVO: Painel de tape reading para mostrar pressão direcional
"""
import os
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque

class Colors:
    """Cores ANSI para terminal"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    BLINK = '\033[5m'
    
    # Backgrounds
    BG_GREEN = '\033[42m'
    BG_RED = '\033[41m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_CYAN = '\033[46m'

class EnhancedDisplay:
    """Sistema de display aprimorado com foco em operações de DÓLAR"""
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Carregar configurações de display
        z_config = self.config.get('z_score_colors', {})
        self.z_high = z_config.get('high_z', 2.0)
        self.z_medium = z_config.get('medium_z', 1.5)
        self.z_low = z_config.get('low_z', 1.0)
        
        self.tape_pressure_threshold = self.config.get('tape_pressure_threshold_pct', 60)
        
        conf_config = self.config.get('confidence_levels', {})
        self.conf_high = conf_config.get('high', 85)
        self.conf_medium = conf_config.get('medium', 70)
        
        self.sizing_labels = self.config.get('position_sizing_labels', {
            'high_confidence': "MÃO CHEIA", 'medium_confidence': "MÃO CHEIA", 'low_confidence': "MEIA MÃO"
        })
        
        behav_config = self.config.get('behavior_filtering', {})
        self.behav_min_strength = behav_config.get('min_strength_for_display', 60)
        self.behav_ignore_momentum = behav_config.get('ignore_momentum_strength_below', 70)
        
        stats_config = self.config.get('session_stats_colors', {})
        self.stats_high_wr = stats_config.get('high_win_rate', 60)
        self.stats_medium_wr = stats_config.get('medium_win_rate', 40)

        self.panels = {
            'header': [], 'market': [], 'tape': [], 'signal': [], 'position': [],
            'arbitrage': [], 'history': [], 'behaviors': [], 'stats': [],
            'alerts': deque(maxlen=5)
        }
        self.last_update = datetime.now()
        self.signal_history = deque(maxlen=5)
        
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def update_header(self, signals_today: int = 0):
        self.panels['header'] = [
            f"{Colors.CYAN}{'═' * 120}{Colors.RESET}",
            f"{Colors.BOLD}{Colors.CYAN}                               ANALISADOR DE ARBITRAGEM WDO/DOL v5.1 com Tape Reading{Colors.RESET}",
            f"Horário: {Colors.WHITE}{datetime.now().strftime('%H:%M:%S')}{Colors.RESET} | Sistema: {Colors.GREEN}ATIVO{Colors.RESET} | Sinais Hoje: {Colors.YELLOW}{signals_today}{Colors.RESET}",
            f"{Colors.CYAN}{'═' * 120}{Colors.RESET}"
        ]
        
    def update_market_panel(self, wdo_price: float, dol_price: float, spread: float, stats: Dict, wdo_change: float = 0, dol_change: float = 0):
        z_score = stats.get('z_score', 0)
        spread_color = Colors.WHITE
        if abs(z_score) > self.z_high: spread_color = Colors.RED + Colors.BOLD
        elif abs(z_score) > self.z_medium: spread_color = Colors.YELLOW + Colors.BOLD
        elif abs(z_score) > self.z_low: spread_color = Colors.YELLOW
            
        wdo_change_str = f"{Colors.GREEN}+{wdo_change:.2f}{Colors.RESET}" if wdo_change >= 0 else f"{Colors.RED}{wdo_change:.2f}{Colors.RESET}"
        dol_change_str = f"{Colors.GREEN}+{dol_change:.2f}{Colors.RESET}" if dol_change >= 0 else f"{Colors.RED}{dol_change:.2f}{Colors.RESET}"
        percentile = int(abs(z_score) * 33.3)
        
        self.panels['market'] = [
            f"{Colors.BLUE}┌─ MERCADO {'─' * 108}┐{Colors.RESET}",
            f"{Colors.BLUE}│{Colors.RESET} WDO: {Colors.BOLD}{wdo_price:>7.2f}{Colors.RESET} ({wdo_change_str}) {Colors.BLUE}|{Colors.RESET} DOL: {Colors.BOLD}{dol_price:>7.2f}{Colors.RESET} ({dol_change_str}) {Colors.BLUE}|{Colors.RESET} Spread: {spread_color}{spread:>6.2f} ({z_score:+.2f}σ){Colors.RESET}",
            f"{Colors.BLUE}│{Colors.RESET} Média: {stats.get('mean', 0):>6.2f} | Desvio: {stats.get('std', 0):>5.2f} | Min: {stats.get('min', 0):>6.2f} | Max: {stats.get('max', 0):>6.2f} | Percentil: {Colors.CYAN}{percentile}°{Colors.RESET}",
            f"{Colors.BLUE}└{'─' * 118}┘{Colors.RESET}"
        ]
    
    def update_tape_panel(self, tape_stats: Dict):
        if not tape_stats or not tape_stats.get('has_data'):
            self.panels['tape'] = []
            return
            
        buy_pct, sell_pct = tape_stats.get('buy_percentage', 0), tape_stats.get('sell_percentage', 0)
        if buy_pct > self.tape_pressure_threshold: pressure_color, arrow, direction = Colors.GREEN, "↑", "COMPRA"
        elif sell_pct > self.tape_pressure_threshold: pressure_color, arrow, direction = Colors.RED, "↓", "VENDA"
        else: pressure_color, arrow, direction = Colors.YELLOW, "→", "NEUTRO"
            
        self.panels['tape'] = [
            f"{Colors.MAGENTA}┌─ TAPE READING {'─' * 103}┐{Colors.RESET}",
            f"{Colors.MAGENTA}│{Colors.RESET} {arrow} Pressão: Compra {Colors.GREEN}{buy_pct:.1f}%{Colors.RESET} vs Venda {Colors.RED}{sell_pct:.1f}%{Colors.RESET} | Fluxo: {pressure_color}{direction}{Colors.RESET} | Trades analisados: {tape_stats.get('total_trades_analyzed', 0)}",
            f"{Colors.MAGENTA}└{'─' * 118}┘{Colors.RESET}"
        ]
        
    def update_signal_panel(self, signal: Optional[Dict]):
        if not signal:
            self.panels['signal'] = []
            return
            
        action_bg = Colors.BG_GREEN if signal['action'] == 'COMPRA' else Colors.BG_RED
        border_color = Colors.GREEN if signal['action'] == 'COMPRA' else Colors.RED
        
        if signal['confidence'] >= self.conf_high:
            emoji, contracts_info, conf_color = "🔥", self.sizing_labels.get('high_confidence'), Colors.GREEN
        elif signal['confidence'] >= self.conf_medium:
            emoji, contracts_info, conf_color = "💪", self.sizing_labels.get('medium_confidence'), Colors.YELLOW
        else:
            emoji, contracts_info, conf_color = "📊", self.sizing_labels.get('low_confidence'), Colors.CYAN
            
        conf_bar = self._create_confidence_bar(signal['confidence'])
        source_text = "📊 TAPE READING DIRECIONAL" if signal.get('source') == 'TAPE_READING' else "📈 ARBITRAGEM ESTATÍSTICA"
        
        self.panels['signal'] = [
            f"{border_color}┌─ SINAL DIRECIONAL {'─' * 99}┐{Colors.RESET}",
            f"{border_color}│{Colors.RESET} {emoji} {action_bg}{Colors.BOLD} {signal['action']} DÓLAR {Colors.RESET} - {source_text}",
            f"{border_color}│{Colors.RESET} Entrada: {Colors.BOLD}{signal['entry']:>7.2f}{Colors.RESET} | Alvo: {Colors.GREEN}{signal['targets'][0]:>7.2f}{Colors.RESET} | Alvo 2: {Colors.GREEN}{signal['targets'][1]:>7.2f}{Colors.RESET} | Stop: {Colors.RED}{signal['stop']:>7.2f}{Colors.RESET}",
            f"{border_color}│{Colors.RESET} Confiança: {conf_bar} {conf_color}{signal['confidence']:.0f}%{Colors.RESET} → {Colors.BOLD}{contracts_info}{Colors.RESET} ({signal['contracts']} contratos)",
            f"{border_color}│{Colors.RESET} 📊 WDO está {Colors.BOLD}R$ {abs(signal.get('spread', 0)):>4.2f}{Colors.RESET} {'acima' if signal.get('spread', 0) > 0 else 'abaixo'} do DOL (spread no {Colors.CYAN}{abs(signal.get('z_score', 0) * 33.3):.0f}°{Colors.RESET} percentil)",
            f"{border_color}│{Colors.RESET} 🔄 {Colors.BOLD}{signal.get('leader', 'WDOFUT')}{Colors.RESET} liderando movimento de {'alta' if signal['action'] == 'COMPRA' else 'baixa'} há {Colors.YELLOW}{signal.get('leadership_time', 15)}{Colors.RESET} segundos",
            f"{border_color}│{Colors.RESET} 💪 {Colors.BOLD}DÓLAR{Colors.RESET} deve convergir seguindo {signal.get('leader', 'WDO')[:3]} nos próximos minutos",
            f"{border_color}└{'─' * 118}┘{Colors.RESET}"
        ]

    def update_monitoring_panel(self, spread: float, z_score: float, threshold: float):
        distance = threshold - abs(z_score)
        progress_bar = self._create_progress_bar(abs(z_score), threshold)
        self.panels['signal'] = [
            f"{Colors.YELLOW}┌─ MONITORANDO OPORTUNIDADE {'─' * 91}┐{Colors.RESET}",
            f"{Colors.YELLOW}│{Colors.RESET} 👁️  Sistema analisando spread...",
            f"{Colors.YELLOW}│{Colors.RESET} Spread atual: {Colors.BOLD}{spread:>6.2f}{Colors.RESET} | Z-score: {Colors.BOLD}{z_score:>+5.2f}σ{Colors.RESET} | Threshold: {Colors.CYAN}±{threshold}σ{Colors.RESET}",
            f"{Colors.YELLOW}│{Colors.RESET} Progresso: {progress_bar} (faltam {Colors.YELLOW}{distance:.2f}σ{Colors.RESET} para sinal)",
            f"{Colors.YELLOW}└{'─' * 118}┘{Colors.RESET}"
        ]

    def update_arbitrage_panel(self, analysis: Dict = None):
        analysis = analysis or {}
        convergence, eta, correlation, leader, lag = (
            analysis.get('convergence', 0), analysis.get('eta', 0),
            analysis.get('correlation', 0), analysis.get('leader', "NEUTRO"),
            analysis.get('leadership_time', 0)
        )
        self.panels['arbitrage'] = [
            f"{Colors.MAGENTA}┌─ ANÁLISE DE ARBITRAGEM {'─' * 94}┐{Colors.RESET}",
            f"{Colors.MAGENTA}│{Colors.RESET} Convergência: {Colors.BOLD}{convergence:.0f}%{Colors.RESET} | ETA: {Colors.BOLD}{eta:.1f} min{Colors.RESET} | Correlação: {Colors.BOLD}{correlation:.2f}{Colors.RESET} | Líder: {Colors.CYAN}{leader}{Colors.RESET} (+{lag}s)",
            f"{Colors.MAGENTA}└{'─' * 118}┘{Colors.RESET}"
        ]

    def update_history_panel(self, history_data):
        if hasattr(history_data, 'get_finished_history'): signals = history_data.get_finished_history()
        elif isinstance(history_data, list): signals = [s for s in history_data if s.get('status') in ['success', 'failed', 'stopped']]
        else: signals = []

        lines = [f"{Colors.CYAN}┌─ HISTÓRICO DE SINAIS {'─' * 96}┐{Colors.RESET}"]
        if not signals:
            lines.append(f"{Colors.CYAN}│{Colors.RESET} {Colors.GRAY}Aguardando sinais finalizados...{Colors.RESET}")
        else:
            for sig in list(signals)[-5:]:
                if sig.get('status') == 'success': icon, result = '✓', f"{Colors.GREEN}LUCRO: R$ {sig.get('profit', 0):.2f}{Colors.RESET}"
                else: icon, result = '✗', f"{Colors.RED}STOP: -R$ {abs(sig.get('loss', 0)):.2f}{Colors.RESET}"
                strength = '🔥' if sig['confidence'] >= self.conf_high else '💪' if sig['confidence'] >= self.conf_medium else '📊'
                action_color = Colors.GREEN if sig['action'] == 'COMPRA' else Colors.RED
                lines.append(f"{Colors.CYAN}│{Colors.RESET} {strength} {Colors.WHITE}{sig['time']}{Colors.RESET} {action_color}{sig['action']} DÓLAR{Colors.RESET} @ {Colors.BOLD}{sig['price']:.2f}{Colors.RESET} ({sig['confidence']:.0f}%)  {result}")
        lines.append(f"{Colors.CYAN}└{'─' * 118}┘{Colors.RESET}")
        self.panels['history'] = lines

    def update_behaviors_panel(self, behaviors: List[Dict]):
        if not behaviors: self.panels['behaviors'] = []; return
        significant_behaviors = [b for b in behaviors if b and b.get('strength', 0) >= self.behav_min_strength]
        if not significant_behaviors: self.panels['behaviors'] = []; return

        lines, added_lines = [f"{Colors.YELLOW}┌─ COMPORTAMENTOS DETECTADOS {'─' * 90}┐{Colors.RESET}"], False
        for behavior in significant_behaviors[:3]:
            if behavior.get('type') == 'momentum' and behavior.get('strength', 0) < self.behav_ignore_momentum: continue
            
            b_type = behavior.get('type')
            if b_type == 'absorption': icon, desc, color = '🛡️', f"ABSORPTION: Grande player absorvendo {behavior.get('side', 'ordens')} em {behavior.get('price', 0):.2f}", Colors.BLUE
            elif b_type == 'exhaustion': icon, desc, color = '🚀', f"EXHAUSTION: Movimento perdendo força, possível reversão", Colors.MAGENTA
            elif b_type == 'institutional': icon, desc, color = '🏦', f"INSTITUTIONAL: {behavior.get('side', 'Atividade')} institucional detectada", Colors.CYAN
            elif b_type == 'price_defense': icon, color = '🔒', Colors.YELLOW; desc = f"PRICE DEFENSE: Defesa {behavior.get('symbol', '')} @ {behavior.get('price_level', 0):.2f}"
            elif b_type == 'imbalance': icon, desc, color = '⚖️', f"IMBALANCE: Desequilíbrio {behavior.get('side', '')} detectado no book", Colors.CYAN
            else: continue
            
            force = behavior.get('strength', 50)
            force_color = Colors.GREEN if force >= self.conf_high else Colors.YELLOW if force >= self.conf_medium else Colors.WHITE
            lines.append(f"{Colors.YELLOW}│{Colors.RESET} {icon} {color}{desc}{Colors.RESET} (Força: {force_color}{force:.0f}%{Colors.RESET})")
            added_lines = True
        
        if not added_lines: self.panels['behaviors'] = []; return
        lines.append(f"{Colors.YELLOW}└{'─' * 118}┘{Colors.RESET}")
        self.panels['behaviors'] = lines

    def update_stats_panel(self, pnl: float = 0, win_rate: float = 0, trades: int = 0, avg_profit: float = 0):
        pnl_color = Colors.GREEN if pnl >= 0 else Colors.RED
        win_color = Colors.GREEN if win_rate >= self.stats_high_wr else Colors.YELLOW if win_rate >= self.stats_medium_wr else Colors.RED
        self.panels['stats'] = [
            f"{Colors.CYAN}┌─ ESTATÍSTICAS DA SESSÃO {'─' * 93}┐{Colors.RESET}",
            f"{Colors.CYAN}│{Colors.RESET} P&L: {pnl_color}{Colors.BOLD}R$ {pnl:>+8.2f}{Colors.RESET} | Taxa de Acerto: {win_color}{win_rate:.1f}%{Colors.RESET} | Trades: {Colors.WHITE}{trades}{Colors.RESET} | Média/Trade: {Colors.WHITE}R$ {avg_profit:.2f}{Colors.RESET}",
            f"{Colors.CYAN}└{'─' * 118}┘{Colors.RESET}"
        ]

    def update_position_panel(self, position: Optional[Dict], alerts: List[str] = None):
        if not position: self.panels['position'] = []; return
        
        pnl_color = Colors.GREEN if position['pnl'] > 0 else Colors.RED if position['pnl'] < 0 else Colors.YELLOW
        action_color = Colors.GREEN if position['action'] == 'COMPRA' else Colors.RED
        
        status = position['status']
        if status == 'STOPPED': emoji, status_color = '⛔', Colors.RED
        elif status == 'TARGET1': emoji, status_color = '✅', Colors.GREEN
        elif status == 'TARGET2': emoji, status_color = '🎯', Colors.GREEN
        elif status == 'INVALIDATED': emoji, status_color = '❌', Colors.YELLOW
        else: emoji, status_color = '📊', Colors.CYAN
            
        lines = [f"{Colors.MAGENTA}┌─ POSIÇÃO ATIVA {'─' * 102}┐{Colors.RESET}"]
        lines.append(f"{Colors.MAGENTA}│{Colors.RESET} {emoji} {action_color}{position['action']}{Colors.RESET} @ {position['entry_price']:.2f} → {Colors.BOLD}{position['current_price']:.2f}{Colors.RESET} | P&L: {pnl_color}R$ {position['pnl']:+.2f}{Colors.RESET} | Tempo: {position['time_minutes']}min {position['time_seconds'] % 60}s | Status: {status_color}{position['status']}{Colors.RESET}")
        if alerts:
            lines.append(f"{Colors.MAGENTA}├{'─' * 118}┤{Colors.RESET}")
            for alert in alerts[:3]: lines.append(f"{Colors.MAGENTA}│{Colors.RESET} {alert}")
        lines.append(f"{Colors.MAGENTA}└{'─' * 118}┘{Colors.RESET}")
        self.panels['position'] = lines

    def _create_confidence_bar(self, confidence: float) -> str:
        filled = int(confidence / 10)
        color = Colors.GREEN if confidence >= self.conf_high else Colors.YELLOW if confidence >= self.conf_medium else Colors.CYAN
        return f"{color}{'█' * filled}{'░' * (10 - filled)}{Colors.RESET}"
        
    def _create_progress_bar(self, current: float, target: float) -> str:
        percentage = min(100, (abs(current) / target) * 100) if target > 0 else 0
        filled = int(percentage / 10)
        color = Colors.RED + Colors.BOLD if percentage >= 90 else Colors.YELLOW if percentage >= 70 else Colors.CYAN
        return f"{color}{'█' * filled}{'░' * (10 - filled)}{Colors.RESET} {percentage:.0f}%"
        
    def render(self, status_message: str = ""):
        self.clear_screen()
        panel_order = ['header', 'market', 'tape', 'signal', 'position', 'arbitrage', 'history', 'behaviors', 'stats']
        for panel_name in panel_order:
            if panel := self.panels.get(panel_name, []):
                for line in panel: print(line)
        if status_message: print(f"\n{Colors.BOLD}Status:{Colors.RESET} {status_message}")
        if self.panels['alerts']:
            print(f"\n{Colors.BOLD}ALERTAS:{Colors.RESET}")
            for alert in self.panels['alerts']: print(f"  {alert}")