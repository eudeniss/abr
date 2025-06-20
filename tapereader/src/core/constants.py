"""
Gerenciador centralizado de constantes do sistema
Carrega todas as constantes dos arquivos YAML
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import logging

logger = logging.getLogger(__name__)


class SystemConstants:
    """Singleton para gerenciar constantes do sistema"""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._load_all_constants()
            self._initialized = True
    
    def _load_all_constants(self):
        """Carrega todas as constantes dos arquivos de configuração"""
        try:
            # Determinar diretório de configurações
            current_dir = Path(__file__).parent
            config_dir = current_dir.parent.parent / 'config'
            
            # Carregar arquivo de constantes se existir
            constants_path = config_dir / 'constants.yaml'
            if constants_path.exists():
                with open(constants_path, 'r', encoding='utf-8') as f:
                    constants_data = yaml.safe_load(f)
                    self._flatten_dict(constants_data.get('constants', {}))
            
            # Carregar constantes de outros arquivos
            self._load_arbitrage_constants(config_dir)
            self._load_behavior_constants(config_dir)
            self._load_excel_constants(config_dir)
            self._load_tape_constants(config_dir)
            
            logger.info("Constantes do sistema carregadas com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao carregar constantes: {e}")
            # Definir valores padrão em caso de erro
            self._set_defaults()
    
    def _flatten_dict(self, d: Dict, parent_key: str = ''):
        """Achata dicionário aninhado em atributos"""
        for k, v in d.items():
            new_key = f"{parent_key}_{k}".upper() if parent_key else k.upper()
            if isinstance(v, dict):
                self._flatten_dict(v, new_key)
            else:
                setattr(self, new_key, v)
    
    def _load_arbitrage_constants(self, config_dir: Path):
        """Carrega constantes específicas de arbitragem"""
        arb_path = config_dir / 'arbitrage.yaml'
        if arb_path.exists():
            with open(arb_path, 'r', encoding='utf-8') as f:
                arb_data = yaml.safe_load(f)
                
                # Contratos
                contracts = arb_data.get('arbitrage', {}).get('contracts', {})
                self.DOL_POINT_VALUE = contracts.get('dol', {}).get('point_value', 10.0)
                self.DOL_TICK_VALUE = contracts.get('dol', {}).get('tick_value', 50.0)
                self.WDO_TICK_VALUE = contracts.get('wdo', {}).get('tick_value', 5.0)
                
                # Equivalência
                self.WDO_DOL_RATIO = arb_data.get('arbitrage', {}).get('equivalence', {}).get('ratio', 5.0)
                
                # Custos
                costs = arb_data.get('arbitrage', {}).get('costs', {})
                self.EMOLUMENTOS = costs.get('emolumentos_per_contract', 0.27)
                self.CORRETAGEM = costs.get('corretagem_per_contract', 0.50)
                
                # Loop principal
                self.MAIN_LOOP_SLEEP = arb_data.get('arbitrage', {}).get('operation', {}).get('main_loop_sleep', 0.1)
                
                # UI
                enhanced = arb_data.get('arbitrage_enhanced', {})
                self.PERCENTILE_CONVERSION_FACTOR = enhanced.get('display', {}).get('z_score_to_percentile_factor', 33.3)
                self.UI_ALERT_BUFFER_SIZE = enhanced.get('display', {}).get('ui_alert_buffer_size', 5)
                
                # Sons
                self.SOUND_NORMAL_FREQ = enhanced.get('alerts', {}).get('sound_frequencies', {}).get('normal_signal', 1500)
                self.SOUND_PREMIUM_FREQ = enhanced.get('alerts', {}).get('sound_frequencies', {}).get('premium_signal', 2000)
                self.SOUND_DURATION = enhanced.get('alerts', {}).get('sound_duration_ms', 300)
    
    def _load_behavior_constants(self, config_dir: Path):
        """Carrega constantes de comportamentos"""
        behav_path = config_dir / 'behaviors.yaml'
        if behav_path.exists():
            with open(behav_path, 'r', encoding='utf-8') as f:
                behav_data = yaml.safe_load(f)
                
                # Absorção
                absorption = behav_data.get('behaviors', {}).get('absorption', {})
                self.ABSORPTION_PRICE_VARIATION = absorption.get('price_variation_threshold_pct', 0.001)
                
                # Exaustão
                exhaustion = behav_data.get('behaviors', {}).get('exhaustion', {})
                momentum = exhaustion.get('momentum_analysis', {})
                self.MOMENTUM_RETRACEMENT_THRESHOLD = momentum.get('retracement_threshold', 0.236)
                self.MOMENTUM_HIGH_RETRACEMENT = momentum.get('high_retracement_threshold', 0.618)
    
    def _load_excel_constants(self, config_dir: Path):
        """Carrega constantes do Excel"""
        excel_path = config_dir / 'excel.yaml'
        if excel_path.exists():
            with open(excel_path, 'r', encoding='utf-8') as f:
                excel_data = yaml.safe_load(f)
                
                # Performance
                perf = excel_data.get('excel', {}).get('performance', {})
                self.BOOK_UPDATE_INTERVAL = perf.get('book_update_interval', 3)
                
                # Leitura
                ranges = excel_data.get('excel', {}).get('ranges', {})
                self.SUBSEQUENT_READ_ROWS = ranges.get('dolfut_trades', {}).get('subsequent_read_rows', 30)
    
    def _load_tape_constants(self, config_dir: Path):
        """Carrega constantes de tape reading"""
        tape_path = config_dir / 'tape_reading.yaml'
        if tape_path.exists():
            with open(tape_path, 'r', encoding='utf-8') as f:
                tape_data = yaml.safe_load(f)
                
                # Risk management
                risk = tape_data.get('tape_reading', {}).get('risk_management', {})
                self.TAPE_RISK_PERCENT = risk.get('risk_percent', 0.15)
                self.TAPE_TARGET_PERCENT = risk.get('target_percent', 0.25)
    
    def _set_defaults(self):
        """Define valores padrão caso falhe o carregamento"""
        # Financeiros
        self.DOL_POINT_VALUE = 10.0
        self.DOL_TICK_VALUE = 50.0
        self.WDO_TICK_VALUE = 5.0
        self.WDO_DOL_RATIO = 5.0
        
        # Performance
        self.MAIN_LOOP_SLEEP = 0.1
        self.BOOK_UPDATE_INTERVAL = 3
        self.SUBSEQUENT_READ_ROWS = 30
        
        # Comportamentos
        self.ABSORPTION_PRICE_VARIATION = 0.001
        self.MOMENTUM_RETRACEMENT_THRESHOLD = 0.236
        self.MOMENTUM_HIGH_RETRACEMENT = 0.618
        
        # UI
        self.PERCENTILE_CONVERSION_FACTOR = 33.3
        self.UI_ALERT_BUFFER_SIZE = 5
        self.SOUND_NORMAL_FREQ = 1500
        self.SOUND_PREMIUM_FREQ = 2000
        self.SOUND_DURATION = 300
        
        logger.warning("Usando valores padrão para constantes")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém uma constante por nome"""
        return getattr(self, key.upper(), default)
    
    def reload(self):
        """Recarrega todas as constantes"""
        self._initialized = False
        self.__init__()


# Instância global
constants = SystemConstants()