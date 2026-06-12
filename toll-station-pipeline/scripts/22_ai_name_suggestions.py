from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PIPELINE_ROOT / "data" / "name-normalization"
INPUT_REVIEW_CSV = OUTPUT_DIR / "name_review.csv"
OUTPUT_AI_CSV = OUTPUT_DIR / "ai_suggestions.csv"

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

OUTPUT_COLUMNS = [
    "object_id",
    "object_type",
    "current_name",
    "candidate_names",
    "issue_types",
    "rule_suggested_name",
    "ai_suggested_name",
    "ai_action",
    "ai_confidence",
    "ai_reason",
    "ai_raw_json",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def compact_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "object_id": clean(row.get("object_id")),
        "object_type": clean(row.get("object_type")),
        "current_name": clean(row.get("current_name")),
        "candidate_names": clean(row.get("candidate_names")),
        "detected_issue": clean(row.get("issue_types")),
        "rule_suggested_name": clean(row.get("suggested_name")),
        "rule_suggested_action": clean(row.get("suggested_action")),
        "province": clean(row.get("province")),
        "road": clean(row.get("road")),
        "address": clean(row.get("address")),
        "osm_name": clean(row.get("osm_name")),
        "source_datasets": clean(row.get("source_datasets")),
    }


def system_prompt() -> str:
    return (
        "Bạn là trợ lý chuẩn hóa tên đối tượng bản đồ Việt Nam. "
        "Nhiệm vụ: đề xuất tên chuẩn cho một object, ưu tiên tên tự nhiên, có dấu, dễ đọc, "
        "không tự bịa nếu nguồn không đủ chắc. "
        "Chỉ trả về JSON hợp lệ, không markdown. "
        "Schema: {"
        "\"suggested_name\": string, "
        "\"action\": \"keep\"|\"rename\"|\"merge\"|\"manual_review\", "
        "\"confidence\": number, "
        "\"reason\": string"
        "}. "
        "Thứ tự ưu tiên nguồn tên: tên đã review thủ công, tên Google/current từ dataset sạch, "
        "nguồn chính thức, tên CSV crawl từ Google, rồi mới đến OSM. "
        "Nếu current_name đã là tên trạm rõ ràng và OSM chỉ thêm địa danh trong ngoặc, "
        "không tự thêm phần ngoặc đó; hãy keep trừ khi input có bằng chứng current_name sai. "
        "Không chọn tên dài hơn chỉ vì dài hơn. "
        "Không thêm địa danh/tuyến đường nếu Google/current không có và nguồn khác chưa đủ chắc. "
        "Lỗi format chắc chắn có thể rename; tên quá chung hoặc nguồn mâu thuẫn mạnh thì manual_review; "
        "nếu tên hiện tại đã rõ và khớp nguồn Google/current thì keep."
    )


def user_prompt(row: dict[str, str]) -> str:
    payload = compact_row(row)
    return (
        "Hãy đánh giá tên object sau và đề xuất tên chuẩn.\n"
        "Dữ liệu:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "Trả về JSON đúng schema."
    )


def extract_response_text(payload: dict[str, object]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]  # type: ignore[return-value]

    chunks: list[str] = []
    for item in payload.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def call_openai(row: dict[str, str], *, api_key: str, model: str, timeout: int) -> dict[str, object]:
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": user_prompt(row)},
        ],
        "temperature": 0.1,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "name_normalization_suggestion",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "suggested_name": {"type": "string"},
                        "action": {"type": "string", "enum": ["keep", "rename", "merge", "manual_review"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string"},
                    },
                    "required": ["suggested_name", "action", "confidence", "reason"],
                },
            }
        },
    }
    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"OpenAI HTTP {response.status_code}: {response.text[:1000]}")

    payload = response.json()
    text = extract_response_text(payload)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI returned non-JSON text: {text[:1000]}") from exc


def suggestion_row(input_row: dict[str, str], ai: dict[str, object]) -> dict[str, object]:
    return {
        "object_id": clean(input_row.get("object_id")),
        "object_type": clean(input_row.get("object_type")),
        "current_name": clean(input_row.get("current_name")),
        "candidate_names": clean(input_row.get("candidate_names")),
        "issue_types": clean(input_row.get("issue_types")),
        "rule_suggested_name": clean(input_row.get("suggested_name")),
        "ai_suggested_name": clean(ai.get("suggested_name")),
        "ai_action": clean(ai.get("action")),
        "ai_confidence": clean(ai.get("confidence")),
        "ai_reason": clean(ai.get("reason")),
        "ai_raw_json": json.dumps(ai, ensure_ascii=False),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate AI name-normalization suggestions with OpenAI.")
    parser.add_argument("--input", default=str(INPUT_REVIEW_CSV), help="Input name_review.csv")
    parser.add_argument("--output", default=str(OUTPUT_AI_CSV), help="Output ai_suggestions.csv")
    parser.add_argument("--limit", type=int, default=10, help="Max rows to process; use 0 for all rows")
    parser.add_argument("--sleep", type=float, default=0.2, help="Delay between API calls")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout seconds")
    parser.add_argument("--dry-run", action="store_true", help="Print first prompt and do not call OpenAI")
    return parser.parse_args()


def main() -> None:
    load_dotenv(PIPELINE_ROOT / ".env")
    args = parse_args()
    api_key = clean(os.getenv("OPENAI_API_KEY"))
    model = clean(os.getenv("OPENAI_MODEL")) or "gpt-4o-mini"

    rows = read_csv(Path(args.input))
    rows = [row for row in rows if clean(row.get("issue_count")) != "0"]
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    if not rows:
        raise SystemExit("No name-review rows to process.")

    if args.dry_run:
        print("MODEL:", model)
        print(user_prompt(rows[0]))
        return

    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY. Add it to toll-station-pipeline/.env or environment.")

    output_rows: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        print(f"[{index}/{len(rows)}] {row.get('object_id')} {row.get('current_name')}")
        ai = call_openai(row, api_key=api_key, model=model, timeout=args.timeout)
        output_rows.append(suggestion_row(row, ai))
        if args.sleep > 0:
            time.sleep(args.sleep)

    write_csv(Path(args.output), output_rows, OUTPUT_COLUMNS)
    print(f"Written {len(output_rows)} AI suggestions -> {args.output}")


if __name__ == "__main__":
    main()
