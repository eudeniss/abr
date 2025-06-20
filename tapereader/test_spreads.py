"""
Script para testar diferentes configurações de spread
Mostra qual perfil usar baseado nos spreads observados
"""
import yaml
import os
from pathlib import Path
import statistics


def analyze_spreads_from_history(spread_values):
    """Analisa uma lista de spreads históricos"""
    if not spread_values:
        return None
    
    return {
        'mean': statistics.mean(spread_values),
        'std': statistics.stdev(spread_values) if len(spread_values) > 1 else 0,
        'min': min(spread_values),
        'max': max(spread_values),
        'range': max(spread_values) - min(spread_values)
    }


def show_spread_analysis():
    """Mostra análise dos thresholds para diferentes spreads"""
    config_path = Path('config/arbitrage.yaml')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    profiles = config.get('arbitrage', {}).get('trading_profiles', {})
    active_profile = config.get('arbitrage', {}).get('active_profile', 'default')
    
    print("📊 ANÁLISE DE THRESHOLDS POR PERFIL")
    print("=" * 70)
    
    # Spreads típicos observados (baseado nos dados do usuário)
    typical_spreads = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    observed_spreads = [-0.5, -0.5, 0.0, 0.0, 0.5, 0.5]  # Dados reais observados
    
    # Analisa spreads observados
    analysis = analyze_spreads_from_history(observed_spreads)
    if analysis:
        print("\n📈 ANÁLISE DOS SEUS SPREADS:")
        print(f"   Média: {analysis['mean']:.2f}")
        print(f"   Desvio padrão: {analysis['std']:.2f}")
        print(f"   Mínimo: {analysis['min']:.2f}")
        print(f"   Máximo: {analysis['max']:.2f}")
        print(f"   Amplitude: {analysis['range']:.2f}")
        
        std_dev = analysis['std'] if analysis['std'] > 0 else 0.48
    else:
        std_dev = 0.48  # Valor padrão baseado nos dados
    
    print(f"\n💡 Usando desvio padrão de {std_dev:.2f} para os cálculos")
    
    # Analisa cada perfil
    recommended_profile = None
    min_spread_needed_for_current = float('inf')
    
    for profile_name, profile_config in profiles.items():
        threshold = profile_config.get('spread_std_devs', 1.5)
        min_spread_needed = threshold * std_dev
        
        is_active = " (ATIVO)" if profile_name == active_profile else ""
        print(f"\n🎯 Perfil: {profile_name}{is_active}")
        print(f"   Threshold: {threshold}σ")
        print(f"   Spread mínimo necessário: {min_spread_needed:.2f} pontos")
        print(f"   Lucro mínimo: R$ {profile_config.get('min_profit_reais', 20)}")
        print(f"   Amostras necessárias: {profile_config.get('min_samples_for_signal', 20)}")
        
        # Verifica se este perfil funcionaria com os spreads observados
        if analysis and min_spread_needed <= analysis['max']:
            if min_spread_needed < min_spread_needed_for_current:
                recommended_profile = profile_name
                min_spread_needed_for_current = min_spread_needed
        
        print("\n   Sinais gerados com spreads típicos:")
        for spread in typical_spreads:
            z_score = spread / std_dev
            generates_signal = z_score >= threshold
            signal = "✅ GERA SINAL" if generates_signal else "❌ Não gera"
            print(f"   Spread {spread:>4.1f} pts → Z-Score {z_score:>4.1f} → {signal}")
    
    # Recomendação
    print("\n" + "=" * 70)
    print("🎯 RECOMENDAÇÃO:")
    
    if recommended_profile and recommended_profile != active_profile:
        print(f"\n⚠️  Com spreads de apenas {analysis['max']:.1f} pontos, recomenda-se usar o perfil '{recommended_profile}'")
        print(f"   Execute: python run_with_profile.py {recommended_profile}")
    elif recommended_profile:
        print(f"\n✅ O perfil atual '{active_profile}' já é adequado para seus spreads")
    else:
        print(f"\n⚠️  Nenhum perfil é adequado para spreads tão pequenos.")
        print("   Considere criar um perfil customizado com threshold ainda menor")
    
    # Simulação com spreads observados
    if analysis and active_profile in profiles:
        print(f"\n📊 SIMULAÇÃO COM PERFIL ATIVO '{active_profile}':")
        active_threshold = profiles[active_profile].get('spread_std_devs', 1.5)
        
        for spread in [-0.5, 0.5, 1.0, 1.5]:
            z_score = spread / std_dev
            generates = abs(z_score) >= active_threshold
            signal_type = "COMPRA" if spread < 0 else "VENDA"
            result = f"✅ Sinal de {signal_type}" if generates else "❌ Sem sinal"
            print(f"   Spread {spread:>5.1f} → Z-Score {z_score:>+5.2f} → {result}")


def create_custom_profile():
    """Ajuda a criar um perfil customizado"""
    print("\n🛠️  CRIADOR DE PERFIL CUSTOMIZADO")
    print("=" * 50)
    
    name = input("Nome do perfil: ").strip()
    threshold = float(input("Threshold (desvios padrão, ex: 0.5): "))
    min_samples = int(input("Amostras mínimas (ex: 5): "))
    min_profit = float(input("Lucro mínimo em R$ (ex: 5.0): "))
    
    print(f"\n📝 Adicione isto ao seu arbitrage.yaml na seção trading_profiles:")
    print(f"""
    {name}:
      spread_std_devs: {threshold}
      min_samples_for_signal: {min_samples}
      min_profit_reais: {min_profit}
    """)
    
    print(f"\n💡 Depois mude active_profile para '{name}' ou execute:")
    print(f"   python run_with_profile.py {name}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--create":
        create_custom_profile()
    else:
        show_spread_analysis()
        print("\n💡 Para criar um perfil customizado: python test_spreads.py --create")