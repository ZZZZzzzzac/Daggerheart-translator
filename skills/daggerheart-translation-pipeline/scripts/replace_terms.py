import json
import os
import re
import sys

# Ensure stdout uses UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MARKER_DELIM = "｜"
PROTECTED_PATTERN = re.compile(r"(【[^】]*】)")


def _protect_urls_and_links(text):
    """Replace URLs and Markdown links with placeholders so term matching skips them."""
    placeholders = []

    link_pat = re.compile(r"(\[(?:\[??[^\[]*?\])\]\()([^)]+)(\))", re.IGNORECASE)

    def _link_replacer(match):
        url = match.group(2)
        token = f"<<<URL_{len(placeholders)}>>>"
        placeholders.append(url)
        return match.group(1) + token + match.group(3)

    text = link_pat.sub(_link_replacer, text)

    bare_url_pat = re.compile(r"(https?://[^\s<>\"']+|www\.[^\s<>\"']+)", re.IGNORECASE)

    def _bare_replacer(match):
        url = match.group(0)
        token = f"<<<URL_{len(placeholders)}>>>"
        placeholders.append(url)
        return token

    text = bare_url_pat.sub(_bare_replacer, text)
    return text, placeholders


def _restore_urls_and_links(text, placeholders):
    for idx, url in enumerate(placeholders):
        text = text.replace(f"<<<URL_{idx}>>>", url)
    return text


def _clean_marker_field(text):
    return " ".join((text or "").split()).replace(MARKER_DELIM, "|")


def _build_marker(original, translation, note=""):
    original = _clean_marker_field(original)
    translation = _clean_marker_field(translation)
    note = _clean_marker_field(note)
    if note:
        return f"【{original}{MARKER_DELIM}{translation}{MARKER_DELIM}{note}】"
    return f"【{original}{MARKER_DELIM}{translation}】"


def replace_terms(text, terms_file_path):
    if not os.path.exists(terms_file_path):
        return text

    try:
        with open(terms_file_path, "r", encoding="utf-8") as f:
            terms_data = json.load(f)
    except Exception as exc:
        print(f"Error loading terms file: {exc}")
        return text

    # Normalize PDF->MD artifacts: \_ escapes prevent \b from matching.
    text = text.replace("\\_", "_")

    # Longer terms first to avoid partial replacement.
    terms_data.sort(key=lambda item: len((item.get("term") or "").strip()), reverse=True)

    replaced_text, url_placeholders = _protect_urls_and_links(text)

    for term_entry in terms_data:
        main_term = (term_entry.get("term") or "").strip()
        translation = _clean_marker_field(term_entry.get("translation") or "")
        note = _clean_marker_field(term_entry.get("note") or "")

        if not main_term or not translation:
            continue

        if "variants" in term_entry:
            all_terms = [main_term] + [v.strip() for v in term_entry["variants"] if v.strip()]
        else:
            all_terms = [main_term]

        for original_term in all_terms:
            escaped_term = re.escape(original_term)
            try:
                per_term_cs = bool(term_entry.get("case_sensitive"))
                flags = 0 if per_term_cs else re.IGNORECASE
                pattern = re.compile(r"\b" + escaped_term + r"\b", flags)
            except re.error:
                continue

            if not pattern.search(replaced_text):
                continue

            segments = PROTECTED_PATTERN.split(replaced_text)
            new_segments = []

            for seg in segments:
                if PROTECTED_PATTERN.fullmatch(seg):
                    new_segments.append(seg)
                    continue

                replaced_seg = pattern.sub(
                    lambda match: _build_marker(match.group(0), translation, note),
                    seg,
                )
                new_segments.append(replaced_seg)

            replaced_text = "".join(new_segments)

    return _restore_urls_and_links(replaced_text, url_placeholders)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "内联术语替换：将原文中的术语标记为【原文｜推荐译文｜注释】。"
            "\n默认不区分大小写；术语条目可设 \"case_sensitive\": true 逐条开启。"
        )
    )
    parser.add_argument("input", help="输入的 .md 文件路径")
    parser.add_argument("terms", help="术语表 JSON 文件路径")
    parser.add_argument("output", nargs="?", help="输出文件路径（可选）")
    args = parser.parse_args()

    input_arg = args.input
    terms_path = args.terms
    output_path = args.output

    if os.path.exists(input_arg):
        with open(input_arg, "r", encoding="utf-8") as f:
            input_text = f.read()
    else:
        input_text = input_arg

    result = replace_terms(input_text, terms_path)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)
    else:
        print(result)
