"""Conservative Markdown rule terminology normalization.

Only explicit resource phrases are rewritten. Markdown structure and narrative
phrases are retained. Use --diff/--check to inspect a document before writing it.
"""
import argparse
import difflib
import re
from pathlib import Path


def protected_spans(text):
    """Locate code, headings, metadata, links and HTML without rendering Markdown."""
    spans = []
    lines = text.splitlines(keepends=True)
    offset = 0
    fence = None
    start = 0
    frontmatter = bool(lines and lines[0].strip() == '---')
    for i, line in enumerate(lines):
        if frontmatter:
            if i and line.strip() in ('---', '...'):
                spans.append((0, offset + len(line))); frontmatter = False
            offset += len(line); continue
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                spans.append((start, offset + len(line))); fence = None
        elif marker:
            fence, start = marker[1], offset
        elif re.match(r'^(?: {4}|\t| {0,3}#{1,6}\s| {0,3}\[[^\]]+\]:)', line):
            spans.append((offset, offset + len(line)))
        offset += len(line)
    if fence: spans.append((start, len(text)))
    if frontmatter: spans.append((0, len(text)))
    for m in re.finditer(r'<!--[\s\S]*?-->|<(pre|code|script|style)\b[^>]*>[\s\S]*?</\1\s*>|<[^>\n]+>|https?://[^\s<>]+', text, re.I):
        spans.append(m.span())
    for m in re.finditer(r'(`+)(?!`)(.*?)(?<!`)\1(?!`)', text, re.S):
        spans.append(m.span())
    # Balanced links/images; protect their labels too, including reference links.
    def closing(pos, opening, ending):
        depth = 0
        for j in range(pos, len(text)):
            if j and text[j-1] == '\\': continue
            if text[j] == opening: depth += 1
            elif text[j] == ending:
                depth -= 1
                if depth == 0: return j + 1
        return None
    pos = 0
    while pos < len(text):
        if text[pos] != '[' or (pos and text[pos-1] == '\\'):
            pos += 1; continue
        end = closing(pos, '[', ']')
        if end and end < len(text) and text[end] in '([':
            tail = closing(end, text[end], ')' if text[end] == '(' else ']')
            if tail:
                spans.append((pos-1 if pos and text[pos-1] == '!' else pos, tail)); pos = tail; continue
        # A bare [label] can be a shortcut reference; leave it alone.
        if end: spans.append((pos, end)); pos = end
        else: pos += 1
    spans.sort()
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]: merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else: merged.append((a, b))
    return merged


def transform_prose(text, transform):
    out, last = [], 0
    for a, b in protected_spans(text):
        out.extend((transform(text[last:a]), text[a:b])); last = b
    out.append(transform(text[last:]))
    return ''.join(out)


SPACE = r'[ \t]*(?:\*\*[ \t]*)*'
NUMBER = r'(?:\d*[dD]\d+(?:[ \t]*[+\-−][ \t]*\d+)?|\d+|[一二三四五六七八九十两]{1,3})'
AMOUNT = rf'(?:(?:至少|至多|最多|最少)[ \t]*)?{NUMBER}(?:[ \t]*(?:或更多|或更少))?|等量的|任意数量的|所有|全部|其余的|剩余的|最后一个'
BASE = r'生命|希望|压力|恐惧|绝望|恩宠|专注|回响|充能'
RESOURCE = rf'(?:(?:{BASE})(?:点|值|槽)(?![点值槽骰池数上限])|护甲(?:槽|值|点)(?![点值槽骰池数上限])|(?:{BASE}|护甲)(?![\u3400-\u9fffA-Za-z0-9_]))'
PHRASE = re.compile(rf'(?P<verb>恢复|回复|标记|清除|移除|获得|花费|消耗|失去|承受){SPACE}(?P<amount>{AMOUNT}){SPACE}(?:个|点)?{SPACE}(?P<resource>{RESOURCE})')
ZH_DIGITS = dict(zip('零一二三四五六七八九', range(10)))
ZH_DIGITS['两'] = 2


def normalize_number(value):
    if value in ZH_DIGITS: return str(ZH_DIGITS[value])
    if '十' in value:
        left, right = value.split('十', 1)
        if (not left or left in ZH_DIGITS) and (not right or right in ZH_DIGITS):
            return str((ZH_DIGITS.get(left, 1) * 10) + ZH_DIGITS.get(right, 0))
    return value


def _resource_phrases(text):
    def normalize(m):
        verb, amount, resource = m['verb'], m['amount'], m['resource']
        # A coordinated phrase may share its verb/quantity across resources.
        # Leave it for human review rather than assigning the first noun's verb.
        if re.search(r'(?:恢复|回复|清除|移除)[ \t]*(?:和|与|或|并)[ \t]*$', text[:m.start()]):
            return m[0]
        if re.match(r'[ \t]*(?:和|与|及|或)[ \t]*(?:生命|希望|压力|恐惧|护甲)', text[m.end():]):
            return m[0]
        # Do not swallow only one side of an emphasis span.
        stars = m[0].count('**')
        if stars % 2: return m[0]
        if resource == '护甲':
            if verb not in ('标记', '恢复', '回复', '清除', '移除'): return m[0]
            resource = '护甲槽'
        elif resource == '护甲点': resource = '护甲槽'
        elif resource == '生命值': resource = '生命点'
        elif resource in ('生命', '希望', '压力', '恐惧', '绝望', '恩宠', '专注', '回响', '充能'): resource += '点'
        # Armor Score and capacity slots are not spendable resources.
        if resource.endswith('值') or (resource.endswith('槽') and resource != '护甲槽'):
            return m[0]
        resource = resource.replace('绝望点', '恐惧点')
        verb = {'回复':'恢复', '消耗':'花费'}.get(verb, verb)
        if verb in ('清除', '移除') and resource == '生命点': verb = '恢复'
        elif verb in ('恢复', '移除') and resource in ('压力点', '护甲槽'): verb = '清除'
        elif verb == '移除': verb = '清除'
        if amount != '最后一个':
            amount = re.sub(r'[一二三四五六七八九十两]+', lambda x:normalize_number(x[0]), amount)
        amount = re.sub(r'\s*([dD+\-−])\s*', lambda x:x[1].lower().replace('−','-'), amount)
        amount = re.sub(r'^(至少|至多|最多|最少)\s*', r'\1 ', amount)
        amount = re.sub(r'\s*(或更多|或更少)$', r' \1', amount)
        phrase = f'{verb} {amount} {resource}'
        if stars and text[:m.start()].count('**') % 2 == 0: phrase = '**'+phrase+'**'
        return phrase
    return PHRASE.sub(normalize, text)


def format_resource_phrases_fn(text):
    return transform_prose(text, _resource_phrases)


REPLACEMENTS = [
    (r'''(?<![A-Za-z0-9_(（“”‘’"'])PC(?![A-Za-z0-9_)）“”‘’"'])''', '玩家角色'),
    (r'''(?<![A-Za-z0-9_(（“”‘’"'])GM(?![A-Za-z0-9_)）“”‘’"'])''', '游戏主持人'),
    (r'重骰', '重掷'),
    (r'生命点值', '生命点'),
    (r'恐惧点池', '恐惧池'),
]


def replace_keywords_fn(text):
    def replace(prose):
        for pattern, replacement in REPLACEMENTS: prose = re.sub(pattern, replacement, prose)
        return prose
    return transform_prose(text, replace)


replace_pc_gm_fn = replace_keywords_fn


def add_space_around_italics_fn(text):
    return transform_prose(text, lambda s:re.sub(r'(?<=[一-龥,.，。])\*([一-龥]{1,5})\*(?=[一-龥,.，。])', r' *\1* ', s))


def add_space_between_chinese_and_ascii_fn(text):
    def space(s):
        s = re.sub(r'(?<=[A-Za-z0-9])(?=[一-龥])', ' ', s)
        return re.sub(r'(?<=[一-龥])(?=[A-Za-z])', ' ', s)
    return transform_prose(text, space)


def remove_image_filename(text):
    # Retained as an explicit opt-in helper; never called by the default pipeline.
    return re.sub(r'!\[\]\(_page_[^\n)]*\)', '', text)


def remove_span(text):
    """Remove only truly attribute-free empty spans, retaining all anchors."""
    return re.sub(r'<span\s*>\s*</span>', '', text)


def remove_escaped_underscore(text):
    return transform_prose(text, lambda s:s.replace('\\_', '_'))


def simplify_markdown_links_fn(text):
    """Compatibility helper: link stripping is no longer a normalization step."""
    return text


def bold_numbers_and_dice_fn(text):
    """Opt-in number emphasis, restricted to prose outside existing emphasis."""
    def bold(s):
        parts = s.split('**')
        for i in range(0,len(parts),2):
            parts[i] = re.sub(r'(?<=[一-龥])([+−-]?\d*(?:d\d+|\d+)(?:[+−-]\d+)?)',r' **\1** ',parts[i])
        return '**'.join(parts)
    return transform_prose(text, bold)


makeup_list = [replace_keywords_fn, format_resource_phrases_fn, add_space_around_italics_fn]


def process_markdown(content, suffix='_makeup', *, space_ascii=False):
    for func in makeup_list: content = func(content)
    if space_ascii: content = add_space_between_chinese_and_ascii_fn(content)
    return content


def process_markdown_file(input_filepath, suffix='_makeup', *, space_ascii=False):
    path = Path(input_filepath)
    content = path.read_bytes().decode('utf-8')
    result = process_markdown(content, suffix, space_ascii=space_ascii)
    output = path.with_name(path.stem + suffix + path.suffix)
    output.write_bytes(result.encode('utf-8'))
    print(f'处理完成，结果已写入 {output}')
    return str(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='保留 Markdown 结构的规则术语规范化')
    parser.add_argument('input')
    parser.add_argument('--suffix', default='', help='输出后缀；默认覆盖原文件')
    parser.add_argument('--space-ascii', action='store_true', help='额外调整正文中英混排空格')
    parser.add_argument('--diff', action='store_true', help='只显示差异，不写文件')
    parser.add_argument('--check', action='store_true', help='只检查；有变化时返回 1')
    args = parser.parse_args()
    if args.diff or args.check:
        source = Path(args.input).read_bytes().decode('utf-8')
        result = process_markdown(source, space_ascii=args.space_ascii)
        if args.diff: print(''.join(difflib.unified_diff(source.splitlines(True), result.splitlines(True), fromfile=args.input, tofile=args.input+' (normalized)')),end='')
        if args.check: raise SystemExit(int(source != result))
    else: process_markdown_file(args.input, args.suffix, space_ascii=args.space_ascii)
