from ..inquilino.migracion import migrar_datos_heredados
from .fabrica import DIRECTORIO_DATOS, capacidades_del_perfil, construir_femix, inquilino_desde_entorno, inquilino_explicito

def main():
    migrar_datos_heredados(DIRECTORIO_DATOS, inquilino_explicito())
    inquilino_id = inquilino_desde_entorno()
    femix = construir_femix(inquilino_id=inquilino_id, capacidades=capacidades_del_perfil(DIRECTORIO_DATOS, inquilino_id))
    print("FEMIX (femix) — Ctrl+C para salir")
    while True:
        try:
            texto = input("> ")
        except (KeyboardInterrupt, EOFError):
            break
        print(femix.procesar("cli", texto))

if __name__ == "__main__":
    main()
