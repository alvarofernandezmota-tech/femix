from .hugin import Hugin

def main():
    hugin = Hugin()
    print("HUGIN (femix) — Ctrl+C para salir")
    while True:
        try:
            texto = input("> ")
        except (KeyboardInterrupt, EOFError):
            break
        print(hugin.procesar("cli", texto))

if __name__ == "__main__":
    main()
