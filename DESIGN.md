---
version: alpha
name: "Fetchly"
description: "A friendly Indonesian media tool built around a crisp, take-away media ticket."
colors:
  background: "#F7F9FD"
  surface: "#FFFFFF"
  ink: "#07142D"
  muted: "#475C7A"
  faint: "#687B96"
  primary: "#0A55E8"
  primary-hover: "#0846C2"
  accent: "#FF7A00"
  border: "#C8D4E8"
  success: "#16825D"
  warning: "#B95B00"
  danger: "#C63C4A"
  focus: "#FF7A00"
  dark-background: "#081224"
  dark-surface: "#101D33"
  dark-ink: "#F6F8FC"
  dark-muted: "#B7C5D9"
typography:
  sans:
    fontFamily: "Aptos, Segoe UI Variable, Inter, system-ui, sans-serif"
    fontSize: "1rem"
    lineHeight: "1.5"
  display:
    fontFamily: "Aptos Display, Segoe UI Variable Display, Aptos, system-ui, sans-serif"
    fontSize: "3.5rem"
    lineHeight: "1.04"
rounded:
  DEFAULT: "0.75rem"
  sm: "0.625rem"
  md: "0.75rem"
  lg: "0.875rem"
spacing:
  control: "0.75rem"
  content: "1.5rem"
  section: "3rem"
  page-max: "90rem"
components:
  button:
    minHeight: "2.75rem"
  input:
    minHeight: "3.75rem"
  media-ticket:
    radius: "0.875rem"
  focus-ring:
    width: "0.1875rem"
---

# Fetchly Design System

## Overview

### Creative North Star

Sebuah loket pengambilan digital di siang hari: pengguna menyerahkan sebuah tautan dan
menerima “tiket media” yang bersih, jelas, dan siap dibawa. Referensi visual normatif ada di
`docs/design/concepts/fetchly-desktop.png` dan `docs/design/concepts/fetchly-mobile.png`.

### Product context and register

- **Audience and primary job:** pengguna umum menempel tautan, memilih format, lalu mengunduh.
- **Target market and evidence:** Indonesia; bahasa dan keputusan produk dikonfirmasi pengguna.
- **Locale and language policy:** `id-ID`; istilah teknis hanya muncul jika membantu keputusan.
- **Usage scene:** ponsel atau laptop, sering dalam cahaya terang, sesi singkat dan terarah.
- **Register:** product; halaman publik lebih ekspresif, dashboard staf tetap memakai token sama.
- **Memorable signature:** hasil inspeksi berbentuk media ticket dengan pemisah perforasi rapi.
- **Restraint:** form, status, pilihan format, dan riwayat memakai affordance produk yang familier.
- **Anti-references:** downloader gelap penuh iklan, cyberpunk neon, bento SaaS, cream editorial.
- **Token ownership/runtime mapping:** DESIGN.md adalah sumber nilai; `static/css/app.css`
  mengimplementasikan setiap token sebagai custom property dengan nama semantik yang sama.

## Colors

Latar utama adalah near-white dingin, bukan cream. Ultramarine hanya untuk aksi utama,
selection, link, dan identitas. Tangerine adalah aksen ekspresif sekaligus focus ring; jangan
menjadikannya dekorasi berulang. State success, warning, dan danger selalu disertai teks atau
ikon. Dark theme memetakan ulang role semantik tanpa mengubah hierarki.

## Typography

Gunakan stack sans lokal agar tidak ada font swap atau ketergantungan CDN. Display memakai
varian display sistem dengan weight 700–800, tracking minimal `-0.035em`, dan hanya pada
headline. Semua label, tombol, format, riwayat, serta dashboard memakai sans yang sama dengan
ukuran eksplisit. Body dibatasi sekitar 68ch dan memakai sentence case bahasa Indonesia.

## Layout

Desktop memakai area kerja fleksibel dan rail riwayat sekitar 23rem; mobile menjadi satu
kolom dengan riwayat sesudah tugas utama. Jarak mengikuti token control/content/section,
tanpa nested card. Area async mencadangkan ruang secukupnya agar form tidak meloncat.
Breakpoint utama 56rem; seluruh layar harus bertahan pada 320px dan zoom 200%.

## Elevation & Depth

Hierarki berasal dari surface putih, outline biru-abu, dan satu shadow pendek maksimal 8px
pada media ticket. Jangan memasangkan outline dekoratif dengan shadow lebar. Overlay gelap
hanya untuk dialog modal dashboard; halaman publik tidak memakai glass atau blur dekoratif.

## Shapes

Kontrol dan container memakai radius 10–14px. Tombol boleh full-pill hanya jika berupa tag,
bukan aksi utama. Perforasi ticket memakai bentuk CSS yang presisi dan tidak menyerupai
doodle. Ikon memakai stroke 1.75–2px, ujung bulat, serta optical size konsisten.

## Components

### Foundational visual states

Semua kontrol memiliki default, hover, focus-visible tangerine 3px, active, disabled, dan busy.
Selection memakai outline ultramarine plus radio native. Error memakai copy korektif dan
`aria-invalid`; loading memakai indikator kecil di ruang yang sudah dipesan, bukan skeleton.

### Buttons and actions

Satu aksi solid ultramarine per area keputusan. Aksi sekunder berupa outline; utility kecil
berupa ghost. Tinggi minimum 44px, label tidak berubah lebar saat busy, ikon selalu disertai
label kecuali kontrol tema yang memiliki accessible name.

### Navigation and data display

Header tenang: brand dan kontrol tema. Riwayat adalah rail/list terbuka, bukan grid kartu.
Baris menjaga tinggi stabil, memotong judul secara visual namun menyediakan nama penuh.

### Forms and overlays

Input URL mempunyai label nyata, help/error region tetap, dan form `novalidate`. Format adalah
radio native di dalam label klik penuh. Dialog staf memakai native `<dialog>` yang ditata dan
mengembalikan fokus; tidak ada `alert`, `confirm`, atau `prompt` browser.

### Iconography

SVG code-native bergaya outline 2px dengan `currentColor`; simbol download dalam kotak biru
adalah mark produk. Jangan memakai emoji atau glyph teks untuk ikon navigasi.

### Motion

Transisi state 180–220ms dengan ease-out; gerak hanya menjelaskan swap HTMX, progress, dan
selection. Reduced motion menghapus transform, scroll behavior, dan animasi non-esensial.

### Content and data visualization

Nada ramah dan langsung: “Cari format”, “Siapkan unduhan”, “Coba lagi”. Jangan tampilkan
stderr, internal ID, fingerprint, IP, cookie, resolver context, atau path. Ukuran file memakai
unit lokal yang ringkas dan tanggal/waktu memakai `id-ID` / `Asia/Jakarta`.

## Do's and Don'ts

- **Do:** jadikan media ticket satu-satunya gestur visual yang ekspresif.
- **Do:** gunakan token semantik yang sama di public flow dan dashboard.
- **Don't:** tambah card grid, metrik palsu, badge dekoratif, gradient text, atau glassmorphism.
- **Don't:** sembunyikan focus ring, scrollbar, error korektif, atau status async.
