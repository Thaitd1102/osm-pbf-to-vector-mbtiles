# Object Name Normalization

## Input

- Clean toll stations: `data\clean\toll_stations_clean.csv`
- Colleague Google dataset: `data\final\tram_thu_phi.csv`
- Reviewed OSM name updates: `data\report\merged_osm_name_updates.csv`

## Output

- `name_candidates.csv`: tất cả tên ứng viên theo từng object.
- `name_issues.csv`: các lỗi tên phát hiện bằng rule.
- `name_review.csv`: file để review tay hoặc đưa AI gợi ý.
- `name_clean.csv`: tên đề xuất hiện tại sau rule-based pass.

## Count

- Objects: 261
- Candidate name rows: 922
- Issue rows: 247
- Objects needing review: 189

## Issue Types

- missing_province_context: 136
- source_name_conflict: 36
- multiple_name_variants: 30
- osm_placeholder_name: 28
- missing_road_context: 8
- osm_road_name_as_object_name: 7
- generic_name: 2

## Severity

- low: 144
- medium: 101
- high: 2

## Suggested Next Step

1. Mở `name_review.csv` để duyệt các dòng có issue.
2. Điền `reviewed_name`, `review_status` = keep/rename/manual_review.
3. Với các dòng khó, dùng AI điền `ai_suggested_name`, `ai_confidence`, `ai_reason` trước khi review.
4. Sau khi review xong, apply ngược vào clean dataset/OSM output.

## AI Suggestion Step

Script OpenAI:

```powershell
cd E:\Internship_VinFuture
python maps-vietnam\toll-station-pipeline\scripts\22_ai_name_suggestions.py --limit 10
```

Chạy thử không gọi API:

```powershell
python maps-vietnam\toll-station-pipeline\scripts\22_ai_name_suggestions.py --dry-run
```

Input:

- `name_review.csv`

Output:

- `ai_suggestions.csv`

Biến môi trường:

- `OPENAI_API_KEY`: API key OpenAI.
- `OPENAI_MODEL`: model dùng để gợi ý tên, mặc định `gpt-4o-mini`.

AI chỉ gợi ý `suggested_name`, `action`, `confidence`, `reason`; không tự apply vào dataset chính.
