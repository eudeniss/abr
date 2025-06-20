# 🏦 Sistema de Arbitragem WDO/DOL v5.2

Sistema profissional de arbitragem entre contratos futuros de dólar (WDO e DOL) com análise em tempo real, gestão inteligente de risco e arquitetura otimizada.

## 🚀 Características

### Core Features
- **Arbitragem Automatizada**: Detecta divergências entre WDO/DOL com validação rigorosa
- **Tape Reading Direcional**: Análise de fluxo de agressões para sinais direcionais
- **Validação Rigorosa**: Mínimo de 5 pontos de lucro líquido
- **Gestão Inteligente**: 5 ou 10 contratos baseado em confiança (60%/70%/85%)
- **Monitor de Posição**: Controle em tempo real com alertas automáticos
- **Detectores Comportamentais**: Absorção, Exaustão, Defesa de Preço, Institucional
- **Sistema de Logging**: Registro completo estruturado para análise posterior

### Novidades v5.2
- **Arquitetura OOP**: Classe `ArbitrageApplication` para melhor organização
- **Performance Otimizada**: Loop principal em 0.1s (10x mais rápido)
- **Display Aprimorado**: Suporte para Rich library com layouts profissionais
- **Logging Eficiente**: IDs únicos sem leitura de arquivo
- **Dataclasses**: Estruturas de dados tipadas e validadas

## 📋 Requisitos

- Python 3.8+
- Excel com RTD configurado
- Windows (para alertas sonoros)
- ~100MB RAM
- Processador dual-core+

## 🔧 Instalação

```bash
# Clone o repositório
git clone [seu-repo]
cd tapereader

# Crie ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale as dependências
pip install -r requirements.txt
```

## ⚙️ Configuração

### 1. Configure o Excel RTD

Certifique-se que o arquivo `rtd_tapeReading.xlsx` está configurado com:
- Dados de WDO nas colunas B-E
- Dados de DOL nas colunas H-K  
- Book de WDO nas colunas N-Q
- Book de DOL nas colunas T-W

### 2. Ajuste as configurações

Edite os arquivos em `config/`:

```yaml
# config/arbitrage.yaml
arbitrage:
  detection:
    min_profit_reais: 20.0    # Lucro mínimo (R$ 20 = 2 pontos DOL)
  alerts:
    spread_std_devs: 1.5      # Threshold de desvio padrão
```

### 3. Estrutura de Logs

O sistema cria automaticamente a estrutura de logs:
```
logs/
├── arbitrage/    # Sinais de arbitragem
├── system/       # Logs do sistema
├── trades/       # Histórico de trades
└── analysis/     # Relatórios
```

## 🎮 Uso

### Executar o Sistema Principal

```bash
python arbitrage_dashboard.py
```

### Monitor de Trades (Visualização)

```bash
python monitor.py
```

O `monitor.py` é uma ferramenta de visualização em tempo real que mostra:
- Trades recentes de WDO e DOL lado a lado
- Books de ofertas com profundidade
- Estatísticas de volume e fluxo
- Detecção de desequilíbrios

É útil para:
- Verificar se o Excel está enviando dados corretamente
- Monitorar a atividade do mercado visualmente
- Debug de problemas de conectividade
- Análise manual complementar

## 📊 Módulos Principais

### Core
- `arbitrage_dashboard.py`: Aplicação principal com classe ArbitrageApplication
- `monitor.py`: Monitor visual de trades em tempo real
- `src/core/`: Configuração, cache e logging base

### Análise
- `src/analysis/arbitrage_validator.py`: Validação de oportunidades (5 pontos mínimos)
- `src/analysis/tape_reading_analyzer.py`: Análise de tape reading direcional
- `src/analysis/flow_analyzer.py`: Análise de fluxo de ordens
- `src/analysis/liquidity_analyzer.py`: Análise de liquidez

### Comportamentos
- `src/behaviors/behaviors_simplified.py`: Detectores de comportamentos
- `src/behaviors/price_defense_detector.py`: Detecção de defesa de preço

### Interface
- `src/ui/enhanced_display.py`: Display em terminal colorido
- `src/ui/rich_display.py`: Display profissional com Rich (opcional)

### Monitoramento
- `src/monitoring/position_monitor.py`: Monitor de posições ativas

### Estratégias
- `src/strategies/dynamic_parameters.py`: Ajuste dinâmico de parâmetros

## 🔍 Interpretação dos Sinais

### Níveis de Confiança
- **60-69%**: Meia mão (5 contratos) - Sinal válido mas conservador
- **70-84%**: Mão cheia (10 contratos) - Sinal forte
- **85%+**: Mão cheia premium - Sinal muito forte com múltiplas confirmações

### Gatilhos Comuns
- **Spread Estatístico**: Desvio significativo da média (>1.5σ)
- **Tape Reading**: Pressão direcional forte (>1.5x)
- **Absorção**: Grande player defendendo nível
- **Defesa de Preço**: Renovação agressiva de ordens
- **Institucional**: Trades grandes detectados

## 📈 Gestão de Risco

### Stop Loss
- Movimento adverso: 0.5 pontos (arbitragem) ou 3.0 pontos (tape)
- Tempo máximo: 5 minutos
- Invalidação por convergência de spread

### Alvos
- Alvo 1: 50% do movimento esperado
- Alvo 2: 100% do movimento esperado

## 🐛 Troubleshooting

### Sem dados do Excel
1. Verifique se o Excel está aberto
2. Confirme o caminho em `config/excel.yaml`
3. Use `monitor.py` para debug visual

### Sem sinais gerados
1. Aguarde 20+ amostras (spread_history)
2. Verifique threshold em configuração
3. Mercado pode estar sem oportunidades

### Erro de permissão em logs
1. Execute como administrador
2. Verifique permissões da pasta logs/
3. Mude log_dir na configuração

## 📝 Logs e Análise

### Arquivos Gerados
- `signals_YYYYMMDD.jsonl`: Log estruturado JSON
- `signals_YYYYMMDD.csv`: Planilha para análise
- `system_YYYYMMDD.log`: Log geral do sistema

### Análise Posterior
```python
from src.logging.signal_logger import analyze_signal_log

stats = analyze_signal_log("logs/arbitrage/signals_20250113.jsonl")
print(f"Total de sinais: {stats['total']}")
print(f"Win rate esperado: {stats['by_confidence']}")
```

## 🔄 Atualizações da v5.2

### Performance
- Loop principal 10x mais rápido (0.1s)
- Geração de IDs sem I/O
- Buffer assíncrono para logs
- Cache de estatísticas

### Arquitetura
- Separação clara de responsabilidades
- Uso de dataclasses
- Métodos privados bem definidos
- Inicialização estruturada

### Manutenibilidade
- Constantes externalizadas
- Menos "magic numbers"
- Código mais modular
- Melhor tratamento de erros

## 🤝 Contribuindo

1. Fork o projeto
2. Crie sua feature branch (`git checkout -b feature/NovaFuncionalidade`)
3. Commit suas mudanças (`git commit -m 'Add: Nova funcionalidade'`)
4. Push para a branch (`git push origin feature/NovaFuncionalidade`)
5. Abra um Pull Request

## 📄 Licença

Este projeto é proprietário e confidencial. Todos os direitos reservados.

## ⚠️ Aviso Legal

Este software é fornecido "como está" para fins educacionais e de pesquisa. 
Trading de futuros envolve risco substancial de perda e não é adequado para todos os investidores.
Desempenho passado não é garantia de resultados futuros.