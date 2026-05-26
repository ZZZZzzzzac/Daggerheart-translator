import os
import re


SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITING_SKILL_DIR = os.path.join(os.path.dirname(SKILL_DIR), "daggerheart-chinese-writing")
WRITING_SKILL_PATH = os.path.join(WRITING_SKILL_DIR, "SKILL.md")
REFERENCE_PATH = os.path.join(WRITING_SKILL_DIR, "REFERENCE.md")
SCHEMA_PATH = os.path.join(SKILL_DIR, "resources", "review_issue_schema.json")


def strip_frontmatter(text):
    return re.sub(r'^---\n.*?\n---\n*', '', text, count=1, flags=re.DOTALL)


def load_writing_skill():
    with open(WRITING_SKILL_PATH, "r", encoding="utf-8") as f:
        return strip_frontmatter(f.read()).strip()


def chunk_basename(path):
    return os.path.splitext(os.path.basename(path))[0]


def chunk_label_from_path(path):
    return chunk_basename(path)


def sibling_source_chunk_path(translated_chunk_path):
    return translated_chunk_path.replace(
        f"{os.sep}_translated_chunks{os.sep}",
        f"{os.sep}_chunks{os.sep}",
        1,
    )


def source_root_from_path(path):
    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    basename = os.path.basename(parent)
    if basename in {"_chunks", "_translated_chunks", "_validation", "_reviews"}:
        return os.path.dirname(parent)
    return parent


def support_dir(path, dirname):
    return os.path.join(source_root_from_path(path), dirname)


def validator_report_path(path):
    return os.path.join(support_dir(path, "_validation"), f"{chunk_basename(path)}.validator.json")


def review_report_path(path):
    return os.path.join(support_dir(path, "_reviews"), f"{chunk_basename(path)}.review.json")


def fixer_prompt_path(path):
    return os.path.join(support_dir(path, "_reviews"), f"_fix_prompt_{chunk_basename(path)}.md")


def reviewer_prompt_path(path):
    return os.path.join(support_dir(path, "_reviews"), f"_review_prompt_{chunk_basename(path)}.md")


def global_review_report_path(merged_path):
    return os.path.join(source_root_from_path(merged_path), "_reviews", "global.review.json")


def global_review_prompt_path(merged_path):
    return os.path.join(source_root_from_path(merged_path), "_reviews", "_global_review_prompt.md")


def merged_chunk_map_path(merged_path):
    root, _ = os.path.splitext(os.path.abspath(merged_path))
    return root + ".map.json"


def ensure_parent_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
