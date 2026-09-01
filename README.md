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

Masukkan hasil perintah pertama sebagai `SECRET_KEY` dan `IDENTITY_HMAC_KEYS`, serta hasil kedua sebagai `RESOLVER_ENCRYPTION_KEYS`. Docker hanya membuka aplikasi di `127.0.0.1:5050`; akses publik dilakukan melalui Nginx di `https://getfetchly.online`. Dashboard staf berada di `/admin/`. Ubah `FETCHLY_PORT` bila port 5050 sudah dipakai dan samakan port pada `proxy_pass` di konfigurasi Nginx.

Pastikan DNS `A`/`AAAA` domain sudah mengarah ke server, lalu buat sertifikat sebelum mengaktifkan konfigurasi Nginx:

```bash
sudo certbot certonly --standalone -d getfetchly.online
sudo cp nginx/getfetchly.online.conf /etc/nginx/sites-available/getfetchly.online
sudo ln -s /etc/nginx/sites-available/getfetchly.online /etc/nginx/sites-enabled/getfetchly.online
sudo nginx -t
sudo systemctl reload nginx
```

Path sertifikat pada konfigurasi mengikuti lokasi standar Certbot. Jika Nginx sedang memakai port 80, hentikan sementara saat menjalankan Certbot `--standalone`.

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

Compose memakai bind mount ke folder project `data/`: `data/downloads`, `data/mongodb`, dan `data/redis`. Folder ini persisten di host, tanpa Docker named volume. Backup MongoDB dengan `mongodump`, dan file unduhan tetap diperlakukan sementara. Uji provider live setelah update dengan satu URL publik yang legal untuk tiap provider karena perubahan situs pihak ketiga tidak dapat dicakup fixture lokal.

## Pengembangan

```powershell
uv sync --dev
uv run pytest
uv run ruff check .
uv run python manage.py check
```

HTMX disimpan lokal di `static/vendor`; aplikasi tidak bergantung pada CDN. Jangan menambahkan kembali Flask, SQLite, WARP, atau proxy otomatis.
