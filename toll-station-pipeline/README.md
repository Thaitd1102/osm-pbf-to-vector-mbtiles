# Toll Station Pipeline

Pipeline này dùng để thu thập, làm sạch, chuẩn hóa, lưu DB và tích hợp dữ liệu trạm thu phí không dừng vào bản đồ nội bộ `maps-vietnam`.

Kết quả hiện tại:

- Clean dataset: `data/clean/toll_stations_clean.csv`
- Số trạm hợp lệ: `261`
- PostgreSQL table: `public.toll_stations`
- OSM output: `data/clean/toll_stations_clean.osm` và `../data/toll/toll_stations_clean.osm`
- MBTiles nội bộ đã render: `../data/base/vietnam-260101-with-tolls-navigation.mbtiles`

## Cấu Trúc Chính

```text
toll-station-pipeline/
├── data/
│   ├── clean/                 # dataset sạch dùng chính
│   ├── final/                 # file tham chiếu đồng nghiệp còn giữ
│   ├── name-normalization/    # chuẩn hóa tên + AI suggestions
│   ├── raw/                   # seed thủ công ban đầu
│   └── report/                # report tổng hợp còn cần lưu
├── gmaps-tool/                # wrapper chạy google-maps-scraper theo tỉnh
├── toll-crawler/              # crawler VETC/ePass/OSM/manual
├── scripts/                   # các bước xử lý dữ liệu
├── requirements.txt
└── .env                       # không commit, chứa OPENAI_API_KEY nếu dùng AI
```

## Output Quan Trọng

- `data/clean/toll_stations_clean.csv`: CSV sạch cuối cùng.
- `data/clean/toll_stations_clean.json`: JSON sạch cuối cùng.
- `data/clean/toll_stations_clean.geojson`: GeoJSON hiển thị trên nền OSM online.
- `data/clean/toll_stations_clean.osm`: OSM XML để merge vào PBF.
- `../data/toll/toll_stations_clean.osm`: bản copy OSM ở project root.
- `data/name-normalization/name_review_with_ai.csv`: file review tên có gợi ý AI.
- `data/name-normalization/ai_review_summary.md`: tổng kết bước AI.

Không commit các file raw/nặng/nhạy cảm:

- `.env`
- `.venv/`
- `data/final/results.csv` nếu crawl lại từ Google Maps
- các file review thủ công tạm như `data/final/1.csv`
- raw output trong `gmaps-tool/data/` và `toll-crawler/data/`
- `../data/base/*.mbtiles`
- `../data/versions/*.osm.pbf`
- `../data/output/`

Các file này đã được chặn trong `../.gitignore`.

## Setup

Tạo virtual environment:

```powershell
cd E:\Internship_VinFuture\maps-vietnam\toll-station-pipeline
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Nếu dùng OpenAI cho chuẩn hóa tên, thêm vào `.env`:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
```

## Flow Dữ Liệu Trạm Thu Phí

### 1. Crawl nguồn công khai VETC/ePass/OSM/manual

```powershell
cd E:\Internship_VinFuture\maps-vietnam\toll-station-pipeline\toll-crawler
python run_crawl.py
```

Output raw nằm trong:

```text
toll-crawler/data/raw/
```

### 2. Crawl Google Maps theo tỉnh

Smoke test:

```powershell
cd E:\Internship_VinFuture\maps-vietnam\toll-station-pipeline\gmaps-tool
.\scripts\run_scraper.ps1 -QueryFile queries\smoke_hanoi_haiphong.txt -OutputFile data\output\gmaps_smoke.csv
```

Chạy full:

```powershell
.\scripts\run_scraper.ps1 -QueryFile queries\provinces_etc.txt -OutputFile data\output\gmaps_results.csv
```

Import CSV Google Maps scraper sang raw JSON:

```powershell
python scripts\import_gmaps_csv.py
```

### 3. Chuẩn hóa, match OSM, sinh report review

Nhóm script đời đầu, dùng khi cần rebuild từ crawler raw:

```powershell
cd E:\Internship_VinFuture\maps-vietnam
python toll-station-pipeline\scripts\01_normalize_sources.py
python toll-station-pipeline\scripts\02_match_with_osm.py
python toll-station-pipeline\scripts\03_export_review_reports.py
```

Output chính:

```text
data/normalized/
data/matched/
data/report/
```

### 4. Các bước review/merge lịch sử

Các script `04` đến `10` và `15` đến `20` được giữ lại để tái hiện quá trình xử lý cũ nếu có đủ file raw/review local.

Lưu ý: sau khi dọn repo, nhiều file trung gian như `results.csv`, `results_clean_candidates.*`, `1.csv`, các report GeoJSON review cũ không còn nằm trong repo. Nếu cần chạy lại các bước này thì phải đưa lại input tương ứng.

### 5. Chuẩn hóa tên chắc chắn

```powershell
python toll-station-pipeline\scripts\21_apply_safe_name_normalization.py
```

Script này chỉ áp dụng rule an toàn:

- chuẩn hóa khoảng trắng/gạch ngang
- `Km104` -> `Km 104`
- `QL1A` -> `Quốc lộ 1A`
- `Trạm Thu Phí` -> `Trạm thu phí`
- `cao toc` -> `cao tốc`

### 6. Export OSM

```powershell
python toll-station-pipeline\scripts\13_export_clean_osm.py
```

Output:

- `toll-station-pipeline/data/clean/toll_stations_clean.osm`
- `data/toll/toll_stations_clean.osm`

### 7. Import PostgreSQL/PostGIS

Docker phải chạy trước:

```powershell
cd E:\Internship_VinFuture\maps-vietnam
docker compose up -d postgres redis api worker nginx
```

Import:

```powershell
python toll-station-pipeline\scripts\11_import_clean_to_postgres.py
```

Kết nối DBeaver:

```text
Host: 127.0.0.1
Port: 15432
Database: maps_vietnam
User: postgres
Password: 110204
Table: public.toll_stations
```

### 8. Merge OSM vào PBF và render MBTiles

Copy config tilemaker vào worker container nếu chưa rebuild image:

```powershell
docker compose cp worker\tilemaker-config.json worker:/app/tilemaker-config.json
docker compose cp worker\tilemaker-process.lua worker:/app/tilemaker-process.lua
```

Convert OSM toll sang PBF và merge vào PBF nền:

```powershell
docker compose exec -T worker osmium cat /data/toll/toll_stations_clean.osm -o /data/toll/toll_stations_clean.osm.pbf --overwrite
docker compose exec -T worker osmium merge /data/versions/vietnam-260101.osm.pbf /data/toll/toll_stations_clean.osm.pbf -o /data/versions/vietnam-260101-with-tolls.osm.pbf --overwrite
```

Render MBTiles:

```powershell
docker compose exec -T worker sh -lc "BASE_VERSION=vietnam-260101-with-tolls.osm.pbf BASE_MBTILES=/data/base/vietnam-260101-with-tolls-navigation.mbtiles python /app/build_base_map.py"
```

Frontend đang dùng:

```text
BASE_MBTILES=/data/base/vietnam-260101-with-tolls-navigation.mbtiles
```

## Flow Chuẩn Hóa Tên Và AI

### Rule-based name normalization

```powershell
python toll-station-pipeline\scripts\14_name_normalization.py
```

Output:

- `data/name-normalization/name_candidates.csv`
- `data/name-normalization/name_issues.csv`
- `data/name-normalization/name_review.csv`
- `data/name-normalization/name_clean.csv`
- `data/name-normalization/summary.md`

### AI suggestions bằng OpenAI

Chạy thử không gọi API:

```powershell
python toll-station-pipeline\scripts\22_ai_name_suggestions.py --dry-run
```

Chạy 20 dòng:

```powershell
python toll-station-pipeline\scripts\22_ai_name_suggestions.py --limit 20
```

Chạy toàn bộ dòng cần review:

```powershell
python toll-station-pipeline\scripts\22_ai_name_suggestions.py --limit 0 --sleep 0.5
```

Output:

- `data/name-normalization/ai_suggestions.csv`

Merge AI suggestion vào review cuối:

```powershell
python toll-station-pipeline\scripts\23_build_name_review_with_ai.py
```

Output:

- `data/name-normalization/name_review_with_ai.csv`
- `data/name-normalization/ai_review_summary.md`

Lưu ý: AI chỉ gợi ý, không tự apply vào dataset chính. Với dataset hiện tại, 9 dòng AI đề xuất rename đã được human override thành `keep` vì tên Google/current được ưu tiên làm tên chuẩn.

## Danh Sách Script

| Script | Vai trò |
| --- | --- |
| `01_normalize_sources.py` | Chuẩn hóa raw crawler VETC/ePass/OSM/manual/Google thành normalized JSON |
| `02_match_with_osm.py` | Match dữ liệu normalized với OSM |
| `03_export_review_reports.py` | Sinh CSV/GeoJSON report để review |
| `04_prepare_name_review_updates.py` | Chuẩn bị update tên OSM từ review tên |
| `05_prepare_remaining_issue_review.py` | Chuẩn bị review các issue còn lại |
| `06_build_final_outputs.py` | Build final CSV/JSON/GeoJSON đời đầu và SQLite |
| `07_insert_postgres.py` | Import final đời đầu vào PostgreSQL |
| `08_compare_colleague_csv.py` | So sánh dataset của mình với file đồng nghiệp |
| `09_normalize_deduplicate_sources.py` | Chuẩn hóa và tìm duplicate giữa hai nguồn |
| `10_apply_auto_keep_merge.py` | Tự động keep/merge nguồn A/B theo rule |
| `11_import_clean_to_postgres.py` | Import `data/clean/toll_stations_clean.csv` vào PostgreSQL |
| `12_publish_clean_outputs.py` | Publish clean output đời cũ; hiện hạn chế dùng vì có thể ghi đè từ nguồn cũ |
| `13_export_clean_osm.py` | Export clean CSV sang OSM XML |
| `14_name_normalization.py` | Rule-based phát hiện issue tên đối tượng |
| `15_ingest_results_csv.py` | Lọc/dedup raw Google Maps `results.csv` |
| `16_apply_results_review.py` | Apply review từ `results_review_resolved.csv` vào clean |
| `17_deduplicate_clean_tolls.py` | Dedup các cặp trạm đã xác nhận trùng |
| `18_apply_results_review_notes.py` | Áp dụng note trong file review thủ công |
| `19_apply_final_manual_fixes.py` | Fix thủ công cuối cho vài ID đặc biệt |
| `20_fix_clean_coordinates_from_candidates.py` | Sửa tọa độ bị hỏng do Excel/format số |
| `21_apply_safe_name_normalization.py` | Auto-fix tên bằng rule chắc chắn |
| `22_ai_name_suggestions.py` | Gọi OpenAI sinh gợi ý chuẩn hóa tên |
| `23_build_name_review_with_ai.py` | Merge AI suggestions vào file review cuối |

## Lệnh Kiểm Tra Nhanh

Đếm PostgreSQL:

```powershell
docker compose exec -T postgres psql -U postgres -d maps_vietnam -c "select count(*) from toll_stations;"
```

Kiểm MBTiles có layer `toll_gantry`:

```powershell
docker compose exec -T worker python -c "import sqlite3; con=sqlite3.connect('/data/base/vietnam-260101-with-tolls-navigation.mbtiles'); meta=dict(con.execute('select name,value from metadata')); print('toll_gantry' in meta.get('json',''))"
```

Chạy frontend:

```text
http://localhost:8080
```

Trên frontend:

- OSM online hiển thị trạm bằng GeoJSON.
- Nền MBTiles nội bộ hiển thị trạm từ layer `toll_gantry`.
- Badge trên map hiển thị tổng số trạm.
