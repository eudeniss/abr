@echo off
title Sistema de Arbitragem WDO/DOL - Menu Principal
color 0A
cd /d "%~dp0"

:MENU
cls
echo ================================================================================
echo                    SISTEMA DE ARBITRAGEM WDO/DOL v5.2
echo ================================================================================
echo.
echo    [1] MODO TESTE         (Spreads Pequenos - 0.8 sigma)
echo    [2] MODO PRODUCAO      (Spreads Normais - 1.5 sigma)
echo    [3] MODO CONSERVADOR   (Apenas Melhores - 2.0 sigma)
echo    [4] MODO AGRESSIVO     (Mais Sinais - 1.0 sigma)
echo.
echo    [5] Ver Configuracao Atual
echo    [6] Analisar Spreads
echo    [7] Analise Visual do Times/Book
echo.
echo    [0] Sair
echo.
echo ================================================================================
set /p opcao="Digite sua opcao: "

if "%opcao%"=="1" goto TESTE
if "%opcao%"=="2" goto PRODUCAO
if "%opcao%"=="3" goto CONSERVADOR
if "%opcao%"=="4" goto AGRESSIVO
if "%opcao%"=="5" goto CONFIG
if "%opcao%"=="6" goto ANALISE
if "%opcao%"=="7" goto MONITOR
if "%opcao%"=="0" goto SAIR
goto MENU

:TESTE
cls
color 0E
echo ================================================================================
echo                         MODO TESTE - SPREADS PEQUENOS
echo ================================================================================
echo.
echo    Configuracoes:
echo    - Threshold: 0.8 desvios padrao
echo    - Amostras minimas: 5
echo    - Lucro minimo: R$ 5.00
echo    - Ideal para: Spreads de 0.5 pontos
echo.
echo ================================================================================
echo Iniciando em 3 segundos...
timeout /t 3 >nul
set ARBITRAGE_PROFILE=small_spreads
python arbitrage_dashboard.py
pause
goto MENU

:PRODUCAO
cls
color 0B
echo ================================================================================
echo                         MODO PRODUCAO - PADRAO
echo ================================================================================
echo.
echo    Configuracoes:
echo    - Threshold: 1.5 desvios padrao
echo    - Amostras minimas: 20
echo    - Lucro minimo: R$ 20.00
echo    - Ideal para: Spreads maiores que 1.0 ponto
echo.
echo ================================================================================
echo Iniciando em 3 segundos...
timeout /t 3 >nul
set ARBITRAGE_PROFILE=default
python arbitrage_dashboard.py
pause
goto MENU

:CONSERVADOR
cls
color 09
echo ================================================================================
echo                      MODO CONSERVADOR - ALTA CONFIANCA
echo ================================================================================
echo.
echo    Configuracoes:
echo    - Threshold: 2.0 desvios padrao
echo    - Amostras minimas: 30
echo    - Lucro minimo: R$ 30.00
echo    - Ideal para: Apenas melhores oportunidades
echo.
echo ================================================================================
echo Iniciando em 3 segundos...
timeout /t 3 >nul
set ARBITRAGE_PROFILE=conservative
python arbitrage_dashboard.py
pause
goto MENU

:AGRESSIVO
cls
color 0C
echo ================================================================================
echo                        MODO AGRESSIVO - MAIS SINAIS
echo ================================================================================
echo.
echo    Configuracoes:
echo    - Threshold: 1.0 desvio padrao
echo    - Amostras minimas: 15
echo    - Lucro minimo: R$ 10.00
echo    - Ideal para: Mercados com boa liquidez
echo.
echo ================================================================================
echo Iniciando em 3 segundos...
timeout /t 3 >nul
set ARBITRAGE_PROFILE=aggressive
python arbitrage_dashboard.py
pause
goto MENU

:CONFIG
cls
echo ================================================================================
echo                         CONFIGURACAO ATUAL
echo ================================================================================
python run_with_profile.py --show
echo.
pause
goto MENU

:ANALISE
cls
echo ================================================================================
echo                      ANALISE DE SPREADS E PERFIS
echo ================================================================================
python test_spreads.py
echo.
pause
goto MENU

:MONITOR
cls
echo ================================================================================
echo                    MONITOR DE MERCADO - Analise Visual do Times/Book
echo ================================================================================
echo.
echo Finalizando Analise Visual do Times/Book...
echo.
python monitor.py
pause
goto MENU

:SAIR
cls
echo Saindo do sistema...
timeout /t 2 >nul
exit