# toll-crawler

Tool này chỉ phục vụ bước crawl raw data từ các nguồn không phải Google Maps: VETC, ePass/VDTC, OSM Overpass và file thủ công của mentor/team.

Phần chuẩn hóa, lọc trùng, merge với Google Maps, import DB, export OSM và render MBTiles nằm ở README tổng của `toll-station-pipeline`.

## Mục Đích

Nguồn Google Maps giúp lấy tọa độ và tên thực địa, còn `toll-crawler` dùng để lấy thêm danh sách tham chiếu từ các nguồn khác. Các nguồn này giúp:

- Kiểm tra trạm nào Google Maps có thể thiếu.
- Đối chiếu tên/tuyến/operator.
- Bổ sung nguồn OSM hiện có để biết đối tượng nào đã tồn tại trên bản đồ.
- Đưa file thủ công của mentor/team vào cùng format raw.

Output của tool này là raw JSON, chưa phải dữ liệu sạch.

## Cấu Trúc

```text
toll-crawler/
├── crawlers/
│   ├── base.py       # BaseCrawler: request, wrap raw record, save JSON
│   ├── vetc.py       # Crawl danh sách từ VETC
│   ├── epass.py      # Crawl danh sách từ ePass/VDTC
│   ├── osm.py        # Query Overpass API lấy toll objects từ OSM
│   └── manual.py     # Load file thủ công từ ../data/raw/toll_stations.json
├── data/
│   └── raw/
│       ├── vetc_raw.json
│       ├── epass_raw.json
│       ├── osm_raw.json
│       ├── manual_raw.json
│       └── crawl_errors.json
├── run_crawl.py
└── requirements.txt
```

## Nguồn Crawl

### VETC

Crawler: `crawlers/vetc.py`

Nguồn:

```text
https://vetc.com.vn/tram-thu-phi.html
```

Output:

```text
data/raw/vetc_raw.json
```

### ePass / VDTC

Crawler: `crawlers/epass.py`

Nguồn:

```text
https://vinfastauto.com/vn_vi/tram-thu-phi-khong-dung-epass
```

Output:

```text
data/raw/epass_raw.json
```

### OSM / Overpass

Crawler: `crawlers/osm.py`

Nguồn:

```text
https://overpass-api.de/api/interpreter
https://overpass.kumi.systems/api/interpreter
https://overpass.openstreetmap.ru/api/interpreter
```

Query lấy các object trong bbox Việt Nam có tag:

- `highway=toll_gantry`
- `barrier=toll_booth`
- `toll=yes`

Output:

```text
data/raw/osm_raw.json
```

### Manual

Crawler: `crawlers/manual.py`

Nguồn local:

```text
../data/raw/toll_stations.json
```

Output:

```text
data/raw/manual_raw.json
```

## Chuẩn Bị

Chạy tại folder:

```powershell
cd E:\Internship_VinFuture\maps-vietnam\toll-station-pipeline\toll-crawler
```

Tạo virtual environment nếu chưa có:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Cài dependencies:

```powershell
pip install -r requirements.txt
```

## Chạy Crawl

Chạy toàn bộ crawlers:

```powershell
python run_crawl.py
```

Kết quả kỳ vọng:

```text
[vetc_etc_list] Saved ... records -> data\raw\vetc_raw.json
[epass_public_list] Saved ... records -> data\raw\epass_raw.json
[osm_overpass] Saved ... records -> data\raw\osm_raw.json
[manual_mentor] Saved ... records -> data\raw\manual_raw.json

Done. Raw data saved to data/raw/
```

Nếu crawler nào lỗi, script vẫn chạy các crawler còn lại và ghi lỗi vào:

```text
data/raw/crawl_errors.json
```

## Format Raw JSON

Mỗi dòng raw được wrap theo format chung:

```json
{
  "source": "vetc_etc_list",
  "source_url": "https://...",
  "raw": {
    "Tên trạm": "...",
    "Địa chỉ": "..."
  },
  "crawled_at": "2026-06-..."
}
```

Ý nghĩa:

- `source`: tên nguồn crawl.
- `source_url`: URL hoặc file local gốc.
- `raw`: dữ liệu gốc, giữ nguyên để bước sau tự normalize.
- `crawled_at`: thời điểm crawl.

## Đưa Sang Pipeline Tổng

Sau khi crawl xong, các file raw nằm trong:

```text
toll-crawler/data/raw/
```

Các bước normalize/match tiếp theo chạy ở folder cha:

```powershell
cd E:\Internship_VinFuture\maps-vietnam\toll-station-pipeline
python scripts\01_normalize_sources.py
python scripts\02_match_with_osm.py
python scripts\03_export_review_reports.py
```

README tổng giải thích toàn bộ flow sau crawl:

```text
toll-station-pipeline/README.md
```

## Lưu Ý

- File OSM raw có thể rất lớn vì Overpass trả nhiều object có `toll=yes`, không chỉ trạm thu phí ETC.
- VETC/ePass là nguồn danh sách, có thể thiếu tọa độ hoặc thiếu trường chi tiết.
- Manual file dùng để đưa dữ liệu mentor/team vào pipeline, không tự kiểm chứng đúng sai.
- Không nên coi output raw là dữ liệu final. Raw chỉ là đầu vào cho bước normalize, deduplicate và review.
