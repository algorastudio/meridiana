#!/usr/bin/env python3
"""Runner semplificato per i test"""
import sys
import os
import pytest

# Aggiungi la directory principale al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Esegui i test"""
    print("🧪 Esecuzione test Catasto Storico...")
    print(f"📁 Directory corrente: {os.getcwd()}")
    
    # Determina cosa eseguire
    if len(sys.argv) > 1 and sys.argv[1] == 'basic':
        # Esegui solo test base
        exit_code = pytest.main(['tests/test_basic.py', '-v', '--cov=models', '--cov=db_modules', '--cov-report=term-missing'])
    else:
        # Esegui tutti i test
        exit_code = pytest.main(['tests/', '-v', '--cov=models', '--cov=db_modules', '--cov-report=term-missing'])
    
    return exit_code

if __name__ == '__main__':
    sys.exit(main())
