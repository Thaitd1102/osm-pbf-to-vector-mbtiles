# gmaps-tool

Tool này chỉ phục vụ bước crawl dữ liệu trạm thu phí từ Google Maps. Đây là nguồn bổ sung để lấy tên, tọa độ, địa chỉ, link Google Maps, CID/place id và ảnh preview nếu scraper trả về.

Phần merge, lọc trùng, chuẩn hóa tên, import DB và render bản đồ nằm ở README tổng của `toll-station-pipeline`.

## Mục Đích

Google Maps thường có tên trạm và tọa độ thực địa tốt hơn các nguồn danh sách tĩnh, nhưng dữ liệu crawl có nhiễu. Vì vậy output của tool này chỉ được xem là raw input, chưa phải dữ liệu sạch.

Tool này dùng để:

- Tạo query theo từng tỉnh/thành.
- Chạy scraper Google Maps bằng Docker image `gosom/google-maps-scraper`.
- Xuất CSV raw từ scraper.
- Convert CSV raw thành `gmaps_raw.json` để pipeline chính đọc tiếp.

## Cấu Trúc

```text
gmaps-tool/
├── config/
│   ├── provinces.csv          # Danh sách tỉnh/thành để sinh query
│   └── query_templates.txt    # Mẫu query, ví dụ: trạm thu phí {province}
├── queries/
│   ├── smoke_hanoi_haiphong.txt
│   └── provinces_etc.txt
├── scripts/
│   ├── build_queries.py       # Sinh queries/provinces_etc.txt
│   ├── run_scraper.ps1        # Wrapper chạy Docker scraper
│   └── import_gmaps_csv.py    # Convert CSV scraper sang raw JSON
├── data/
│   ├── output/
│   │   └── gmaps_results.csv  # CSV thô từ Google Maps scraper
│   └── raw/
│       └── gmaps_raw.json     # Raw JSON đưa sang pipeline tổng
└── google-maps-scraper/       # Repo/tool bên thứ ba, không commit lên git
```

## Chuẩn Bị

Yêu cầu:

- Docker Desktop đang chạy.
- Có image `gosom/google-maps-scraper`, hoặc Docker tự pull khi chạy lần đầu.
- Chạy lệnh tại folder:

```powershell
cd E:\Internship_VinFuture\maps-vietnam\toll-station-pipeline\gmaps-tool
```

## Bước 1: Sinh Query Theo Tỉnh

Script đọc:

- `config/provinces.csv`
- `config/query_templates.txt`

và sinh:

- `queries/provinces_etc.txt`

Lệnh:

```powershell
python scripts\build_queries.py
```

Khi cần thêm kiểu query, sửa `config/query_templates.txt`.

Khi cần thêm/bớt tỉnh, sửa `config/provinces.csv`.

## Bước 2: Chạy Smoke Test

Smoke test chỉ chạy vài query Hà Nội/Hải Phòng để kiểm tra Docker, scraper và format output.

```powershell
.\scripts\run_scraper.ps1 `
  -QueryFile queries\smoke_hanoi_haiphong.txt `
  -OutputFile data\output\gmaps_smoke.csv `
  -Depth 1 `
  -Concurrency 1
```

Nếu file `data/output/gmaps_smoke.csv` có dữ liệu thì mới chạy full.

## Bước 3: Crawl Full Theo Tỉnh/Thành

```powershell
.\scripts\run_scraper.ps1 `
  -QueryFile queries\provinces_etc.txt `
  -OutputFile data\output\gmaps_results.csv `
  -Depth 1 `
  -Concurrency 1
```

Có thể tăng `-Concurrency 2` nếu máy ổn và muốn chạy nhanh hơn:

```powershell
.\scripts\run_scraper.ps1 `
  -QueryFile queries\provinces_etc.txt `
  -OutputFile data\output\gmaps_results.csv `
  -Depth 1 `
  -Concurrency 2
```

Không nên tăng quá cao vì Google Maps có thể block hoặc trả kết quả thiếu ổn định.

## Bước 4: Convert CSV Sang Raw JSON

Sau khi có CSV từ scraper:

```powershell
python scripts\import_gmaps_csv.py `
  --input data\output\gmaps_results.csv `
  --output data\raw\gmaps_raw.json
```

Mặc định script chỉ giữ các dòng có dấu hiệu liên quan tới trạm thu phí như:

- `trạm thu phí`
- `tram thu phi`
- `toll`
- `VETC`
- `ePass`
- `BOT`

Nếu muốn import tất cả dòng raw để tự lọc sau:

```powershell
python scripts\import_gmaps_csv.py `
  --input data\output\gmaps_results.csv `
  --output data\raw\gmaps_raw.json `
  --include-all
```

## Output Chính

### `data/output/gmaps_results.csv`

File CSV thô từ scraper Google Maps. File này có thể rất nặng và không nên commit lên git.

Thường có các trường như:

- tên địa điểm
- địa chỉ
- latitude/longitude
- category
- rating/review count
- Google Maps URL
- place id/CID
- image/thumbnail nếu scraper lấy được

### `data/raw/gmaps_raw.json`

File raw JSON đã được chuẩn hóa nhẹ để pipeline tổng đọc tiếp.

Mỗi record có dạng chính:

```json
{
  "id": "gmaps-...",
  "source": "google_maps_scraper",
  "source_url": "...",
  "crawled_at": "...",
  "name": "...",
  "address": "...",
  "lat": 21.0,
  "lon": 105.8,
  "google_place_id": "...",
  "google_cid": "...",
  "category": "...",
  "raw": {}
}
```

## Đưa Sang Pipeline Tổng

Sau khi có `data/raw/gmaps_raw.json`, quay về folder `toll-station-pipeline` và chạy các bước xử lý chính:

```powershell
cd E:\Internship_VinFuture\maps-vietnam\toll-station-pipeline
python scripts\01_normalize_sources.py
python scripts\02_match_with_osm.py
python scripts\03_export_review_reports.py
```

Các bước sau như review, merge, export OSM, import DB và render MBTiles xem trong:

```text
toll-station-pipeline/README.md
```

## Lưu Ý

- Đây là scrape Google Maps, không phải Google Places API chính thức.
- Kết quả có thể có nhiễu: điểm dán thẻ, văn phòng VETC/ePass, công ty, bãi xe, điểm dịch vụ.
- Tên từ Google Maps thường khá tốt, nhưng tọa độ và loại địa điểm vẫn cần đối soát.
- File raw lớn như `gmaps_results.csv`, `gmaps_raw.json` nên được kiểm soát bằng `.gitignore` nếu quá nặng hoặc chỉ dùng cục bộ.
