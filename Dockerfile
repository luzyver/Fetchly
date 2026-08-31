FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project \
    && .venv/bin/playwright install --with-deps chromium

COPY . .

RUN mkdir -p downloads staticfiles

EXPOSE 5050

CMD ["gunicorn", "--bind", "0.0.0.0:5050", "fetchly.wsgi:application"]
