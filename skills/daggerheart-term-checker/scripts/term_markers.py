"""Shared balanced marker parser; ordinary Chinese brackets are not term markers."""
import re


def parse_markers(text):
    markers, errors = [], []
    i = 0
    while i < len(text):
        if text[i] != '【':
            if text[i] == '｜':
                errors.append((i, '术语分隔符在标记外'))
            i += 1
            continue
        start, depth = i, 1
        i += 1
        while i < len(text) and depth:
            depth += (text[i] == '【') - (text[i] == '】')
            i += 1
        raw = text[start:i]
        if '｜' not in raw:
            if '|' in raw:
                errors.append((start, '术语标记使用半角分隔符'))
            continue
        if depth:
            errors.append((start, '术语标记未闭合'))
            continue
        inner = raw[1:-1]
        slots = inner.split('｜', 2)
        if len(slots) < 2 or not slots[0].strip() or not slots[1].strip():
            errors.append((start, '术语槽位为空或缺失'))
            continue
        if any('【' in slot or '】' in slot for slot in slots[:2]):
            errors.append((start, '术语正文或推荐槽位包含嵌套标记'))
            continue
        markers.append(dict(index=len(markers)+1, slot1=slots[0].strip(),
                            slot2=slots[1].strip(), slot3=slots[2].strip() if len(slots)>2 else '',
                            raw=raw, pos=start, end=i))
    return markers, errors


def readable_context(text, pos):
    """Full sentence/line, with every marker rendered as its first slot. No clipping."""
    markers, _ = parse_markers(text)
    pieces, cursor, clean_pos = [], 0, pos
    for marker in markers:
        pieces.extend([text[cursor:marker['pos']], marker['slot1']])
        if marker['pos'] < pos:
            clean_pos -= len(marker['raw']) - len(marker['slot1'])
        cursor = marker['end']
    pieces.append(text[cursor:])
    clean = ''.join(pieces)
    # English period only terminates at whitespace/end, avoiding decimal truncation.
    boundaries = list(re.finditer(r'[。！？!?\n]|\.(?=\s|$)', clean))
    start = max([m.end() for m in boundaries if m.end() <= clean_pos] or [0])
    end = next((m.end() for m in boundaries if m.start() >= clean_pos), len(clean))
    return re.sub(r'\s+', ' ', clean[start:end]).strip()
