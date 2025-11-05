FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for persistent storage
RUN mkdir -p /data

ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data

EXPOSE 5000

CMD ["python", "app.py"]
