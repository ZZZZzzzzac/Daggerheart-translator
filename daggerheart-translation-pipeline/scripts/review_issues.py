import argparse
import json
import sys


SCOPES = {"chunk_review", "global_review"}
SEVERITIES = {"high", "medium", "low"}
CATEGORIES = {
    "term_miss",
    "term_overuse",
    "mechanics_form",
    "translationese",
    "dialogue_stiff",
    "description_flat",
    "feels_translated",
    "term_wrong",
    "markdown",
    "style",
}
REQUIRED_TOP_LEVEL = {"scope", "target_file", "issues"}
REQUIRED_ISSUE_FIELDS = {
    "severity",
    "category",
    "chunk_labels",
    "location",
    "problem",
    "reference",
    "suggested_fix",
}


def validate_issue_file(data, expected_mode="any"):
    errors = []

    if not isinstance(data, dict):
        return ["顶层必须是 JSON object"]

    missing = REQUIRED_TOP_LEVEL - set(data.keys())
    if missing:
        errors.append(f"缺少顶层字段: {sorted(missing)}")

    scope = data.get("scope")
    if scope not in SCOPES:
        errors.append(f"scope 非法: {scope!r}")
    elif expected_mode != "any" and scope != expected_mode:
        errors.append(f"scope 应为 {expected_mode!r}，实际 {scope!r}")

    target_file = data.get("target_file")
    if not isinstance(target_file, str) or not target_file.strip():
        errors.append("target_file 必须是非空字符串")

    issues = data.get("issues")
    if not isinstance(issues, list):
        errors.append("issues 必须是数组")
        return errors

    for idx, issue in enumerate(issues, 1):
        prefix = f"issues[{idx}]"
        if not isinstance(issue, dict):
            errors.append(f"{prefix} 必须是 object")
            continue

        missing_fields = REQUIRED_ISSUE_FIELDS - set(issue.keys())
        if missing_fields:
            errors.append(f"{prefix} 缺少字段: {sorted(missing_fields)}")

        severity = issue.get("severity")
        if severity not in SEVERITIES:
            errors.append(f"{prefix}.severity 非法: {severity!r}")

        category = issue.get("category")
        if category not in CATEGORIES:
            errors.append(f"{prefix}.category 非法: {category!r}")

        chunk_labels = issue.get("chunk_labels")
        if not isinstance(chunk_labels, list) or not chunk_labels or not all(isinstance(v, str) and v.strip() for v in chunk_labels):
            errors.append(f"{prefix}.chunk_labels 必须是非空字符串数组")
        elif scope == "chunk_review" and len(chunk_labels) != 1:
            errors.append(f"{prefix}.chunk_labels 在 chunk_review 模式下必须恰好 1 个")

        for key in ("location", "problem", "reference", "suggested_fix"):
            value = issue.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{key} 必须是非空字符串")

        for key in ("line_start", "line_end"):
            if key in issue and issue[key] is not None:
                value = issue[key]
                if not isinstance(value, int) or value <= 0:
                    errors.append(f"{prefix}.{key} 必须是正整数或 null")

    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate reviewer/global-review JSON issue files")
    parser.add_argument("path", help="Path to issue JSON file")
    parser.add_argument("--mode", default="any", choices=["any", "chunk_review", "global_review"], help="Expected scope")
    args = parser.parse_args()

    with open(args.path, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors = validate_issue_file(data, expected_mode=args.mode)
    if errors:
        for line in errors:
            print(line)
        sys.exit(1)

    issues = data["issues"]
    high = sum(1 for issue in issues if issue["severity"] == "high")
    medium = sum(1 for issue in issues if issue["severity"] == "medium")
    low = sum(1 for issue in issues if issue["severity"] == "low")
    print(f"valid {data['scope']} issue file: {len(issues)} issues (high={high}, medium={medium}, low={low})")
