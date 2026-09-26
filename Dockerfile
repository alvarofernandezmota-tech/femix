FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
COPY conectores/ ./conectores/

# Usuario sin privilegios. /app/datos (RAG, tareas, diario, sesiones del panel) y la caché del
# modelo de Whisper se montan como volúmenes en docker-compose.yml; se crean aquí con el dueño
# correcto para que un volumen con nombre nuevo herede estos permisos.
RUN useradd --create-home --uid 1000 femix \
    && mkdir -p /app/datos /app/documentos /home/femix/.cache \
    && chown -R femix:femix /app/datos /app/documentos /home/femix/.cache
USER femix

EXPOSE 8000

# Un solo contenedor: bot de Telegram + panel web (FEMIX_PANEL=0 para solo el bot).
CMD ["python", "-m", "conectores.arranque"]
