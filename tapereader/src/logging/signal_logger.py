"""
Sistema de Logging de Sinais - Versão Otimizada
Combina eficiência do original com melhorias da refatoração
"""
import json
import csv
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from collections import deque
import threading

from src.core.logger import get_logger

logger = get_logger(__name__)


class SignalLogger:
    """Registra todos os sinais gerados para análise posterior"""
    
    def __init__(self, config: Dict = None):
        config = config or {}
        
        # Configuração de diretório com fallback robusto
        log_dir_config = config.get('log_dir', 'logs/arbitrage')
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.log_dir = base_dir / log_dir_config
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurações
        self.buffer_size = config.get('buffer_size', 10)
        self.formats = config.get('formats', ['jsonl', 'csv'])
        self.debug_mode = config.get('debug', False)
        
        # Buffer thread-safe
        self.buffer = []
        self.lock = threading.Lock()
        
        # Arquivos do dia
        today = datetime.now().strftime("%Y%m%d")
        self.jsonl_file = self.log_dir / f"signals_{today}.jsonl"
        self.csv_file = self.log_dir / f"signals_{today}.csv"
        
        # Contador eficiente (lê arquivo uma vez)
        self._signal_counter = self._init_counter()
        
        # Inicializa CSV se necessário
        if 'csv' in self.formats:
            self._init_csv()
            
        # Testa permissões uma vez
        self._verify_permissions()
        
        logger.info(f"SignalLogger inicializado em: {self.log_dir}")
    
    def _init_counter(self) -> int:
        """Inicializa contador lendo arquivo uma vez"""
        if self.jsonl_file.exists():
            try:
                with open(self.jsonl_file, 'r') as f:
                    return sum(1 for _ in f)
            except Exception:
                return 0
        return 0
    
    def _verify_permissions(self):
        """Verifica permissões de escrita uma vez"""
        try:
            test_file = self.log_dir / '.write_test'
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            logger.error(f"Sem permissão de escrita em {self.log_dir}: {e}")
            raise
    
    def _init_csv(self):
        """Inicializa CSV com headers"""
        if not self.csv_file.exists():
            headers = [
                'timestamp', 'signal_id', 'action', 'asset', 'price',
                'confidence', 'contracts', 'expected_profit', 'risk',
                'spread', 'z_score', 'gatilhos', 'status'
            ]
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(headers)
    
    def _generate_signal_id(self) -> str:
        """Gera ID único usando contador em memória (eficiente)"""
        with self.lock:
            self._signal_counter += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"SIG_{timestamp}_{self._signal_counter:04d}"
    
    def log_signal(self, signal_data: Dict) -> str:
        """Registra um sinal gerado"""
        with self.lock:
            signal_data['timestamp'] = datetime.now().isoformat()
            signal_data['signal_id'] = self._generate_signal_id()
            
            self.buffer.append(signal_data)
            
            logger.info(f"Sinal registrado: {signal_data['signal_id']} - "
                       f"{signal_data.get('action')} @ {signal_data.get('price', 0):.2f}")
            
            if self.debug_mode:
                logger.debug(f"Buffer: {len(self.buffer)}/{self.buffer_size}")
            
            if len(self.buffer) >= self.buffer_size:
                self._flush_buffer()
            
            return signal_data['signal_id']
    
    def _flush_buffer(self):
        """Escreve buffer nos arquivos de forma eficiente"""
        if not self.buffer:
            return
        
        buffer_copy = self.buffer.copy()
        self.buffer.clear()
        
        try:
            # JSONL
            if 'jsonl' in self.formats:
                with open(self.jsonl_file, 'a', encoding='utf-8') as f:
                    for signal in buffer_copy:
                        f.write(json.dumps(signal, ensure_ascii=False) + '\n')
            
            # CSV
            if 'csv' in self.formats:
                with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    for signal in buffer_copy:
                        row = [
                            signal.get('timestamp', ''),
                            signal.get('signal_id', ''),
                            signal.get('action', ''),
                            signal.get('asset', ''),
                            signal.get('price', 0),
                            signal.get('confidence', 0),
                            signal.get('contracts', 0),
                            signal.get('expected_profit', 0),
                            signal.get('risk', 0),
                            signal.get('spread', 0),
                            signal.get('z_score', 0),
                            '|'.join(str(g) for g in signal.get('gatilhos', [])),
                            signal.get('status', 'GERADO')
                        ]
                        writer.writerow(row)
            
            logger.debug(f"{len(buffer_copy)} sinais salvos")
            
        except Exception as e:
            logger.error(f"Erro ao salvar buffer: {e}")
            # Re-adiciona ao buffer em caso de erro
            with self.lock:
                self.buffer = buffer_copy + self.buffer
    
    def flush_buffer(self):
        """Força flush do buffer (público)"""
        with self.lock:
            self._flush_buffer()
    
    def get_daily_stats(self) -> Dict:
        """Retorna estatísticas do dia"""
        self.flush_buffer()  # Garante dados atualizados
        
        stats = {
            'total_signals': 0,
            'by_confidence': {'60-69': 0, '70-79': 0, '80-89': 0, '90+': 0},
            'by_action': {'COMPRA': 0, 'VENDA': 0},
            'avg_confidence': 0,
            'total_expected_profit': 0,
            'log_dir': str(self.log_dir)
        }
        
        if not self.jsonl_file.exists():
            return stats
        
        confidences = []
        profits = []
        
        try:
            with open(self.jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        signal = json.loads(line)
                        stats['total_signals'] += 1
                        
                        # Confiança
                        conf = signal.get('confidence', 0)
                        confidences.append(conf)
                        
                        if 60 <= conf < 70:
                            stats['by_confidence']['60-69'] += 1
                        elif 70 <= conf < 80:
                            stats['by_confidence']['70-79'] += 1
                        elif 80 <= conf < 90:
                            stats['by_confidence']['80-89'] += 1
                        elif conf >= 90:
                            stats['by_confidence']['90+'] += 1
                        
                        # Ação
                        action = signal.get('action', '')
                        if action in stats['by_action']:
                            stats['by_action'][action] += 1
                        
                        # Lucro esperado
                        profit = signal.get('expected_profit', 0)
                        if profit > 0:
                            profits.append(profit)
                            
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas: {e}")
        
        if confidences:
            stats['avg_confidence'] = sum(confidences) / len(confidences)
        if profits:
            stats['total_expected_profit'] = sum(profits)
        
        return stats
    
    def __del__(self):
        """Garante flush ao destruir objeto"""
        if hasattr(self, 'buffer') and self.buffer:
            self._flush_buffer()


class SignalHistoryManager:
    """Gerencia histórico visual dos últimos N sinais"""
    
    def __init__(self, config: Dict = None):
        config = config or {}
        self.max_signals = config.get('max_signals', 5)
        self.signals = deque(maxlen=self.max_signals)
    
    def add_signal(self, signal_data: Dict):
        """Adiciona sinal ao histórico"""
        summary = {
            'time': datetime.now().strftime("%H:%M"),
            'action': signal_data.get('action', ''),
            'price': signal_data.get('entry', signal_data.get('price', 0)),
            'confidence': signal_data.get('confidence', 0),
            'status': 'active',
            'profit': 0,
            'loss': 0
        }
        self.signals.append(summary)
    
    def update_last_signal_status(self, status: str, value: float = 0):
        """Atualiza status do último sinal (mantém API original)"""
        if self.signals:
            self.signals[-1]['status'] = status
            if status == 'success':
                self.signals[-1]['profit'] = value
            elif status == 'failed':
                self.signals[-1]['loss'] = value
    
    def update_signal_status(self, index: int, status: str, value: float = 0):
        """Atualiza status de um sinal específico (nova API)"""
        if 0 <= index < len(self.signals):
            self.signals[index]['status'] = status
            if status == 'success':
                self.signals[index]['profit'] = value
            elif status == 'failed':
                self.signals[index]['loss'] = value
    
    def get_formatted_history(self) -> List[Dict]:
        """Retorna histórico formatado"""
        return list(self.signals)


def create_signal_log_entry(**kwargs) -> Dict:
    """Cria entrada de log estruturada (compatível com ambas versões)"""
    return {
        'action': kwargs.get('action'),
        'asset': kwargs.get('asset'),
        'price': kwargs.get('price'),
        'entry': kwargs.get('price'),  # Duplicado para compatibilidade
        'confidence': kwargs.get('confidence'),
        'contracts': kwargs.get('contratos', kwargs.get('contracts')),
        'expected_profit': kwargs.get('expected_profit'),
        'risk': kwargs.get('risk'),
        'spread': kwargs.get('spread'),
        'z_score': kwargs.get('z_score'),
        'gatilhos': kwargs.get('gatilhos', []),
        'targets': kwargs.get('alvos', kwargs.get('targets', [])),
        'stop': kwargs.get('stop'),
        'leadership': kwargs.get('leadership', {}),
        'behaviors': kwargs.get('behaviors', []),
        'status': 'GERADO'
    }