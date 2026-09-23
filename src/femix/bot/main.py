from ..inquilino.migracion import migrar_datos_heredados
from .fabrica import DIRECTORIO_DATOS, construir_femix, inquilino_desde_entorno

def main():
    migrar_datos_heredados(DIRECTORIO_DATOS, inquilino_desde_entorno())
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
