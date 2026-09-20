from .femix import Femix

def main():
    femix = Femix()
    print("FEMIX (femix) — Ctrl+C para salir")
    while True:
        try:
            texto = input("> ")
        except (KeyboardInterrupt, EOFError):
            break
        print(femix.procesar("cli", texto))

if __name__ == "__main__":
    main()
