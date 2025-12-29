FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg chromium chromium-driver && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p downloads logs

EXPOSE 5050

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]