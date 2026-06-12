# Toll Station Data

Thư mục này chứa dữ liệu của pipeline trạm thu phí không dừng. README chi tiết cách chạy script nằm ở:

```text
../README.md
```

## Clean Dataset

Folder quan trọng nhất:

```text
clean/
├── toll_stations_clean.csv
├── toll_stations_clean.json
├── toll_stations_clean.geojson
└── toll_stations_clean.osm
```

Ý nghĩa:

- `toll_stations_clean.csv`: bảng dữ liệu sạch cuối cùng, hiện có `261` trạm.
- `toll_stations_clean.json`: JSON tương ứng CSV.
- `toll_stations_clean.geojson`: dùng hiển thị trên nền OSM online bằng MapLibre.
- `toll_stations_clean.osm`: dùng để merge vào PBF nội bộ trước khi render MBTiles.

## Final / Review Inputs

```text
final/
```

Hiện chỉ giữ lại file tham chiếu của đồng nghiệp:

```text
final/
└── tram_thu_phi.csv
```

Lưu ý:

- `results.csv` là raw Google Maps scraper rất lớn, không commit lên git.
- `1.csv` và các file review thủ công tạm không commit lên git.
- Các candidate/report trung gian có thể sinh lại nếu đưa raw input vào và chạy lại script tương ứng.

## Name Normalization

```text
name-normalization/
```

Chứa output của bài toán chuẩn hóa tên đối tượng:

- `name_candidates.csv`: các tên ứng viên từ nhiều nguồn.
- `name_issues.csv`: lỗi tên phát hiện bằng rule.
- `name_review.csv`: file review trước khi AI.
- `ai_suggestions.csv`: gợi ý từ OpenAI.
- `name_review_with_ai.csv`: file review đã merge AI và quyết định cuối.
- `ai_review_summary.md`: tổng kết bước AI.
- `summary.md`: tổng kết rule-based normalization.

## Reports

```text
report/
```

Hiện giữ report tổng hợp còn cần để tham chiếu:

- `colleague_compare_summary.md`: nhận xét so sánh dữ liệu của mình với file đồng nghiệp.

Các report GeoJSON/CSV trung gian cũ đã được dọn khỏi repo.

## Raw

```text
raw/
```

Chứa seed thủ công ban đầu. Đây không còn là nguồn chính, nhưng vẫn giữ để làm mẫu format hoặc bổ sung tay khi cần.

## DB / Map Integration

Dữ liệu clean đã được:

- import vào PostgreSQL/PostGIS bảng `public.toll_stations`;
- export thành OSM XML;
- merge vào PBF nội bộ;
- render lại MBTiles để frontend hiển thị layer `toll_gantry`.

Frontend:

- OSM online dùng `clean/toll_stations_clean.geojson`.
- MBTiles nội bộ dùng layer vector `toll_gantry`.
