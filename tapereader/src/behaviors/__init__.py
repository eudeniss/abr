"""
Módulo de detecção de comportamentos de mercado
"""
from .behaviors_simplified import SimplifiedBehaviorManager
from .price_defense_detector import PriceDefenseDetector

__all__ = [
    'SimplifiedBehaviorManager',
    'PriceDefenseDetector'
]