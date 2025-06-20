"""
Módulo para garantir estrutura de diretórios de logs
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


def ensure_log_structure() -> Tuple[bool, Dict[str, Path]]:
    """
    Garante que a estrutura de logs existe e retorna os caminhos
    
    Returns:
        Tuple[bool, Dict[str, Path]]: (sucesso, dicionário com caminhos)
    """
    paths = {}
    
    try:
        # Determinar diretório base
        current_file = os.path.abspath(__file__)
        src_dir = os.path.dirname(current_file)
        tapereader_dir = os.path.dirname(src_dir)
        parent_dir = os.path.dirname(tapereader_dir)
        logs_base = Path(parent_dir) / "logs"
        
        # Estrutura de diretórios
        log_dirs = {
            'base': logs_base,
            'arbitrage': logs_base / "arbitrage",
            'system': logs_base / "system",
            'trades': logs_base / "trades",
            'analysis': logs_base / "analysis"
        }
        
        # Criar todos os diretórios
        for name, path in log_dirs.items():
            path.mkdir(parents=True, exist_ok=True)
            paths[name] = path
            
        # Verificar permissões
        test_file = logs_base / "test_permissions.tmp"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            logger.error(f"Sem permissão de escrita em {logs_base}: {e}")
            return False, paths
            
        # Log de sucesso
        logger.info(f"Estrutura de logs criada/verificada em: {logs_base}")
        
        # Criar README nos diretórios
        readme_content = {
            'arbitrage': "# Logs de Arbitragem\n\nContém logs de sinais de arbitragem gerados pelo sistema.",
            'system': "# Logs do Sistema\n\nContém logs gerais do sistema e mensagens de debug.",
            'trades': "# Logs de Trades\n\nContém histórico de trades executados.",
            'analysis': "# Logs de Análise\n\nContém análises e relatórios gerados."
        }
        
        for dir_name, content in readme_content.items():
            readme_path = log_dirs[dir_name] / "README.md"
            if not readme_path.exists():
                readme_path.write_text(content)
                
        return True, paths
        
    except Exception as e:
        logger.error(f"Erro ao criar estrutura de logs: {e}")
        return False, paths


def get_log_paths() -> Dict[str, Path]:
    """
    Retorna os caminhos dos diretórios de log
    
    Returns:
        Dict[str, Path]: Dicionário com os caminhos
    """
    _, paths = ensure_log_structure()
    return paths


def cleanup_old_logs(days: int = 30) -> int:
    """
    Remove logs antigos
    
    Args:
        days: Número de dias para manter
        
    Returns:
        int: Número de arquivos removidos
    """
    import time
    
    paths = get_log_paths()
    removed = 0
    
    current_time = time.time()
    cutoff_time = current_time - (days * 24 * 60 * 60)
    
    for dir_path in paths.values():
        if not dir_path.exists():
            continue
            
        for file_path in dir_path.glob("*.log"):
            if file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    removed += 1
                    logger.info(f"Removido log antigo: {file_path.name}")
                except Exception as e:
                    logger.error(f"Erro ao remover {file_path}: {e}")
                    
        for file_path in dir_path.glob("*.jsonl"):
            if file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    removed += 1
                    logger.info(f"Removido log antigo: {file_path.name}")
                except Exception as e:
                    logger.error(f"Erro ao remover {file_path}: {e}")
                    
    return removed


def get_log_statistics() -> Dict[str, any]:
    """
    Retorna estatísticas sobre os logs
    
    Returns:
        Dict com estatísticas
    """
    paths = get_log_paths()
    stats = {
        'total_size_mb': 0,
        'file_count': 0,
        'by_directory': {}
    }
    
    for name, path in paths.items():
        if not path.exists():
            continue
            
        dir_stats = {
            'files': 0,
            'size_mb': 0,
            'latest_file': None,
            'oldest_file': None
        }
        
        files = list(path.glob("*.*"))
        if files:
            dir_stats['files'] = len(files)
            dir_stats['size_mb'] = sum(f.stat().st_size for f in files) / (1024 * 1024)
            
            # Encontrar mais novo e mais antigo
            files_with_time = [(f, f.stat().st_mtime) for f in files]
            files_with_time.sort(key=lambda x: x[1])
            
            if files_with_time:
                dir_stats['oldest_file'] = files_with_time[0][0].name
                dir_stats['latest_file'] = files_with_time[-1][0].name
                
        stats['by_directory'][name] = dir_stats
        stats['total_size_mb'] += dir_stats['size_mb']
        stats['file_count'] += dir_stats['files']
        
    return stats