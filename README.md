# Maps Vietnam

Project xây dựng pipeline bản đồ nội bộ cho dữ liệu OSM Việt Nam. Hệ thống hỗ trợ khoanh vùng bbox để cập nhật dữ liệu cục bộ, render lại MBTiles theo vùng cần kiểm tra, hiển thị kết quả trên frontend MapLibre và bổ sung dữ liệu POI trạm thu phí không dừng.

README này chỉ mô tả tổng quan toàn project. Các bước chi tiết nằm trong README của từng module.

## Mục Tiêu Chính

- Cập nhật bản đồ theo bbox thay vì xử lý lại toàn bộ Việt Nam.
- So sánh hai phiên bản OSM PBF, sinh diff và patched PBF.
- Render MBTiles/PNG theo vùng để kiểm tra kết quả cập nhật.
- Duy trì bản đồ nền online để đối chiếu và bản đồ nội bộ từ MBTiles để kiểm tra dữ liệu đã vá.
- Xây dựng bộ dữ liệu trạm thu phí không dừng, import vào PostgreSQL/PostGIS và merge vào bản đồ nội bộ.
- Bắt đầu pipeline đánh giá chuẩn hóa tên đối tượng bản đồ.

## Thành Phần Chính

```text
api/                         FastAPI backend, quản lý job, DB, tile endpoint
worker/                      Celery worker, osmium, tilemaker, render pipeline
frontend/                    MapLibre frontend
nginx/                       Serve frontend và proxy API/output
data/
├── versions/                Các bản OSM PBF nguồn
├── base/                    MBTiles nền nội bộ
├── cache/                   Cache extract bbox
├── output/                  Output từng job bbox
├── toll/                    OSM/PBF trạm thu phí để merge vào bản đồ
└── tmp/                     File tạm trong quá trình xử lý
toll-station-pipeline/       Pipeline dữ liệu trạm thu phí
```

## Luồng Cập Nhật Bản Đồ Theo BBox

1. Người dùng chọn bản nguồn, bản đích và khoanh bbox trên frontend.
2. API tạo job xử lý.
3. Worker extract vùng bbox từ hai bản PBF.
4. Cache giúp tránh extract lại nếu bbox/version đã xử lý trước đó.
5. `osmium derive-changes` sinh diff giữa hai vùng.
6. `osmium apply-changes` tạo `patched.osm.pbf`.
7. Frontend hiển thị `diff.geojson` để kiểm tra điểm thêm/sửa/xóa.
8. Nếu bật render, hệ thống sinh thêm MBTiles/PNG cho vùng bbox.
9. Các vùng MBTiles đã render được lưu theo job và có thể khôi phục sau khi refresh.

Output chính:

```text
patched.osm.pbf     # dữ liệu OSM đã vá theo bbox
diff.geojson        # lớp thay đổi để hiển thị trên frontend
patched.mbtiles     # vector tiles render từ patched PBF nếu bật render
preview PNG         # ảnh phục vụ kiểm tra/báo cáo nếu bật render PNG
```

## Luồng Trạm Thu Phí Không Dừng

Pipeline trạm thu phí nằm trong:

```text
toll-station-pipeline/
```

Kết quả hiện tại:

- Đã tổng hợp dữ liệu từ nhiều nguồn: Google Maps, VETC/ePass, OSM, manual/mentor và file đồng nghiệp.
- Đã lọc nhiễu, lọc trùng và chốt bộ dữ liệu sạch gồm `261` trạm hợp lệ.
- Đã xuất CSV/JSON/GeoJSON/OSM.
- Đã import vào PostgreSQL/PostGIS.
- Đã merge OSM trạm thu phí vào PBF nội bộ.
- Đã render lại MBTiles beta để hiển thị trạm thu phí trực tiếp trên bản đồ nội bộ.
- Frontend hỗ trợ hiển thị trạm trên OSM online bằng GeoJSON và trên nền nội bộ bằng layer MBTiles.

README chi tiết:

```text
toll-station-pipeline/README.md
toll-station-pipeline/gmaps-tool/README.md
toll-station-pipeline/toll-crawler/README.md
toll-station-pipeline/data/README.md
```

## Chuẩn Hóa Tên Đối Tượng

Hiện đang thử nghiệm trên nhóm trạm thu phí.

Mục tiêu:

- Phát hiện tên quá chung chung.
- Phát hiện tên thiếu chuẩn hóa như `Km104`, `QL1A`, thiếu dấu, sai hoa/thường.
- So sánh tên giữa Google Maps, OSM, file review và dataset sạch.
- Sinh file review để con người kiểm tra.
- Dùng AI để gợi ý, nhưng không tự động apply nếu chưa review.

Thư mục liên quan:

```text
toll-station-pipeline/data/name-normalization/
```

## Chạy Local Bằng Docker

Chạy tại root project:

```powershell
cd E:\Internship_VinFuture\maps-vietnam
docker compose up -d postgres redis api worker nginx
```

Frontend:

```text
http://localhost:8080
```

API:

```text
http://localhost:8000
```

PostgreSQL/PostGIS:

```text
host: 127.0.0.1
port: 15432
database: maps_vietnam
user: postgres
password: 110204
```

## Các File Lớn Không Commit

Các file sau chỉ dùng local và được bỏ qua bằng `.gitignore`:

- `.env`
- `.venv/`
- `*.osm.pbf`
- `*.mbtiles`
- `data/output/`
- `data/cache/`
- `data/tmp/`
- raw crawl nặng từ Google Maps
- repo/tool bên thứ ba trong `gmaps-tool/google-maps-scraper/`

Trước khi push nên kiểm tra:

```powershell
git status --short
git status --ignored --short
```

## Ghi Chú

- OSM online dùng để đối chiếu và khoanh vùng.
- MBTiles nội bộ dùng để kiểm tra dữ liệu đã merge/render.
- GeoJSON overlay phù hợp để review nhanh.
- OSM/PBF/MBTiles là hướng tích hợp chính thức vào bản đồ nội bộ.
