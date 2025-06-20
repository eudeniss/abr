import os
import yaml
import logging
from typing import Dict, Any, Optional
# Remover a importação incorreta de DataProvider aqui

logger = logging.getLogger(__name__)

class ConfigManager:
    """Gerenciador de configurações"""
    
    def __init__(self, config_dir: str = "./config", env: str = "production"):
        self.config_dir = config_dir
        self.env = env
        self.config = {}
        self._load_configs()
        
    def _load_configs(self):
        """Carrega todos os arquivos de configuração"""
        try:
            # Carrega config base
            base_config_path = os.path.join(self.config_dir, "base.yaml")
            if os.path.exists(base_config_path):
                with open(base_config_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
                    logger.info(f"Config base carregado de {base_config_path}")
            
            # Carrega config do ambiente específico
            env_config_path = os.path.join(self.config_dir, f"{self.env}.yaml")
            if os.path.exists(env_config_path):
                with open(env_config_path, 'r', encoding='utf-8') as f:
                    env_config = yaml.safe_load(f)
                    self._merge_configs(self.config, env_config)
                    logger.info(f"Config do ambiente {self.env} carregado de {env_config_path}")
            
            # Carrega configurações específicas (excel.yaml, etc)
            for filename in os.listdir(self.config_dir):
                if filename.endswith('.yaml') and filename not in ['base.yaml', f'{self.env}.yaml']:
                    filepath = os.path.join(self.config_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        specific_config = yaml.safe_load(f)
                        self._merge_configs(self.config, specific_config)
                        logger.info(f"Config específico carregado de {filepath}")
            
            logger.info("Todas as configurações carregadas com sucesso")
            logger.debug(f"Configuração final: {self.config}")
            
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}")
            raise
    
    def _merge_configs(self, base: Dict, override: Dict):
        """Mescla configurações recursivamente"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_configs(base[key], value)
            else:
                base[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém uma configuração usando notação de ponto"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_provider_config(self, provider_type: str) -> Optional[Dict[str, Any]]:
        """Obtém configuração específica de um provider"""
        # Retorna a configuração completa do provider
        return self.config.get(provider_type, {})
    
    def get_all(self) -> Dict[str, Any]:
        """Retorna todas as configurações"""
        return self.config.copy()
    
    def reload(self):
        """Recarrega as configurações"""
        self.config = {}
        self._load_configs()
        logger.info("Configurações recarregadas")