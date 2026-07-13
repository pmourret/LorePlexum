from src.LorePlexum import TNFCDataInjector

if __name__ == "__main__":
    while True:
        # Point d'entrée de l'application
        injector = TNFCDataInjector()
        injector.run_injection()