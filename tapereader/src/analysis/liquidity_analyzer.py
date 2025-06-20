"""
Analisador de liquidez e profundidade do book
"""
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class LiquidityAnalyzer:
    """Analisa profundidade e qualidade do book de ofertas"""
    
    def __init__(self, config: Dict):
        self.config = config
        
        # Parâmetros de análise
        self.min_liquidity_score = config.get('min_liquidity_score', 0.6)
        self.iceberg_ratio = config.get('iceberg_ratio', 3.0)
        self.max_levels = config.get('max_levels_analysis', 5)
        
        # Histórico para detecção de padrões
        self.book_history = []
        self.iceberg_detections = {'WDOFUT': 0, 'DOLFUT': 0}
        
    def analyze_book_depth(self, book: Dict, symbol: str, volume_needed: int) -> Dict:
        """Analisa profundidade do book para um volume específico"""
        analysis = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'has_liquidity': False,
            'liquidity_score': 0.0,
            'bid_depth': 0,
            'ask_depth': 0,
            'spread': 0.0,
            'avg_fill_price_buy': 0.0,
            'avg_fill_price_sell': 0.0,
            'slippage_buy': 0.0,
            'slippage_sell': 0.0,
            'levels_needed_buy': 0,
            'levels_needed_sell': 0,
            'iceberg_detected': False,
            'book_imbalance': 0.0,
            'quality_rating': 'POOR'
        }
        
        if not book or not book.get('bids') or not book.get('asks'):
            return analysis
            
        # Calcula métricas básicas
        analysis['spread'] = book['asks'][0]['price'] - book['bids'][0]['price']
        analysis['bid_depth'] = sum(bid['volume'] for bid in book['bids'][:self.max_levels])
        analysis['ask_depth'] = sum(ask['volume'] for ask in book['asks'][:self.max_levels])
        
        # Simula execução para compra e venda
        buy_sim = self._simulate_market_order(book['asks'], volume_needed, 'BUY')
        sell_sim = self._simulate_market_order(book['bids'], volume_needed, 'SELL')
        
        # Atualiza análise com resultados da simulação
        if buy_sim['filled']:
            analysis['avg_fill_price_buy'] = buy_sim['avg_price']
            analysis['slippage_buy'] = buy_sim['slippage']
            analysis['levels_needed_buy'] = buy_sim['levels_used']
            
        if sell_sim['filled']:
            analysis['avg_fill_price_sell'] = sell_sim['avg_price']
            analysis['slippage_sell'] = sell_sim['slippage'] 
            analysis['levels_needed_sell'] = sell_sim['levels_used']
            
        # Verifica se tem liquidez suficiente
        analysis['has_liquidity'] = buy_sim['filled'] and sell_sim['filled']
        
        # Calcula score de liquidez
        analysis['liquidity_score'] = self._calculate_liquidity_score(
            analysis, book, volume_needed
        )
        
        # Detecta possíveis icebergs
        analysis['iceberg_detected'] = self._detect_iceberg(book, symbol)
        
        # Calcula desequilíbrio do book
        total_depth = analysis['bid_depth'] + analysis['ask_depth']
        if total_depth > 0:
            analysis['book_imbalance'] = (analysis['bid_depth'] - analysis['ask_depth']) / total_depth
            
        # Determina qualidade geral
        analysis['quality_rating'] = self._rate_book_quality(analysis)
        
        return analysis
        
    def _simulate_market_order(self, levels: List[Dict], volume: int, side: str) -> Dict:
        """Simula execução de ordem de mercado"""
        result = {
            'filled': False,
            'avg_price': 0.0,
            'total_cost': 0.0,
            'volume_filled': 0,
            'levels_used': 0,
            'slippage': 0.0
        }
        
        if not levels:
            return result
            
        remaining = volume
        total_value = 0.0
        levels_used = 0
        
        best_price = levels[0]['price']
        
        for level in levels[:self.max_levels]:
            if remaining <= 0:
                break
                
            fill_qty = min(remaining, level['volume'])
            total_value += fill_qty * level['price']
            remaining -= fill_qty
            levels_used += 1
            result['volume_filled'] += fill_qty
            
        if remaining == 0:
            result['filled'] = True
            result['avg_price'] = total_value / volume
            result['total_cost'] = total_value
            result['levels_used'] = levels_used
            
            # Calcula slippage
            if side == 'BUY':
                result['slippage'] = result['avg_price'] - best_price
            else:
                result['slippage'] = best_price - result['avg_price']
                
        return result
        
    def _calculate_liquidity_score(self, analysis: Dict, book: Dict, volume: int) -> float:
        """Calcula score de liquidez de 0 a 1"""
        score = 1.0
        
        # Penaliza por usar muitos níveis
        max_acceptable_levels = 3
        if analysis['levels_needed_buy'] > max_acceptable_levels:
            score *= (max_acceptable_levels / analysis['levels_needed_buy'])
        if analysis['levels_needed_sell'] > max_acceptable_levels:
            score *= (max_acceptable_levels / analysis['levels_needed_sell'])
            
        # Penaliza por slippage alto
        if analysis['avg_fill_price_buy'] > 0:
            max_acceptable_slippage = 0.002  # 0.2%
            slippage_ratio = analysis['slippage_buy'] / analysis['avg_fill_price_buy']
            if slippage_ratio > max_acceptable_slippage:
                score *= (max_acceptable_slippage / slippage_ratio)
                
        # Penaliza por spread largo
        if book['bids'] and book['asks']:
            mid_price = (book['bids'][0]['price'] + book['asks'][0]['price']) / 2
            spread_ratio = analysis['spread'] / mid_price
            max_acceptable_spread = 0.001  # 0.1%
            if spread_ratio > max_acceptable_spread:
                score *= (max_acceptable_spread / spread_ratio)
                
        # Penaliza por desequilíbrio no book
        if abs(analysis['book_imbalance']) > 0.5:
            score *= (1 - abs(analysis['book_imbalance']) / 2)
            
        # Bonus se detectou iceberg (indica liquidez oculta)
        if analysis['iceberg_detected']:
            score *= 1.1
            
        return max(0.0, min(1.0, score))
        
    def _detect_iceberg(self, book: Dict, symbol: str) -> bool:
        """Detecta possíveis ordens iceberg"""
        # Iceberg: volume consistente em múltiplos níveis (ordem grande fatiada)
        
        for side in ['bids', 'asks']:
            if len(book[side]) < 3:
                continue
                
            volumes = [level['volume'] for level in book[side][:5]]
            
            # Verifica se volumes são suspeitosamente similares
            if len(set(volumes)) == 1 and volumes[0] > 0:
                # Todos os níveis têm exatamente o mesmo volume
                self.iceberg_detections[symbol] += 1
                return True
                
            # Verifica se há um padrão de volume decrescente uniforme
            if len(volumes) >= 3:
                avg_volume = sum(volumes) / len(volumes)
                min_volume = min(volumes)
                max_volume = max(volumes)
                
                # Se a variação é muito pequena comparada à média
                if max_volume > 0 and (max_volume - min_volume) / avg_volume < 0.2:
                    return True
                    
        return False
        
    def _rate_book_quality(self, analysis: Dict) -> str:
        """Classifica a qualidade do book"""
        score = analysis['liquidity_score']
        
        if not analysis['has_liquidity']:
            return 'INSUFFICIENT'
        elif score >= 0.8:
            return 'EXCELLENT'
        elif score >= 0.6:
            return 'GOOD'
        elif score >= 0.4:
            return 'FAIR'
        else:
            return 'POOR'
            
    def analyze_dual_books(self, wdo_book: Dict, dol_book: Dict, 
                          wdo_volume: int, dol_volume: int) -> Dict:
        """Analisa liquidez para operação de arbitragem com ambos os books"""
        wdo_analysis = self.analyze_book_depth(wdo_book, 'WDOFUT', wdo_volume)
        dol_analysis = self.analyze_book_depth(dol_book, 'DOLFUT', dol_volume)
        
        # Análise combinada
        combined = {
            'timestamp': datetime.now(),
            'wdo_liquidity': wdo_analysis,
            'dol_liquidity': dol_analysis,
            'both_liquid': wdo_analysis['has_liquidity'] and dol_analysis['has_liquidity'],
            'combined_score': (wdo_analysis['liquidity_score'] + dol_analysis['liquidity_score']) / 2,
            'execution_risk': 'LOW',
            'recommended_action': 'PROCEED'
        }
        
        # Avalia risco de execução
        if not combined['both_liquid']:
            combined['execution_risk'] = 'HIGH'
            combined['recommended_action'] = 'ABORT'
        elif combined['combined_score'] < 0.5:
            combined['execution_risk'] = 'MEDIUM'
            combined['recommended_action'] = 'CAUTION'
        elif wdo_analysis['iceberg_detected'] or dol_analysis['iceberg_detected']:
            combined['execution_risk'] = 'MEDIUM'
            combined['recommended_action'] = 'MONITOR'
            
        return combined