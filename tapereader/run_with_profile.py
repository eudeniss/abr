#!/usr/bin/env python
"""
Executa o sistema de arbitragem com um perfil específico
Uso: python run_with_profile.py [perfil]
Exemplo: python run_with_profile.py small_spreads
"""
import sys
import os
import asyncio
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from arbitrage_dashboard import ArbitrageApplication
from src.core.logger import ensure_log_structure


def set_active_profile(profile_name: str):
    """Atualiza o perfil ativo no arquivo de configuração"""
    config_path = os.path.join('config', 'arbitrage.yaml')
    
    # Lê configuração atual
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Verifica se o perfil existe
    profiles = config.get('arbitrage', {}).get('trading_profiles', {})
    if profile_name not in profiles:
        print(f"❌ Perfil '{profile_name}' não encontrado!")
        print(f"Perfis disponíveis: {', '.join(profiles.keys())}")
        return False
    
    # Atualiza perfil ativo
    config['arbitrage']['active_profile'] = profile_name
    
    # Salva configuração
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"✅ Perfil '{profile_name}' ativado com sucesso!")
    
    # Mostra detalhes do perfil
    profile_config = profiles[profile_name]
    print(f"\n📊 Configurações do perfil '{profile_name}':")
    print(f"   - Threshold: {profile_config.get('spread_std_devs')}σ")
    print(f"   - Amostras mínimas: {profile_config.get('min_samples_for_signal')}")
    print(f"   - Lucro mínimo: R$ {profile_config.get('min_profit_reais')}")
    
    return True


def show_current_profile():
    """Mostra o perfil atualmente ativo"""
    config_path = os.path.join('config', 'arbitrage.yaml')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    current_profile = config.get('arbitrage', {}).get('active_profile', 'default')
    profiles = config.get('arbitrage', {}).get('trading_profiles', {})
    
    print(f"\n📊 Perfil atual: {current_profile}")
    
    if current_profile in profiles:
        profile_config = profiles[current_profile]
        print(f"   - Threshold: {profile_config.get('spread_std_devs')}σ")
        print(f"   - Amostras mínimas: {profile_config.get('min_samples_for_signal')}")
        print(f"   - Lucro mínimo: R$ {profile_config.get('min_profit_reais')}")
    
    print(f"\n💡 Perfis disponíveis: {', '.join(profiles.keys())}")
    print("Para trocar: python run_with_profile.py [nome_perfil]")


async def main():
    # Verifica argumento de linha de comando
    if len(sys.argv) > 1:
        profile = sys.argv[1]
        
        # Comandos especiais
        if profile == "--show":
            show_current_profile()
            return
        elif profile == "--help":
            print("\nUso: python run_with_profile.py [perfil|comando]")
            print("\nPerfis disponíveis:")
            print("  - default: Configurações padrão de produção")
            print("  - small_spreads: Para spreads pequenos (teste)")
            print("  - conservative: Modo conservador")
            print("  - aggressive: Modo agressivo")
            print("\nComandos:")
            print("  --show: Mostra o perfil atual")
            print("  --help: Mostra esta ajuda")
            return
        
        if not set_active_profile(profile):
            return
    else:
        show_current_profile()
    
    print("\n🚀 Iniciando sistema de arbitragem...")
    print("=" * 50)
    
    # Executa aplicação
    ensure_log_structure()
    app = ArbitrageApplication()
    await app.run()


if __name__ == "__main__":
    if sys.platform == "win32":
        os.system("color")
    asyncio.run(main())