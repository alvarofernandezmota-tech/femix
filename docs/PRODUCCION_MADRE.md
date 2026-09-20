# Femix en Producción (madre)

## Estado

- ✅ Bot corriendo en `madre`
- ✅ RAG por inquilino (186 tests)
- ✅ Multi-usuario + Multi-inquilino

## Configuración

### Variables de entorno

```bash
export FEMIX_INQUILINO_ID="tu_inquilino"
export FEMIX_USUARIO_ID="tu_usuario"
export FEMIX_MODELO_BASE="mistral"
export FEMIX_MODELO_RAPIDO="llama3.2"
export FEMIX_MODELO_PENSAMIENTO="qwen3.5"
export OPENAI_API_KEY="tu_api_key"
export OPENAI_BASE_URL="http://localhost:11434/v1"
```

### Datos
datos/
├── {inquilino_id}/
│ ├── tareas/
│ ├── diario/
│ ├── recordatorios/
│ └── rag/
│ └── indice.json
└── memoria/
└── {usuario_id}.json

text

## Ejecución

```bash
cd ~/GitHub/personal/femix
source .venv/bin/activate
python src/femix/cli.py
```

## Tests

```bash
python -m pytest tests/ -v
# 186 passed
```

## Próximos pasos

- [ ] Panel web (FastAPI + Jinja2)
- [ ] Docker con panel web + bot
- [ ] Release v0.2.0
