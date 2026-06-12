# AI Prompt Template - Object Name Normalization

## Role

Bạn là hệ thống hỗ trợ chuẩn hóa tên đối tượng bản đồ tiếng Việt.
Không tự bịa thông tin ngoài input. Nếu không đủ chắc chắn, trả về `manual_review`.

## Input JSON

```json
{
  "object_type": "toll_station",
  "current_name": "",
  "candidate_names": [],
  "issue_types": [],
  "province": "",
  "road": "",
  "address": "",
  "osm_name": "",
  "google_place_id": ""
}
```

## Output JSON

```json
{
  "suggested_name": "",
  "action": "keep | rename | merge | manual_review",
  "confidence": 0.0,
  "reason": ""
}
```

## Rules

- Ưu tiên tên có dạng tên đối tượng cụ thể, ví dụ `Trạm thu phí ...`.
- Ưu tiên tên đã review thủ công, tên Google/current trong dataset sạch, rồi mới đến OSM.
- Không chọn tên dạng placeholder như `OSM toll 123456`.
- Không chọn tên đường/hướng đi làm tên đối tượng nếu có tên trạm tốt hơn.
- Nếu nhiều tên gần giống nhau, chọn tên đầy đủ, dễ hiểu, có dấu tiếng Việt.
- Không tự thêm địa danh trong ngoặc từ OSM nếu Google/current name đã rõ và không có phần ngoặc đó.
- Không chọn tên dài hơn chỉ vì dài hơn.
- Nếu tên mâu thuẫn mạnh hoặc tọa độ/ngữ cảnh không đủ, chọn `manual_review`.

## Script

Chạy thử không gọi API:

```powershell
cd E:\Internship_VinFuture
python maps-vietnam\toll-station-pipeline\scripts\22_ai_name_suggestions.py --dry-run
```

Chạy thử 10 dòng:

```powershell
cd E:\Internship_VinFuture
python maps-vietnam\toll-station-pipeline\scripts\22_ai_name_suggestions.py --limit 10
```

Chạy toàn bộ dòng cần review:

```powershell
cd E:\Internship_VinFuture
python maps-vietnam\toll-station-pipeline\scripts\22_ai_name_suggestions.py --limit 0
```

Biến môi trường cần có trong `toll-station-pipeline/.env` hoặc terminal:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
```

Output:

```text
data/name-normalization/ai_suggestions.csv
```
