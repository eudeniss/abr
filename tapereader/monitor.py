# monitor.py
import sys, os, time, logging
import asyncio  # Adicionado para suporte assíncrono
from datetime import datetime
from collections import deque
from typing import Deque, Dict, List, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.config import ConfigManager
from src.data.excel_provider import ExcelDataProvider
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.logging import RichHandler

logging.basicConfig(level="INFO", format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True, show_path=False)])
log = logging.getLogger("rich")

class SimpleAnalyzer:
    def __init__(self, config): self.config = config
    def analyze_flow(self, trades):
        if not trades: return {'flow_bias': 'NEUTRAL', 'delta_percent': 0}
        buy_volume = sum(t.get('volume', 0) for t in trades if 'COMPRADOR' in t.get('side', '').upper() or 'BUY' in t.get('side', '').upper())
        sell_volume = sum(t.get('volume', 0) for t in trades if 'VENDEDOR' in t.get('side', '').upper() or 'SELL' in t.get('side', '').upper())
        total_volume = buy_volume + sell_volume
        if total_volume == 0: return {'flow_bias': 'NEUTRAL', 'delta_percent': 0}
        delta = buy_volume - sell_volume; delta_percent = (delta / total_volume) * 100
        bias_threshold = self.config.get('flow_bias_threshold_percent', 20)
        if delta_percent > bias_threshold: bias = 'BULLISH'
        elif delta_percent < -bias_threshold: bias = 'BEARISH'
        else: bias = 'NEUTRAL'
        return {'flow_bias': bias, 'delta_percent': delta_percent}
    def analyze_volatility(self, trades):
        if len(trades) < 2: return {'volatility': 'LOW'}
        prices = [t['price'] for t in trades if t.get('price') is not None]
        if not prices: return {'volatility': 'LOW'}
        price_range, avg_price = max(prices) - min(prices), sum(prices) / len(prices)
        if avg_price > 0:
            volatility_pct = (price_range / avg_price) * 100
            if volatility_pct > self.config.get('volatility_high_threshold_pct', 0.5): return {'volatility': 'HIGH'}
            elif volatility_pct > self.config.get('volatility_medium_threshold_pct', 0.2): return {'volatility': 'MEDIUM'}
        return {'volatility': 'LOW'}
    def analyze_book_pressure(self, book):
        if not book or not book.get('bids') or not book.get('asks'): return {'pressure': 'NEUTRAL', 'ratio': 0}
        levels = self.config.get('book_pressure_levels', 10)
        bid_volume = sum(b['volume'] for b in book['bids'][:levels]); ask_volume = sum(a['volume'] for a in book['asks'][:levels])
        if bid_volume + ask_volume == 0: return {'pressure': 'NEUTRAL', 'ratio': 0}
        ratio = bid_volume / (bid_volume + ask_volume)
        if ratio > self.config.get('book_pressure_buy_threshold', 0.65): return {'pressure': 'BUY', 'ratio': ratio}
        elif ratio < self.config.get('book_pressure_sell_threshold', 0.35): return {'pressure': 'SELL', 'ratio': ratio}
        else: return {'pressure': 'NEUTRAL', 'ratio': ratio}

def make_layout():
    layout = Layout(name="root"); layout.split(Layout(name="header", size=3), Layout(name="summary", size=5), Layout(ratio=1, name="main"), Layout(name="footer", size=5)); layout["main"].split_row(Layout(name="wdo"), Layout(name="dol")); layout["wdo"].split_column(Layout(name="wdo_trades", minimum_size=15), Layout(name="wdo_book")); layout["dol"].split_column(Layout(name="dol_trades", minimum_size=15), Layout(name="dol_book")); return layout
def create_trades_table(title, trades, display_rows):
    table = Table(title=title, expand=True, padding=(0, 1), title_style="bold"); table.add_column("Data", justify="right", style="dim", width=14); table.add_column("Agressor", width=10); table.add_column("Valor", justify="right", style="bright_white", width=10); table.add_column("Qtde", justify="right", width=8)
    display_trades = list(trades)[-display_rows:]
    for trade in reversed(display_trades): # Mostra o mais recente no topo
        side_text = trade.get('side', '').upper()
        if 'COMPRADOR' in side_text or 'BUY' in side_text: color, aggressor_display = "green", "COMPRADOR"
        else: color, aggressor_display = "red", "VENDEDOR"
        table.add_row(trade['timestamp'], f"[{color}]{aggressor_display}[/{color}]", f"{trade['price']:.2f}", str(trade['volume']))
    return table
def create_book_table(title, bids, asks, display_rows):
    table = Table(title=title, expand=True, padding=(0, 1), title_style="bold"); table.add_column("Hora C.", justify="center", style="dim", width=9); table.add_column("ID C.", justify="right", style="dim", no_wrap=True, width=14); table.add_column("Qtde C.", justify="right", width=7); table.add_column("Compra", justify="right", style="green", width=10); table.add_column("Venda", justify="left", style="red", width=10); table.add_column("Qtde V.", justify="left", width=7); table.add_column("ID V.", justify="left", style="dim", no_wrap=True, width=14); table.add_column("Hora V.", justify="center", style="dim", width=9)
    for i in range(display_rows):
        bid_hora, bid_id, bid_vol, bid_prc = ("", "", "", "");
        if i < len(bids): bid_hora, bid_id, bid_vol, bid_prc = bids[i].get('hora', ""), bids[i].get('id', ""), str(bids[i]['volume']), f"{bids[i]['price']:.2f}"
        ask_prc, ask_vol, ask_id, ask_hora = ("", "", "", "");
        if i < len(asks): ask_prc, ask_vol, ask_id, ask_hora = f"{asks[i]['price']:.2f}", str(asks[i]['volume']), asks[i].get('id', ""), asks[i].get('hora', "")
        table.add_row(bid_hora, bid_id, bid_vol, bid_prc, ask_prc, ask_vol, ask_id, ask_hora)
    return table
def generate_summary_panel(wdo_analysis, dol_analysis):
    def get_color(bias): return "green" if bias == 'BULLISH' else "red" if bias == 'BEARISH' else "yellow"
    wdo_color, dol_color = get_color(wdo_analysis['flow']['flow_bias']), get_color(dol_analysis['flow']['flow_bias']); wdo_text = f"[cyan]WDO:[/cyan] Fluxo [{wdo_color}]{wdo_analysis['flow']['flow_bias']}[/] ({wdo_analysis['flow']['delta_percent']:+.1f}%) | Volatilidade {wdo_analysis['volatility']['volatility']} | Book {wdo_analysis['book']['pressure']} ({wdo_analysis['book']['ratio']:.2f})"; dol_text = f"[magenta]DOL:[/magenta] Fluxo [{dol_color}]{dol_analysis['flow']['flow_bias']}[/] ({dol_analysis['flow']['delta_percent']:+.1f}%) | Volatilidade {dol_analysis['volatility']['volatility']} | Book {dol_analysis['book']['pressure']} ({dol_analysis['book']['ratio']:.2f})"; return Panel(Text.from_markup(f"{wdo_text}\n{dol_text}", justify="left"), title="[bold]📊 Resumo da Análise[/bold]", border_style="blue", expand=False)
def generate_footer(session_stats, status_message: str):
    wdo_total_vol = session_stats['WDOFUT']['buy_vol'] + session_stats['WDOFUT']['sell_vol']; dol_total_vol = session_stats['DOLFUT']['buy_vol'] + session_stats['DOLFUT']['sell_vol']; wdo_delta, dol_delta = (session_stats['WDOFUT']['buy_vol'] - session_stats['WDOFUT']['sell_vol']), (session_stats['DOLFUT']['buy_vol'] - session_stats['DOLFUT']['sell_vol']); wdo_delta_pct, dol_delta_pct = ((wdo_delta / wdo_total_vol * 100) if wdo_total_vol > 0 else 0), ((dol_delta / dol_total_vol * 100) if dol_total_vol > 0 else 0); wdo_stats = f"WDO: {session_stats['WDOFUT']['total']} trades | Vol Compra: {session_stats['WDOFUT']['buy_vol']:,} | Vol Venda: {session_stats['WDOFUT']['sell_vol']:,} | Delta: {wdo_delta:+,} ({wdo_delta_pct:+.1f}%)"; dol_stats = f"DOL: {session_stats['DOLFUT']['total']} trades | Vol Compra: {session_stats['DOLFUT']['buy_vol']:,} | Vol Venda: {session_stats['DOLFUT']['sell_vol']:,} | Delta: {dol_delta:+,} ({dol_delta_pct:+.1f}%)"; status_line = f"\n[dim]Status:[/] {status_message}"; return Panel(Text.from_markup(f"{wdo_stats}\n{dol_stats}{status_line}", justify="left"), title="[bold]📈 Estatísticas da Sessão[/bold]", border_style="dim", expand=False)

# Função main agora é assíncrona
async def main():
    console = Console(); data_provider = None
    try:
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config'); config_manager = ConfigManager(config_dir=config_dir, env='production'); excel_config = config_manager.get('excel', {}); display_config = excel_config.get('display', {}); update_interval = excel_config.get('update_interval', 0.2); trades_rows = display_config.get('trades_rows', 30); book_rows = display_config.get('book_rows', 10)
        data_provider = ExcelDataProvider(excel_config, None)
        await data_provider.initialize()  # Aguarda a inicialização
        analyzer = SimpleAnalyzer(display_config); wdo_trades_history, dol_trades_history = deque(maxlen=500), deque(maxlen=500); processed_trade_keys: Set[tuple] = set(); session_stats = {'WDOFUT': {'total': 0, 'buy_vol': 0, 'sell_vol': 0}, 'DOLFUT': {'total': 0, 'buy_vol': 0, 'sell_vol': 0}}; layout = make_layout(); status_message = "[green]Monitorando...[/green]"
        with Live(layout, screen=True, redirect_stderr=False, console=console, refresh_per_second=4) as live:
            console.print("[bold green]✅ Monitor iniciado. Pressione Ctrl+C para sair.[/bold green]")
            try:
                await asyncio.sleep(1)  # Usa asyncio.sleep ao invés de time.sleep
            except asyncio.CancelledError:
                pass  # Ignora o erro de cancelamento
            while True:
                try:
                    snapshot = await data_provider.get_market_snapshot()  # Aguarda o snapshot
                    if not snapshot: 
                        status_message = "[yellow]Aguardando dados...[/yellow]"
                        await asyncio.sleep(update_interval)  # Usa asyncio.sleep
                        continue
                    status_message = f"[green]OK - Última atualização: {datetime.now().strftime('%H:%M:%S')}[/green]"
                    new_trades_count = 0
                    for trades_list, symbol, history in [(snapshot['wdofut']['trades'], 'WDOFUT', wdo_trades_history), (snapshot['dolfut']['trades'], 'DOLFUT', dol_trades_history)]:
                        for trade in reversed(trades_list):
                            trade_key = (trade['timestamp'], trade['symbol'], trade['side'], trade['price'], trade['volume'])
                            if trade_key not in processed_trade_keys:
                                processed_trade_keys.add(trade_key); new_trades_count += 1
                                history.append(trade); session_stats[symbol]['total'] += 1
                                if 'COMPRADOR' in trade['side'].upper() or 'BUY' in trade['side'].upper(): session_stats[symbol]['buy_vol'] += trade['volume']
                                else: session_stats[symbol]['sell_vol'] += trade['volume']
                    if new_trades_count > 0: status_message = f"{status_message} | [yellow]Novos: {new_trades_count}[/yellow]"
                    wdo_analysis = {'flow': analyzer.analyze_flow(list(wdo_trades_history)[-50:]), 'volatility': analyzer.analyze_volatility(list(wdo_trades_history)[-50:]), 'book': analyzer.analyze_book_pressure(snapshot['wdofut']['book'])}; dol_analysis = {'flow': analyzer.analyze_flow(list(dol_trades_history)[-50:]), 'volatility': analyzer.analyze_volatility(list(dol_trades_history)[-50:]), 'book': analyzer.analyze_book_pressure(snapshot['dolfut']['book'])}
                    layout["header"].update(Text(f"Monitor de Mercado TapeReader | {datetime.now().strftime('%H:%M:%S')}", justify="center", style="bold white on blue")); layout["summary"].update(generate_summary_panel(wdo_analysis, dol_analysis)); layout["wdo_trades"].update(create_trades_table("[bold cyan]WDOFUT - Times & Trades[/bold cyan]", wdo_trades_history, trades_rows)); layout["wdo_book"].update(create_book_table("[bold cyan]WDOFUT - Livro[/bold cyan]", snapshot['wdofut']['book'].get('bids',[]), snapshot['wdofut']['book'].get('asks',[]), book_rows)); layout["dol_trades"].update(create_trades_table("[bold magenta]DOLFUT - Times & Trades[/bold magenta]", dol_trades_history, trades_rows)); layout["dol_book"].update(create_book_table("[bold magenta]DOLFUT - Livro[/bold magenta]", snapshot['dolfut']['book'].get('bids',[]), snapshot['dolfut']['book'].get('asks',[]), book_rows))
                    layout["footer"].update(generate_footer(session_stats, status_message))
                except asyncio.CancelledError:
                    # Captura o erro de cancelamento do asyncio sem logar
                    break
                except Exception as e: 
                    status_message = f"[bold red]ERRO: {e}[/bold red]"
                    log.error("Erro no loop principal:", exc_info=e)
                await asyncio.sleep(update_interval)  # Usa asyncio.sleep
    except (KeyboardInterrupt, asyncio.CancelledError): 
        pass  # Saída limpa sem mensagens de erro
    finally:
        if data_provider: 
            try:
                await data_provider.close()  # Aguarda o fechamento
            except:
                pass  # Ignora erros ao fechar
        console.print("\n[bold]Monitor encerrado.[/bold]")

# Executa a função main usando asyncio
if __name__ == "__main__":
    try:
        # Garante que o loop de eventos correto seja usado no Windows
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(main())
    except KeyboardInterrupt:
        # Captura a interrupção final do asyncio.run() e sai de forma limpa
        print("\nSaída controlada. Retornando ao menu...")
    except Exception as e:
        # Captura qualquer outro erro inesperado
        print(f"\nErro inesperado: {e}")
        print("Retornando ao menu...")