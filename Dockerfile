FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONPATH=/app/src

# Exponer puerto del panel web
EXPOSE 8000

# Comando por defecto: ejecutar el bot
CMD ["python", "-m", "femix.bot.main"]
