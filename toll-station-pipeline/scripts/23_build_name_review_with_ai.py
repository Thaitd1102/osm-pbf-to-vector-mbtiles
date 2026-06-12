import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME_DIR = ROOT / "data" / "name-normalization"
NAME_REVIEW_CSV = NAME_DIR / "name_review.csv"
AI_SUGGESTIONS_CSV = NAME_DIR / "ai_suggestions.csv"
OUTPUT_REVIEW_CSV = NAME_DIR / "name_review_with_ai.csv"
SUMMARY_MD = NAME_DIR / "ai_review_summary.md"


OUTPUT_COLUMNS = [
    "object_id",
    "object_type",
    "lat",
    "lon",
    "current_name",
    "candidate_names",
    "issue_types",
    "rule_suggested_name",
    "rule_suggested_action",
    "ai_suggested_name",
    "ai_action_original",
    "ai_action_final",
    "ai_confidence",
    "ai_reason",
    "final_review_decision",
    "final_name",
    "reviewer_note",
]


def clean(value):
    return str(value or "").strip()


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    review_rows = read_csv(NAME_REVIEW_CSV)
    ai_rows = {row["object_id"]: row for row in read_csv(AI_SUGGESTIONS_CSV)}

    output_rows = []
    ai_covered = 0
    ai_keep = 0
    ai_rename_original = 0
    human_override_keep = 0
    missing_ai = 0

    for row in review_rows:
        object_id = row["object_id"]
        ai = ai_rows.get(object_id)
        if ai:
            ai_covered += 1
            ai_action_original = clean(ai.get("ai_action"))
            ai_suggested_name = clean(ai.get("ai_suggested_name"))
            ai_confidence = clean(ai.get("ai_confidence"))
            ai_reason = clean(ai.get("ai_reason"))
        else:
            missing_ai += 1
            ai_action_original = ""
            ai_suggested_name = ""
            ai_confidence = ""
            ai_reason = ""

        ai_action_final = ai_action_original
        final_review_decision = ""
        final_name = ""
        reviewer_note = ""

        if ai_action_original == "rename":
            ai_rename_original += 1
            ai_action_final = "keep"
            final_review_decision = "keep"
            final_name = clean(row.get("current_name"))
            reviewer_note = "Human override: keep Google/current name; IC/parenthetical info may be useful."
            human_override_keep += 1
        elif ai_action_original == "keep":
            ai_keep += 1
            final_review_decision = "keep"
            final_name = clean(row.get("current_name"))
        elif ai_action_original:
            final_review_decision = ai_action_original
            final_name = ai_suggested_name or clean(row.get("current_name"))

        output_rows.append(
            {
                "object_id": object_id,
                "object_type": row.get("object_type", ""),
                "lat": row.get("lat", ""),
                "lon": row.get("lon", ""),
                "current_name": row.get("current_name", ""),
                "candidate_names": row.get("candidate_names", ""),
                "issue_types": row.get("issue_types", ""),
                "rule_suggested_name": row.get("suggested_name", ""),
                "rule_suggested_action": row.get("suggested_action", ""),
                "ai_suggested_name": ai_suggested_name,
                "ai_action_original": ai_action_original,
                "ai_action_final": ai_action_final,
                "ai_confidence": ai_confidence,
                "ai_reason": ai_reason,
                "final_review_decision": final_review_decision,
                "final_name": final_name,
                "reviewer_note": reviewer_note,
            }
        )

    write_csv(OUTPUT_REVIEW_CSV, output_rows, OUTPUT_COLUMNS)

    summary = [
        "# AI Name Review Summary",
        "",
        f"- Review rows: {len(review_rows)}",
        f"- Rows covered by AI: {ai_covered}",
        f"- Rows missing AI suggestion: {missing_ai}",
        f"- AI original keep: {ai_keep}",
        f"- AI original rename: {ai_rename_original}",
        f"- Human override rename -> keep: {human_override_keep}",
        "",
        "## Decision",
        "",
        "AI suggestions are advisory only. For the current toll-station dataset, all AI rename suggestions were overridden to `keep` because Google/current names are treated as the primary source for POI names, and IC/parenthetical parts may be useful identifiers.",
        "",
        "## Output",
        "",
        f"- `{OUTPUT_REVIEW_CSV.relative_to(ROOT)}`",
    ]
    SUMMARY_MD.write_text("\n".join(summary), encoding="utf-8")

    print(f"Review rows: {len(review_rows)}")
    print(f"AI covered: {ai_covered}")
    print(f"AI rename original: {ai_rename_original}")
    print(f"Human override rename -> keep: {human_override_keep}")
    print(f"Written: {OUTPUT_REVIEW_CSV}")
    print(f"Written: {SUMMARY_MD}")


if __name__ == "__main__":
    main()
