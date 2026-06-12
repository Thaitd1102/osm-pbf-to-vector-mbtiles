# Clean toll station dataset

## Source

- Input: `data/normalization/toll_stations_clean_auto.csv`
- Rule: B_final làm nền, A_colleague merge/bổ sung, A-only được giữ lại.

## Output

- `toll_stations_clean.csv`
- `toll_stations_clean.json`
- `toll_stations_clean.geojson`

## Count

- CSV rows: 127
- GeoJSON features: 127
- Active stations: 127
- Closed permanently: 0
- Province filled: 125
- Road filled: 46
- Operator filled: 0

## Note

Dataset này là bản clean hiện tại dùng để import DB và hiển thị MapLibre.
Một số trường như `operator`, `road`, `km_marker` vẫn có thể cần bổ sung thủ công nếu nguồn crawl không cung cấp đủ.
