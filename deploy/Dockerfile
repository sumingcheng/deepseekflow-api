FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py main.py ./

EXPOSE ${PORT:-8080}

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
