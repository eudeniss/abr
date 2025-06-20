"""
Script para corrigir o problema de inicialização
"""
import fileinput
import sys

# Corrige a ordem de inicialização
filename = "arbitrage_dashboard.py"

print("Corrigindo ordem de inicialização...")

# Procura e corrige o método run
in_run_method = False
fixed = False

with fileinput.FileInput(filename, inplace=True, backup='.bak') as file:
    for line in file:
        if 'async def run(self):' in line:
            in_run_method = True
            
        if in_run_method and 'await self.initialize_components()' in line and not fixed:
            # Move esta linha para antes do get_all()
            print(line, end='')
            fixed = True
            continue
            
        if in_run_method and 'config = self.config_manager.get_all()' in line and not fixed:
            # Adiciona initialize antes
            print('        await self.initialize_components()')
            print('        print("✅ Sistema inicializado - v5.2")')
            print()
            
        print(line, end='')

print("Correção aplicada! Backup salvo como arbitrage_dashboard.py.bak")