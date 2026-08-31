# Fetchly

Fetchly adalah pengunduh media sementara yang ramah pengguna. Aplikasi memakai Django + HTMX, MongoDB sebagai satu-satunya database, Redis/RQ untuk antrean, dan Playwright/yt-dlp untuk resolusi media. Tidak ada WARP, proxy bawaan, atau jalur migrasi SQLite.

## Menjalankan dengan Docker

Prasyarat: Docker Compose.

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
docker compose up --build -d --wait
docker compose exec web python manage.py createsuperuser
```

Masukkan hasil perintah pertama sebagai `SECRET_KEY` dan `IDENTITY_HMAC_KEYS`, serta hasil kedua sebagai `RESOLVER_ENCRYPTION_KEYS`. Buka `http://localhost:5050`; dashboard staf berada di `/admin/`. Ubah `FETCHLY_PORT` bila port 5050 sudah dipakai.

Konfigurasi batas unduhan tersedia di `.env.example`. `TRUSTED_PROXY_NETWORKS` harus berisi CIDR reverse proxy yang memang dipercaya; identitas anonim dibentuk dari fingerprint browser dan alamat IP yang sudah di-HMAC.

## Operasional

```powershell
docker compose ps
docker compose logs -f web worker
docker compose exec web python manage.py check_capabilities
docker compose exec web python manage.py reconcile_downloads
docker compose pull
docker compose up --build -d --wait
```

File unduhan kedaluwarsa otomatis setelah satu jam (dapat diubah dengan `DOWNLOAD_TASK_TTL_SECONDS`). Worker membersihkan file dan merekonsiliasi job macet tiap lima menit. Log berbentuk JSON, menyamarkan token/rahasia, dan dirotasi oleh Docker.

MongoDB, Redis, dan file unduhan disimpan pada named volume. Backup data persisten dengan alat volume host dan `mongodump`; pulihkan MongoDB dengan `mongorestore`, lalu jalankan `docker compose up -d --wait`. File unduhan bersifat sementara dan tidak perlu dipulihkan. Uji provider live setelah update dengan satu URL publik yang legal untuk tiap provider karena perubahan situs pihak ketiga tidak dapat dicakup fixture lokal.

## Pengembangan

```powershell
uv sync --dev
uv run pytest
uv run ruff check .
uv run python manage.py check
```

HTMX disimpan lokal di `static/vendor`; aplikasi tidak bergantung pada CDN. Jangan menambahkan kembali Flask, SQLite, WARP, atau proxy otomatis.
