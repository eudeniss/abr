"""
Logger integrado com gerenciamento de estrutura de logs
Salva logs em arquivos e mostra no console
"""
import logging
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# ======================== LOGGING BÁSICO ========================

def get_logger(name):
    """Retorna logger configurado com arquivo e console"""
    # Criar logger
    logger = logging.getLogger(name)
    
    # Se já tem handlers, retorna
    if logger.handlers:
        return logger
    
    # Configurar nível
    logger.setLevel(logging.DEBUG)
    
    # Garantir estrutura de logs existe
    ensure_log_structure()
    
    # Criar pasta de logs se não existir
    try:
        # Caminho para logs/system
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        parent_dir = os.path.dirname(project_root)
        log_dir = os.path.join(parent_dir, 'logs', 'system')
        os.makedirs(log_dir, exist_ok=True)
        
        # Nome do arquivo de log
        log_file = os.path.join(log_dir, f'system_{datetime.now().strftime("%Y%m%d")}.log')
        
        # Handler para arquivo
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Formato para arquivo
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        logger.addHandler(file_handler)
        
    except Exception as e:
        print(f"[Logger] Não foi possível criar arquivo de log: {e}")
    
    # Handler para console (apenas warnings e erros)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    
    # Formato simples para console
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(console_handler)
    
    return logger


# ======================== ESTRUTURA DE LOGS ========================

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
            'analysis': logs_base / "analysis",
            'debug': logs_base / "debug"  # <-- ESTA É A LINHA ADICIONADA
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
            logging.error(f"Sem permissão de escrita em {logs_base}: {e}")
            return False, paths
            
        # Log de sucesso (apenas uma vez)
        if not hasattr(ensure_log_structure, '_logged'):
            logging.info(f"Estrutura de logs criada/verificada em: {logs_base}")
            ensure_log_structure._logged = True
        
        # Criar README nos diretórios (se não existir)
        readme_content = {
            'arbitrage': "# Logs de Arbitragem\n\nContém logs de sinais de arbitragem gerados pelo sistema.",
            'system': "# Logs do Sistema\n\nContém logs gerais do sistema e mensagens de debug.",
            'trades': "# Logs de Trades\n\nContém histórico de trades executados.",
            'analysis': "# Logs de Análise\n\nContém análises e relatórios gerados."
        }
        
        for dir_name, content in readme_content.items():
            if dir_name in log_dirs:
                readme_path = log_dirs[dir_name] / "README.md"
                if not readme_path.exists():
                    readme_path.write_text(content)
                    
        return True, paths
        
    except Exception as e:
        logging.error(f"Erro ao criar estrutura de logs: {e}")
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
    paths = get_log_paths()
    removed = 0
    
    current_time = time.time()
    cutoff_time = current_time - (days * 24 * 60 * 60)
    
    for dir_path in paths.values():
        if not dir_path.exists():
            continue
            
        # Remove .log files
        for file_path in dir_path.glob("*.log"):
            if file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    removed += 1
                    logging.info(f"Removido log antigo: {file_path.name}")
                except Exception as e:
                    logging.error(f"Erro ao remover {file_path}: {e}")
                    
        # Remove .jsonl files
        for file_path in dir_path.glob("*.jsonl"):
            if file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    removed += 1
                    logging.info(f"Removido log antigo: {file_path.name}")
                except Exception as e:
                    logging.error(f"Erro ao remover {file_path}: {e}")
                    
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


# ======================== UTILITÁRIOS ========================

def rotate_logs(max_size_mb: int = 100):
    """
    Rotaciona logs quando excedem tamanho máximo
    
    Args:
        max_size_mb: Tamanho máximo em MB antes de rotacionar
    """
    paths = get_log_paths()
    
    for dir_path in paths.values():
        if not dir_path.exists():
            continue
            
        for log_file in dir_path.glob("*.log"):
            size_mb = log_file.stat().st_size / (1024 * 1024)
            
            if size_mb > max_size_mb:
                # Criar arquivo rotacionado
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                rotated_name = f"{log_file.stem}_{timestamp}{log_file.suffix}"
                rotated_path = log_file.parent / rotated_name
                
                try:
                    log_file.rename(rotated_path)
                    logging.info(f"Log rotacionado: {log_file.name} -> {rotated_name}")
                except Exception as e:
                    logging.error(f"Erro ao rotacionar {log_file}: {e}")


def get_log_summary(log_file: Path) -> Dict:
    """
    Retorna resumo de um arquivo de log
    
    Args:
        log_file: Caminho do arquivo
        
    Returns:
        Dict com resumo do log
    """
    if not log_file.exists():
        return {'error': 'Arquivo não encontrado'}
        
    summary = {
        'file': log_file.name,
        'size_mb': log_file.stat().st_size / (1024 * 1024),
        'lines': 0,
        'errors': 0,
        'warnings': 0,
        'first_entry': None,
        'last_entry': None
    }
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            summary['lines'] = len(lines)
            
            if lines:
                summary['first_entry'] = lines[0][:100]
                summary['last_entry'] = lines[-1][:100]
                
            for line in lines:
                if 'ERROR' in line:
                    summary['errors'] += 1
                elif 'WARNING' in line:
                    summary['warnings'] += 1
                    
    except Exception as e:
        summary['error'] = str(e)
        
    return summary


# ======================== EXPORTS ========================

__all__ = [
    'get_logger',
    'ensure_log_structure',
    'get_log_paths',
    'cleanup_old_logs',
    'get_log_statistics',
    'rotate_logs',
    'get_log_summary'
]