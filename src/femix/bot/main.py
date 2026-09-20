from .fabrica import construir_femix

def main():
    femix = construir_femix()
    print("FEMIX (femix) — Ctrl+C para salir")
    while True:
        try:
            texto = input("> ")
        except (KeyboardInterrupt, EOFError):
            break
        print(femix.procesar("cli", texto))

if __name__ == "__main__":
    main()
