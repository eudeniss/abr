"""
Display Rich para o sistema de arbitragem
Interface visual moderna usando a biblioteca Rich
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.columns import Columns
from rich.progress import Progress, BarColumn, TextColumn
from rich.align import Align

logger = logging.getLogger(__name__)


class RichEnhancedDisplay:
    """Display aprimorado usando Rich para interface moderna"""
    
    def __init__(self):
        self.console = Console()
        self.layout = self._create_layout()
        self.live = Live(self.layout, console=self.console, refresh_per_second=4)
        self._started = False
        
    def _create_layout(self) -> Layout:
        """Cria o layout principal"""
        layout = Layout()
        
        # Estrutura principal
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3)
        )
        
        # Divide o corpo em painéis
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="center", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Subdivide o painel central
        layout["center"].split_column(
            Layout(name="market", size=8),
            Layout(name="signals", size=10),
            Layout(name="positions", ratio=1)
        )
        
        # Subdivide painéis laterais
        layout["left"].split_column(
            Layout(name="tape", size=10),
            Layout(name="behaviors", ratio=1)
        )
        
        layout["right"].split_column(
            Layout(name="history", size=15),
            Layout(name="stats", ratio=1)
        )
        
        return layout
    
    def update(self, data: Dict):
        """Atualiza todos os painéis com novos dados"""
        try:
            # Header
            self._update_header(data.get('signals_today', 0))
            
            # Market Data
            self._update_market(data.get('market', {}))
            
            # Tape Reading
            self._update_tape(data.get('tape', {}))
            
            # Signals/Positions
            if data.get('positions'):
                self._update_positions(data.get('positions', []))
            elif data.get('signal'):
                self._update_signal(data.get('signal'))
            else:
                self._update_monitoring(data.get('market', {}))
            
            # Behaviors
            self._update_behaviors(data.get('behaviors', []))
            
            # History
            self._update_history(data.get('history', []))
            
            # Stats
            self._update_stats(data.get('stats', {}))
            
            # Footer
            self._update_footer(data.get('system_health', {}))
            
        except Exception as e:
            logger.error(f"Erro ao atualizar display: {e}")
    
    def _update_header(self, signals_today: int):
        """Atualiza o cabeçalho"""
        header_text = Text()
        header_text.append("ARBITRAGEM WDO/DOL v5.2", style="bold cyan")
        header_text.append(" | ", style="white")
        header_text.append(f"{datetime.now().strftime('%H:%M:%S')}", style="yellow")
        header_text.append(" | ", style="white")
        header_text.append(f"Sinais Hoje: {signals_today}", style="green")
        
        self.layout["header"].update(
            Panel(Align.center(header_text), style="blue")
        )
    
    def _update_market(self, market_data: Dict):
        """Atualiza painel de mercado"""
        table = Table(show_header=False, box=None, padding=(0, 1))
        
        # Preços
        wdo_price = market_data.get('wdo_price', 0)
        dol_price = market_data.get('dol_price', 0)
        spread = market_data.get('spread', 0)
        z_score = market_data.get('z_score', 0)
        
        # Cores baseadas no z-score
        if abs(z_score) > 2.0:
            z_color = "red bold"
        elif abs(z_score) > 1.5:
            z_color = "yellow bold"
        elif abs(z_score) > 1.0:
            z_color = "yellow"
        else:
            z_color = "white"
        
        table.add_row("WDO:", f"[bold]{wdo_price:.2f}[/bold]", 
                      "DOL:", f"[bold]{dol_price:.2f}[/bold]")
        table.add_row("Spread:", f"[{z_color}]{spread:.2f}[/{z_color}]",
                      "Z-Score:", f"[{z_color}]{z_score:+.2f}σ[/{z_color}]")
        table.add_row("Média:", f"{market_data.get('mean', 0):.2f}",
                      "Desvio:", f"{market_data.get('std', 0):.2f}")
        
        # Barra de progresso do Z-Score
        z_progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=20),
            TextColumn("{task.percentage:.0f}%"),
            expand=False
        )
        
        z_task = z_progress.add_task(
            "Z-Score", 
            total=3.0, 
            completed=min(abs(z_score), 3.0)
        )
        
        panel_content = Columns([table, z_progress], padding=(1, 2))
        
        self.layout["market"].update(
            Panel(panel_content, title="[cyan]Mercado[/cyan]", border_style="cyan")
        )
    
    def _update_tape(self, tape_data: Dict):
        """Atualiza painel de tape reading"""
        if not tape_data or not tape_data.get('has_data'):
            self.layout["tape"].update(
                Panel("Aguardando dados...", title="[magenta]Tape Reading[/magenta]", 
                      border_style="magenta")
            )
            return
        
        table = Table(show_header=False, box=None)
        
        buy_pct = tape_data.get('buy_percentage', 0)
        sell_pct = tape_data.get('sell_percentage', 0)
        
        # Determina a direção
        if buy_pct > 60:
            direction = "[green]↑ COMPRA[/green]"
        elif sell_pct > 60:
            direction = "[red]↓ VENDA[/red]"
        else:
            direction = "[yellow]→ NEUTRO[/yellow]"
        
        table.add_row("Direção:", direction)
        table.add_row("Compra:", f"[green]{buy_pct:.1f}%[/green]")
        table.add_row("Venda:", f"[red]{sell_pct:.1f}%[/red]")
        # CORREÇÃO: Usando a chave correta 'total_trades_session'
        table.add_row("Trades:", str(tape_data.get('total_trades_session', 0)))
        
        self.layout["tape"].update(
            Panel(table, title="[magenta]Tape Reading[/magenta]", border_style="magenta")
        )
    
    def _update_signal(self, signal: Dict):
        """Atualiza painel quando há sinal"""
        if not signal:
            return
        
        # Determina cores e símbolos
        if signal['action'] == 'COMPRA':
            action_color = "green"
            arrow = "↑"
        else:
            action_color = "red"
            arrow = "↓"
        
        # Título com destaque
        title = f"[bold {action_color}]{arrow} SINAL DE {signal['action']}![/bold {action_color}]"
        
        # Conteúdo
        table = Table(show_header=False, box=None)
        table.add_row("Ativo:", f"[bold]{signal.get('asset', 'DÓLAR')}[/bold]")
        table.add_row("Entrada:", f"[bold yellow]{signal.get('entry', 0):.2f}[/bold yellow]")
        table.add_row("Alvo 1:", f"[green]{signal.get('targets', [0,0])[0]:.2f}[/green]")
        table.add_row("Alvo 2:", f"[green]{signal.get('targets', [0,0])[1]:.2f}[/green]")
        table.add_row("Stop:", f"[red]{signal.get('stop', 0):.2f}[/red]")
        table.add_row("Confiança:", f"[cyan]{signal.get('confidence', 0):.0f}%[/cyan]")
        table.add_row("Contratos:", f"[bold]{signal.get('contracts', 0)}[/bold]")
        
        # Gatilhos
        gatilhos = signal.get('gatilhos', [])
        if gatilhos:
            gatilhos_text = "\n".join(f"• {g}" for g in gatilhos[:3])
            table.add_row("Gatilhos:", gatilhos_text)
        
        self.layout["signals"].update(
            Panel(table, title=title, border_style=action_color, 
                  subtitle=f"Z-Score: {signal.get('z_score', 0):+.2f}")
        )
    
    def _update_monitoring(self, market_data: Dict):
        """Atualiza painel quando está monitorando"""
        z_score = market_data.get('z_score', 0)
        spread = market_data.get('spread', 0)
        
        monitoring_text = Text()
        monitoring_text.append("👁  Monitorando oportunidades...\n\n", style="yellow")
        monitoring_text.append(f"Spread atual: {spread:.2f}\n", style="white")
        monitoring_text.append(f"Z-Score: {z_score:+.2f}σ\n", style="cyan")
        
        if abs(z_score) > 1.0:
            monitoring_text.append("\n⚡ Aproximando-se do threshold!", style="yellow bold")
        
        self.layout["signals"].update(
            Panel(Align.center(monitoring_text, vertical="middle"), 
                  title="[yellow]Aguardando Sinal[/yellow]", border_style="yellow")
        )
    
    def _update_positions(self, positions: List[Dict]):
        """Atualiza painel de posições ativas"""
        if not positions:
            self.layout["positions"].update(
                Panel("Nenhuma posição ativa", title="[blue]Posições[/blue]", 
                      border_style="blue")
            )
            return
        
        table = Table(expand=True)
        table.add_column("Ação", style="cyan")
        table.add_column("Entrada", justify="right")
        table.add_column("Atual", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("Tempo", justify="right")
        
        for pos in positions[:3]:  # Máximo 3 posições
            pnl = pos.get('pnl', 0)
            pnl_color = "green" if pnl > 0 else "red" if pnl < 0 else "yellow"
            
            table.add_row(
                pos.get('action', ''),
                f"{pos.get('entry_price', 0):.2f}",
                f"{pos.get('current_price', 0):.2f}",
                f"[{pnl_color}]R$ {pnl:+.2f}[/{pnl_color}]",
                f"{pos.get('time_minutes', 0)}m"
            )
        
        self.layout["positions"].update(
            Panel(table, title="[blue]Posições Ativas[/blue]", border_style="blue")
        )
    
    def _update_behaviors(self, behaviors: List[Dict]):
        """Atualiza painel de comportamentos"""
        if not behaviors:
            self.layout["behaviors"].update(
                Panel("Nenhum comportamento detectado", 
                      title="[yellow]Comportamentos[/yellow]", border_style="yellow")
            )
            return
        
        table = Table(show_header=False, box=None)
        
        for behavior in behaviors[:5]:  # Máximo 5 comportamentos
            strength = behavior.get('strength', 0)
            if strength >= 80:
                strength_color = "red"
            elif strength >= 60:
                strength_color = "yellow"
            else:
                strength_color = "white"
            
            table.add_row(
                behavior.get('type', 'Unknown'),
                f"[{strength_color}]{strength:.0f}%[/{strength_color}]"
            )
        
        self.layout["behaviors"].update(
            Panel(table, title="[yellow]Comportamentos[/yellow]", border_style="yellow")
        )
    
    def _update_history(self, history: List[Dict]):
        """Atualiza histórico de sinais"""
        if not history:
            self.layout["history"].update(
                Panel("Nenhum sinal anterior", title="[cyan]Histórico[/cyan]", 
                      border_style="cyan")
            )
            return
        
        table = Table(expand=True, show_header=True)
        table.add_column("Hora", style="dim", width=5)
        table.add_column("Ação", width=6)
        table.add_column("Preço", justify="right", width=7)
        table.add_column("Result", justify="right", width=8)
        
        for signal in history[:10]:  # Últimos 10 sinais
            status = signal.get('status', 'active')
            if status == 'success':
                result = f"[green]+R${signal.get('profit', 0):.0f}[/green]"
            elif status == 'failed':
                result = f"[red]-R${abs(signal.get('loss', 0)):.0f}[/red]"
            else:
                result = "[yellow]...[/yellow]"
            
            action_color = "green" if signal.get('action') == 'COMPRA' else "red"
            
            table.add_row(
                signal.get('time', ''),
                f"[{action_color}]{signal.get('action', '')[:6]}[/{action_color}]",
                f"{signal.get('price', 0):.2f}",
                result
            )
        
        self.layout["history"].update(
            Panel(table, title="[cyan]Histórico[/cyan]", border_style="cyan")
        )
    
    def _update_stats(self, stats: Dict):
        """Atualiza estatísticas"""
        table = Table(show_header=False, box=None)
        
        total_pnl = stats.get('total_pnl', 0)
        pnl_color = "green" if total_pnl > 0 else "red" if total_pnl < 0 else "yellow"
        
        win_rate = stats.get('win_rate', 0)
        wr_color = "green" if win_rate >= 60 else "yellow" if win_rate >= 40 else "red"
        
        table.add_row("P&L Total:", f"[{pnl_color}]R$ {total_pnl:.2f}[/{pnl_color}]")
        table.add_row("Win Rate:", f"[{wr_color}]{win_rate:.1f}%[/{wr_color}]")
        table.add_row("Trades:", str(stats.get('total_positions', 0)))
        table.add_row("Ativas:", str(stats.get('active_positions', 0)))
        
        self.layout["stats"].update(
            Panel(table, title="[green]Estatísticas[/green]", border_style="green")
        )
    
    def _update_footer(self, health: Dict):
        """Atualiza rodapé com status do sistema"""
        errors = health.get('data_errors', 0)
        if errors > 0:
            status = f"[yellow]⚠ Erros de dados: {errors}[/yellow]"
        else:
            status = "[green]✓ Sistema operando normalmente[/green]"
        
        # CORREÇÃO: Usando Text.from_markup() para processar as tags de cor
        self.layout["footer"].update(
            Panel(Align.center(Text.from_markup(status)), style="dim")
        )
    
    def render(self):
        """Renderiza o display (para compatibilidade)"""
        if not self._started:
            self.live.start()
            self._started = True
        self.live.refresh()
    
    def stop(self):
        """Para o display"""
        if self._started:
            self.live.stop()
            self._started = False
    
    def __del__(self):
        """Garante que o Live seja parado"""
        self.stop()