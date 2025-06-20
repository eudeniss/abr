#!/usr/bin/env python
"""
Script de teste para diagnóstico do Tape Reading
Executa isoladamente para verificar o processamento de trades
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.config import ConfigManager
from src.data.excel_provider import ExcelDataProvider
from src.analysis.tape_reading_analyzer import TapeReadingAnalyzer
from datetime import datetime


async def test_tape_reading():
    """Testa o módulo de tape reading isoladamente"""
    print("=== TESTE DE TAPE READING ===\n")
    
    # 1. Inicializar configuração
    config_manager = ConfigManager(config_dir='config', env='production')
    excel_config = config_manager.get('excel', {})
    tape_config = config_manager.get('tape_reading', {})
    
    print(f"✅ Configuração carregada")
    print(f"   - Min trades para sinal: {tape_config.get('min_trades_for_signal', 20)}")
    print(f"   - Janela de análise: {tape_config.get('trade_window', 50)}")
    print(f"   - Ratio mínimo: {tape_config.get('min_pressure_ratio', 1.5)}\n")
    
    # 2. Inicializar data provider
    data_provider = ExcelDataProvider(excel_config, None)
    await data_provider.initialize()
    print("✅ Excel provider inicializado\n")
    
    # 3. Inicializar tape analyzer
    tape_analyzer = TapeReadingAnalyzer(tape_config)
    print("✅ Tape analyzer inicializado\n")
    
    # 4. Loop de teste
    print("Iniciando coleta de dados...\n")
    
    for i in range(10):  # 10 iterações de teste
        try:
            # Obter dados
            snapshot = await data_provider.get_market_snapshot()
            
            if not snapshot:
                print(f"Iteração {i+1}: Sem dados")
                await asyncio.sleep(1)
                continue
            
            # Combinar trades
            wdo_trades = snapshot['wdofut']['trades']
            dol_trades = snapshot['dolfut']['trades']
            all_trades = wdo_trades + dol_trades
            
            print(f"\nIteração {i+1}:")
            print(f"  - WDO trades: {len(wdo_trades)}")
            print(f"  - DOL trades: {len(dol_trades)}")
            print(f"  - Total: {len(all_trades)}")
            
            # Mostrar amostra de trade
            if all_trades:
                sample = all_trades[0]
                print(f"  - Amostra de trade: Symbol={sample.get('symbol')}, "
                      f"Side='{sample.get('side')}', Price={sample.get('price')}")
                
                # Verificar se está no formato esperado
                if sample.get('side') not in ['Comprador', 'Vendedor']:
                    print(f"  ⚠️  ATENÇÃO: Side '{sample.get('side')}' não é 'Comprador' ou 'Vendedor'!")
            
            # Analisar com tape reading
            dol_book = snapshot['dolfut']['book']
            if dol_book.get('bids') and dol_book.get('asks'):
                dol_mid = (dol_book['bids'][0]['price'] + dol_book['asks'][0]['price']) / 2
                
                # Passar trades para o analyzer
                tape_signal, tape_reason = tape_analyzer.analyze_trades(all_trades, dol_mid)
                
                # Obter estatísticas
                stats = tape_analyzer.get_statistics()
                
                print(f"\n  📊 Estatísticas do Tape Reading:")
                print(f"     - Total acumulado: {stats.get('total_trades_session', 0)}")
                print(f"     - DOL: {stats.get('dol_trades', 0)}")
                print(f"     - WDO: {stats.get('wdo_trades', 0)}")
                print(f"     - Buy %: {stats.get('buy_percentage', 0):.1f}%")
                print(f"     - Sell %: {stats.get('sell_percentage', 0):.1f}%")
                print(f"     - Razão: {tape_reason}")
                
                # Diagnóstico de formato
                if i == 5:  # Na 5ª iteração, faz diagnóstico completo
                    print(f"\n  🔍 Diagnóstico de formato:")
                    diag = tape_analyzer.diagnose_trades_format()
                    print(f"     - Sides encontrados: {diag.get('sides_found', {})}")
                    print(f"     - Valores esperados: {diag.get('expected_values', [])}")
                    print(f"     - Classificação: {diag.get('classification', {})}")
                    print(f"     - Campos no trade: {diag.get('fields_in_trade', [])}")
                    print(f"     - Trade exemplo: {diag.get('sample_trade', {})}")
            
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"\n❌ Erro na iteração {i+1}: {e}")
            import traceback
            traceback.print_exc()
    
    # 5. Cleanup
    await data_provider.close()
    print("\n\n✅ Teste concluído!")
    
    # Resumo final
    final_stats = tape_analyzer.get_statistics()
    print(f"\nRESUMO FINAL:")
    print(f"- Total de trades processados: {final_stats.get('total_trades_session', 0)}")
    print(f"- Trades DOL: {final_stats.get('dol_trades', 0)}")
    print(f"- Trades WDO: {final_stats.get('wdo_trades', 0)}")
    print(f"- Buy total: {final_stats.get('total_buy_count', 0)}")
    print(f"- Sell total: {final_stats.get('total_sell_count', 0)}")


if __name__ == "__main__":
    print("Iniciando teste de Tape Reading...")
    print("Certifique-se de que o Excel está aberto com dados de mercado.\n")
    
    try:
        asyncio.run(test_tape_reading())
    except KeyboardInterrupt:
        print("\n\nTeste interrompido pelo usuário.")
    except Exception as e:
        print(f"\n\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()