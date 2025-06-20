# Importações existentes (com proteção)
try:
    from .analyzers import (
        VolumeAnalyzer,
        PriceActionAnalyzer,
        OrderFlowAnalyzer,
        ImbalanceAnalyzer
    )
except ImportError:
    # Se não existir, define como None
    VolumeAnalyzer = None
    PriceActionAnalyzer = None
    OrderFlowAnalyzer = None
    ImbalanceAnalyzer = None

# NOVAS importações (também com proteção)
try:
    from .flow_analyzer import FlowAnalyzer
except ImportError:
    FlowAnalyzer = None

try:
    from .liquidity_analyzer import LiquidityAnalyzer
except ImportError:
    LiquidityAnalyzer = None

# Exporta tudo que existe
__all__ = []
if VolumeAnalyzer: __all__.append('VolumeAnalyzer')
if PriceActionAnalyzer: __all__.append('PriceActionAnalyzer')
if OrderFlowAnalyzer: __all__.append('OrderFlowAnalyzer')
if ImbalanceAnalyzer: __all__.append('ImbalanceAnalyzer')
if FlowAnalyzer: __all__.append('FlowAnalyzer')
if LiquidityAnalyzer: __all__.append('LiquidityAnalyzer')