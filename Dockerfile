FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg chromium chromium-driver && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p downloads

EXPOSE 5050

CMD ["gunicorn", "--workers", "3", "--timeout", "120", "--bind", "0.0.0.0:5050", "app:app"]