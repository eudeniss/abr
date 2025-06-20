from asyncio.log import logger
import xlwings as xw
from datetime import datetime, time
from typing import Dict, Any, List
from src.data.provider import DataProvider
from src.core.config import ConfigManager
from src.core.constants import constants
import asyncio


class ExcelDataProvider(DataProvider):
    def __init__(self, config: Dict[str, Any], cache=None):
        super().__init__(config, cache)
        
        # Carrega configurações
        self.config_manager = ConfigManager()
        excel_config = self.config_manager.get('excel', {})
        
        self.book: xw.Book = None
        self.sheet: xw.Sheet = None
        self.ranges: Dict[str, Any] = excel_config.get('ranges', {})
        self.is_initial_load = True
        self.last_timestamp = {'WDOFUT': None, 'DOLFUT': None}
        self.last_book_data = {'wdofut': {'bids': [], 'asks': []}, 'dolfut': {'bids': [], 'asks': []}}
        
        # Usa constante para intervalo de atualização do book
        self.book_update_interval = constants.BOOK_UPDATE_INTERVAL
        self.book_update_counter = 0
        
        # Configuração de performance
        perf_config = excel_config.get('performance', {})
        self.enable_screen_updates = perf_config.get('enable_screen_updates', False)

    async def initialize(self) -> None:
        try:
            app = xw.apps.active
            if not app: 
                raise ConnectionError("Nenhuma instância do Excel está ativa.")
            
            self.book = app.books[self.config['workbook_name']]
            self.sheet = self.book.sheets[self.config['sheet_name']]
            
            # Otimização: Desabilita atualizações de tela do Excel
            if not self.enable_screen_updates:
                app.screen_updating = False
                
        except Exception as e: 
            raise ConnectionError(f"Erro ao conectar ao Excel: {e}")

    async def close(self) -> None:
        """Restaura a atualização de tela do Excel ao fechar."""
        try:
            if self.book and self.book.app:
                self.book.app.screen_updating = True
        except: 
            pass

    def _read_trades(self, range_key: str) -> List[Dict[str, Any]]:
        """Lê os trades de forma otimizada, tratando-os como uma pilha (novos no topo)."""
        trades = []
        try:
            cfg = self.ranges.get(range_key, {})
            symbol = 'WDOFUT' if 'wdo' in range_key else 'DOLFUT'
            
            # Usa constante para número de linhas subsequentes
            rows = cfg.get('max_rows', 100) if self.is_initial_load else constants.SUBSEQUENT_READ_ROWS
            
            range_str = f"{cfg['start_col']}{cfg['start_row']}:{cfg['end_col']}{cfg['start_row'] + rows - 1}"
            data = self.sheet.range(range_str).api.Value
            
            if data is None: 
                return trades
            if not isinstance(data[0], (list, tuple)): 
                data = [data]

            for row in data:
                if row[0] is not None:
                    try:
                        timestamp = self._format_time(row[0])
                        # Otimização principal: para de ler ao encontrar o último trade conhecido
                        if not self.is_initial_load and self.last_timestamp[symbol] and timestamp == self.last_timestamp[symbol]:
                            break
                        
                        trades.append({
                            'timestamp': timestamp, 
                            'side': str(row[1]), 
                            'price': float(row[2]), 
                            'volume': int(row[3]), 
                            'symbol': symbol,
                            'aggressor': True  # Assumindo que todos são agressores
                        })
                    except (ValueError, TypeError): 
                        continue
            
            if trades:
                self.last_timestamp[symbol] = trades[0]['timestamp']
                
        except Exception as e:
            logger.error(f"Erro ao ler trades: {e}")
            
        return trades
        
    def _read_book(self, range_key: str) -> Dict[str, List]:
        """Lê o book de ofertas com cache, atualizando apenas periodicamente."""
        
        # Usa configuração de intervalo de atualização
        if self.book_update_counter % self.book_update_interval != 0 and not self.is_initial_load:
            symbol_key = 'wdofut' if 'wdo' in range_key else 'dolfut'
            return self.last_book_data[symbol_key]
        
        cfg = self.ranges.get(range_key, {})
        bids, asks = [], []
        
        try:
            bid_rng = f"{cfg['hora_compra']}{cfg['start_row']}:{cfg['compra']}{cfg['start_row'] + cfg['max_rows'] - 1}"
            ask_rng = f"{cfg['venda']}{cfg['start_row']}:{cfg['hora_venda']}{cfg['start_row'] + cfg['max_rows'] - 1}"
            
            bid_data = self.sheet.range(bid_rng).api.Value
            ask_data = self.sheet.range(ask_rng).api.Value
            
            if bid_data:
                if not isinstance(bid_data[0], (list, tuple)): 
                    bid_data = [bid_data]
                for row in bid_data:
                    if row[3] is not None and row[2] is not None: 
                        bids.append({
                            'hora': self._format_time(row[0]), 
                            'id': str(int(row[1])) if row[1] else "", 
                            'volume': int(row[2]), 
                            'price': float(row[3])
                        })
                        
            if ask_data:
                if not isinstance(ask_data[0], (list, tuple)): 
                    ask_data = [ask_data]
                for row in ask_data:
                    if row[0] is not None and row[1] is not None: 
                        asks.append({
                            'price': float(row[0]), 
                            'volume': int(row[1]), 
                            'id': str(int(row[2])) if row[2] else "", 
                            'hora': self._format_time(row[3])
                        })
                        
        except Exception as e:
            logger.error(f"Erro ao ler book: {e}")
        
        book_data = {'bids': bids, 'asks': asks}
        
        # Atualiza o cache
        symbol_key = 'wdofut' if 'wdo' in range_key else 'dolfut'
        self.last_book_data[symbol_key] = book_data
        
        return book_data
    
    def _format_time(self, value: Any) -> str:
        """Formata timestamp preservando milissegundos para garantir unicidade."""
        if value is None: 
            return ""
        if isinstance(value, (datetime, time)): 
            return value.strftime('%H:%M:%S.%f')[:-3]
        
        s_value = str(value).strip()
        time_part = s_value.split(" ")[-1]
        
        if '.' in time_part:
            main, ms = time_part.split('.')
            return f"{main}.{ms.ljust(3, '0')[:3]}"
        else: 
            return f"{time_part}.000"

    async def get_market_snapshot(self) -> Dict[str, Any]:
        try:
            self.book_update_counter += 1
            
            wdo_trades = self._read_trades('wdofut_trades')
            dol_trades = self._read_trades('dolfut_trades')
            
            wdo_book = self._read_book('wdofut_book')
            dol_book = self._read_book('dolfut_book')
            
            if self.is_initial_load: 
                self.is_initial_load = False
            
            return {
                'wdofut': {'trades': wdo_trades, 'book': wdo_book}, 
                'dolfut': {'trades': dol_trades, 'book': dol_book}, 
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.error(f"Erro ao obter snapshot: {e}")
            return None