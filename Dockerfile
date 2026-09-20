FROM python:3.14-slim

WORKDIR /app

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY src/ ./src/
COPY conectores/ ./conectores/

# Variables de entorno
ENV FEMIX_INQUILINO_ID=default
ENV FEMIX_USUARIO_ID=default
ENV OPENAI_API_KEY=tu_api_key
ENV OPENAI_BASE_URL=http://localhost:11434/v1

# Exponer puertos
EXPOSE 8000  # Panel web
EXPOSE 8080  # Telegram webhook (si es necesario)

# Comando: bot de Telegram + panel web
CMD ["sh", "-c", "python -m conectores.telegram.bot & python -m src.femix.web.app"]
