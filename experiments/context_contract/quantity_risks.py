"""Opt-in, scoped quantity surface comparisons, never semantic verdicts.

Selectors are reviewed declarations, not automatic alignment. Unsupported forms
and empty comparisons need review; matching tokens cannot verify their roles.
"""
import json
import re
import subprocess

VERSION = 'mechanic-quantity-scopes-v1'
NOTE = ('Only declared scopes and supported quantity spellings are compared. '
        'Risks are review clues, not translation-error counts. Matching quantities '
        'do not verify meaning, units, attribution, conditions, or completeness.')


def read(path):
    """Reject duplicate JSON keys instead of silently changing a declaration."""
    from pathlib import Path
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON object key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def _object(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(label + ' requires exactly: ' + ', '.join(keys))


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' must be a nonempty string')


def _parts(pointer):
    _text(pointer, 'quantity field pointer')
    if not pointer.startswith('/') or re.search(r'~(?![01])', pointer):
        raise ValueError('invalid RFC 6901 quantity field pointer')
    parts = [p.replace('~1', '/').replace('~0', '~') for p in pointer[1:].split('/')]
    if len(parts) < 2 or parts[0] != 'quantity_fields':
        raise ValueError('field pointer must name a value inside /quantity_fields/')
    return parts


def validate_config(sources, config, *, markdown_only=False):
    _object(config, ('version', 'scopes'), 'quantity scopes document')
    if config['version'] != VERSION or not isinstance(config['scopes'], list):
        raise ValueError('unsupported quantity scopes version or invalid scopes array')
    if not isinstance(sources, list) or not sources:
        raise ValueError('quantity scopes require nonempty source units')
    units = set()
    for unit in sources:
        if not isinstance(unit, dict):
            raise ValueError('source unit must be an object')
        _text(unit.get('id'), 'source unit id')
        if unit['id'] in units or not isinstance(unit.get('source'), str):
            raise ValueError('invalid source or duplicate source unit id')
        units.add(unit['id'])
    ids, endpoints = set(), set()
    for scope in config['scopes']:
        _object(scope, ('id', 'unit_id', 'source', 'translation'), 'quantity scope')
        _text(scope['id'], 'quantity scope id')
        _text(scope['unit_id'], 'quantity scope unit_id')
        if scope['id'] in ids or scope['unit_id'] not in units:
            raise ValueError('duplicate quantity scope id or unknown source unit')
        ids.add(scope['id'])
        for side in ('source', 'translation'):
            selector = scope[side]
            if not isinstance(selector, dict):
                raise ValueError('quantity selector must be an object')
            kind = selector.get('kind')
            if kind == 'unit':
                _object(selector, ('kind',), 'unit selector')
                key = ('unit',)
            elif kind == 'block':
                _object(selector, ('kind', 'block'), 'block selector')
                if type(selector['block']) is not int or selector['block'] < 0:
                    raise ValueError('quantity block must be a zero-based nonnegative integer')
                key = ('block', selector['block'])
            elif kind == 'field':
                _object(selector, ('kind', 'pointer'), 'field selector')
                _parts(selector['pointer'])
                if markdown_only:
                    raise ValueError('quantity field selectors are standalone-scan only; prepared runs deliver Markdown')
                key = ('field', selector['pointer'])
            else:
                raise ValueError('unsupported quantity selector kind')
            endpoint = (scope['unit_id'], side, *key)
            if endpoint in endpoints:
                raise ValueError('duplicate quantity scope endpoint: ' + repr(endpoint))
            endpoints.add(endpoint)


def _inline(inlines):
    text = []
    for node in inlines:
        kind, content = node['t'], node.get('c')
        if kind == 'Str':
            text.append(content)
        elif kind in {'Space', 'SoftBreak', 'LineBreak'}:
            text.append(' ')
        elif kind in {'Emph', 'Strong'}:
            text.append(_inline(content))
        elif kind == 'Link':
            text.append(_inline(content[-2]))  # Destinations and titles are not quantities.
        else:
            raise ValueError('unsupported inline in quantity scope: ' + kind)
    return ''.join(text)


def _block(block):
    if block['t'] in {'Para', 'Plain'}:
        return _inline(block['c'])
    if block['t'] == 'Header':
        return _inline(block['c'][-1])
    raise ValueError('unsupported top-level quantity block: ' + block['t'])


def _evidence(records, uid, side, selector, parse_ast, cache):
    result = {'unit_id': uid, 'selector': dict(selector), 'side': side,
              'offset_basis': 'Unicode code points in extracted_text, not raw Markdown'}
    matches = [(i, u) for i, u in enumerate(records) if isinstance(u, dict) and u.get('id') == uid]
    if len(matches) != 1:
        result['unavailable'] = 'selected unit missing or duplicated'
        return result
    index, unit = matches[0]
    prefix = '/' + str(index) if side == 'source' else '/units/' + str(index)
    result['record_pointer'] = prefix
    try:
        if selector['kind'] == 'field':
            value = unit
            result['field_pointer'] = prefix + selector['pointer']
            for part in _parts(selector['pointer']):
                if isinstance(value, dict) and part in value:
                    value = value[part]
                elif isinstance(value, list) and re.fullmatch(r'0|[1-9][0-9]*', part) and int(part) < len(value):
                    value = value[int(part)]
                else:
                    raise ValueError('quantity field missing or invalid array index')
            if not isinstance(value, str):
                raise ValueError('quantity field must be a plain string')
            result['extracted_text'] = value
        else:
            result['field_pointer'] = prefix + '/' + side
            value = unit.get(side)
            if not isinstance(value, str):
                raise ValueError('selected quantity unit must contain Markdown text')
            result['raw_text'] = value
            key = (side, uid)
            if key not in cache:
                cache[key] = parse_ast(value)['blocks']
            blocks = cache[key]
            if selector['kind'] == 'block':
                index = selector['block']
                result['ast_paths'] = ['/blocks/' + str(index)]
                if index >= len(blocks):
                    raise ValueError('selected quantity Markdown block is missing')
                result['extracted_text'] = _block(blocks[index])
            else:
                result['ast_paths'] = ['/blocks/' + str(i) for i in range(len(blocks))]
                result['extracted_text'] = '\n\n'.join(_block(block) for block in blocks)
        result.update(tokenize(result['extracted_text']))
    except (ValueError, RuntimeError, subprocess.SubprocessError, OSError,
            KeyError, TypeError, IndexError, AttributeError) as error:
        result['unavailable'] = str(error)
    return result


# Intentionally bounded grammar. No NFKC: fractions/superscripts must not become
# ordinary integers. Full-width decimal digits alone are a safe spelling variant.
FULLWIDTH = str.maketrans('０１２３４５６７８９Ｄｄ．，＋－／％：～', '0123456789Dd.,+-/%:~')
CN_DIGITS = '零一二三四五六七八九'
CN = '零〇一二两兩三四五六七八九十百千万萬亿億兆半壹贰貳叁參肆伍陆陸柒捌玖拾佰仟'
SMALL = ('zero one two three four five six seven eight nine ten eleven twelve '
         'thirteen fourteen fifteen sixteen seventeen eighteen nineteen').split()
TENS = 'twenty thirty forty fifty sixty seventy eighty ninety'.split()
WORDS = SMALL + TENS + ['hundred', 'thousand', 'million', 'billion', 'half', 'halves',
                        'quarter', 'quarters', 'dozen', 'once', 'twice', 'thrice']
ORDINALS = ('first second third fourth fifth sixth seventh eighth ninth tenth '
            'eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth '
            'eighteenth nineteenth twentieth thirtieth fortieth fiftieth sixtieth '
            'seventieth eightieth ninetieth hundredth thousandth').split()
WORDS += ORDINALS + [word + 's' for word in ORDINALS]
# Longest first prevents the singular part of "thirds" being accepted separately.
WORDS.sort(key=len, reverse=True)
WORD = '(?:' + '|'.join(WORDS) + ')'
NUM = r'[0-9]+(?:[.,][0-9]+)*'
CN_NUM = '[' + CN + ']+'
ATOM = '(?:' + NUM + '|' + CN_NUM + ')'
DICE_LEXEME = (r'(?:[+−-]\s*)?(?:' + NUM + r'\s*)?[dD]\s*' + NUM +
               r'(?:[A-Za-z0-9!]+)?(?:\s*[+−*/×÷^⁄-]\s*(?:[0-9]*[dD]\s*)?' + NUM + r')*(?:\s*[%％‰])?')
NUMBER_LEXEME = (r'(?:[+−-]\s*)?[.,]?' + NUM + r'(?:[eE][+−-]?[0-9]+|[A-Za-z]+[A-Za-z0-9]*)?'
                  r'(?:\s*(?:[+−*/／:：×÷^⁄–—~～-]|到|至|点|點|\bto\b|\bthrough\b)\s*' + ATOM + r')*(?:\s*(?:[%％‰]|\bpercent\b|\bper\s+cent\b))?')
CHINESE_LEXEME = (r'(?:第\s*)?' + CN_NUM + r'(?:[点點分之]+[' + CN + r'0-9]+)?'
                   r'(?:\s*(?:[–—~～-]|到|至)\s*' + ATOM + r')*(?:\s*[%％‰])?')
LEXEMES = re.compile('|'.join([
    r'(?:负|負|正|\bnegative\s+|\bminus\s+|\bplus\s+)\s*(?:' + ATOM + '|' + WORD + ')',
    NUM + r'(?:\s+' + NUM + r')+',
    r'(?<![A-Za-z0-9])' + DICE_LEXEME,
    r'第\s*[0-9]+',
    r'[A-Za-z]+[0-9]+[A-Za-z0-9]*',
    NUMBER_LEXEME,
    CHINESE_LEXEME,
    r'(?<![A-Za-z])' + WORD + r'(?:(?:\s+(?:(?:and|point)\s+)?|-)'+ WORD + r')*(?:\s*(?:%|\bpercent\b|\bper\s+cent\b))?(?![A-Za-z])',
]), re.I)
STRICT_DICE = re.compile(r'([0-9]*)[dD]([0-9]+)(?:([+−-])([0-9]+))?')
UNIT_SUFFIX = re.compile(r'(?:点|點|次|个|個|名|颗|顆|枚|张|張|只|位|轮|輪|回合|小时|小時|分钟|分鐘|天|日|周|米|尺|格|步|级|級|层|層|项|項|种|種|条|條|份|压力|壓力|希望|生命|护甲|護甲|伤害|傷害|目标|目標|敌人|敵人|盟友|骰|以上|以下|以内|以內|以外)')
AMBIGUOUS_CN = re.compile('一旦|一起|一同|一并|一併|一律|一致|唯一|统一|統一|万一|萬一|两者|兩者|二者|一方|十分|一半')
URL = re.compile(r"https?://[A-Za-z0-9:/?#\[\]@!$&'()*+,;=%._~+\-]+")


def _cn_spelling(number):
    if number == 0:
        return '零'
    text, zero = '', False
    for scale, unit in [(1000, '千'), (100, '百'), (10, '十'), (1, '')]:
        digit, number = divmod(number, scale)
        if digit:
            if zero:
                text += '零'
            text += CN_DIGITS[digit] + unit
            zero = False
        elif text and number:
            zero = True
    return text[1:] if text.startswith('一十') else text


def _cn_integer(text):
    text = text.replace('〇', '零').replace('两', '二').replace('兩', '二')
    if text in CN_DIGITS:
        return str(CN_DIGITS.index(text))
    # Standard cardinal forms through 9999 only. Shorthand such as 一百二,
    # digit strings such as 二〇二六, and larger units remain uncertain.
    if not re.fullmatch('[零一二三四五六七八九十百千]+', text):
        return None
    total, digit = 0, 0
    for char in text:
        if char in CN_DIGITS:
            digit = CN_DIGITS.index(char)
        else:
            total += (digit or 1) * {'十': 10, '百': 100, '千': 1000}[char]
            digit = 0
    total += digit
    return str(total) if 0 <= total <= 9999 and _cn_spelling(total) == text else None


def _english_integer(text):
    parts = text.lower().replace('-', ' ').split()
    if len(parts) == 1:
        if parts[0] in SMALL:
            return str(SMALL.index(parts[0]))
        if parts[0] in TENS:
            return str((TENS.index(parts[0]) + 2) * 10)
        return {'once': '1', 'twice': '2'}.get(parts[0])
    if len(parts) == 2 and parts[0] in TENS and parts[1] in SMALL[1:10]:
        return str((TENS.index(parts[0]) + 2) * 10 + SMALL.index(parts[1]))
    return None


def tokenize(text):
    """Offsets always refer to the supplied extracted text, including full width."""
    normalized = text.translate(FULLWIDTH)
    # Mask URLs without changing offsets. Explicit Markdown destinations were
    # already omitted by the AST extraction; bare URLs are not quantity evidence.
    for match in list(URL.finditer(normalized)):
        normalized = normalized[:match.start()] + ' ' * len(match.group()) + normalized[match.end():]
    tokens, uncertain, covered = [], [], set()
    ambiguous = [m.span() for m in AMBIGUOUS_CN.finditer(text)]
    for match in LEXEMES.finditer(normalized):
        start, end = match.span()
        covered.update(range(start, end))
        value, kind, reason = None, 'integer', 'unsupported or ambiguous numeric form'
        raw = match.group()
        compact = re.sub(r'\s+', '', raw)
        if len(raw) > 128:
            reason = 'numeric expression exceeds supported length'
        elif (dice := STRICT_DICE.fullmatch(compact)):
            count, faces, sign, modifier = dice.groups()
            if int(count or '1') > 0 and int(faces) > 0:
                kind = 'dice'
                value = str(int(count or '1')) + 'd' + str(int(faces))
                if modifier is not None:
                    value += ('-' if sign in {'−', '-'} else '+') + str(int(modifier))
        elif re.fullmatch('[0-9]+', raw):
            value = str(int(raw))
        elif re.fullmatch('[' + CN + ']+', raw):
            value = _cn_integer(raw)
            suffix = text[end:]
            if any(a < end and start < b for a, b in ambiguous) or (
                    suffix and '\u4e00' <= suffix[0] <= '\u9fff' and not UNIT_SUFFIX.match(suffix)):
                value, reason = None, 'Chinese numeral has an ambiguous lexical context'
        else:
            value = _english_integer(raw)
        if value is not None and (re.match(r'\s*[+−*/×÷^⁄–—~～-]', normalized[end:]) or
                                  (start and normalized[start - 1] in './')):
            value, reason = None, 'quantity is adjacent to unsupported numeric syntax'
        evidence = {'start': start, 'end': end, 'quote': text[start:end]}
        if value is None:
            uncertain.append(dict(evidence, reason=reason))
        else:
            tokens.append(dict(evidence, kind=kind, value=value))
    # Unicode numerals outside the explicit grammar (e.g. ½, ², Ⅲ, Arabic-Indic
    # digits) must remain visible as uncertainty, never disappear into equality.
    for index, char in enumerate(normalized):
        if index not in covered and char.isnumeric():
            uncertain.append({'start': index, 'end': index + 1, 'quote': text[index:index + 1],
                              'reason': 'unsupported Unicode numeric form'})
    return {'tokens': tokens, 'uncertain': sorted(uncertain, key=lambda item: item['start'])}


def scan(sources, translations, config, parse_ast):
    result = {'version': VERSION, 'status': 'needs_review', 'semantic_verified': False,
              'release_allowed': False, 'configuration_errors': [], 'scopes': [],
              'risk_count': 0, 'note': NOTE}
    try:
        validate_config(sources, config)
    except ValueError as error:
        result['configuration_errors'] = [str(error)]
        return result
    records = translations.get('units') if isinstance(translations, dict) else None
    records = records if isinstance(records, list) else []
    cache = {}
    for scope in config['scopes']:
        source = _evidence(sources, scope['unit_id'], 'source', scope['source'], parse_ast, cache)
        target = _evidence(records, scope['unit_id'], 'translation', scope['translation'], parse_ast, cache)
        risks = []
        if 'unavailable' in source or 'unavailable' in target:
            kinds = [('quantity_scope_unavailable', 'A declared scope cannot be reliably extracted.')]
        else:
            kinds = []
            if source['uncertain'] or target['uncertain']:
                kinds.append(('quantity_not_comparable', 'Unsupported forms or ambiguous lexical contexts need review.'))
            left = [(t['kind'], t['value']) for t in source['tokens']]
            right = [(t['kind'], t['value']) for t in target['tokens']]
            if not left and not right:
                kinds.append(('no_comparable_quantities', 'No supported quantity evidence on either side.'))
            elif left != right:
                kinds.append(('quantity_sequence_difference', 'Ordered quantity surfaces differ; legitimate reordering is possible.'))
        for kind, detail in kinds:
            risks.append({'kind': kind, 'detail': detail, 'source': source, 'translation': target})
        result['scopes'].append({'id': scope['id'], 'unit_id': scope['unit_id'],
                                 'status': 'needs_review' if risks else 'quantity_surface_match',
                                 'semantic_verified': False, 'source': source, 'translation': target,
                                 'risks': risks})
        result['risk_count'] += len(risks)
    result['release_allowed'] = not result['risk_count']
    result['status'] = ('needs_review' if result['risk_count'] else
                        'quantity_surface_match' if result['scopes'] else 'no_scopes_configured')
    return result


def policy(config):
    return ('已显式选择的机制数量范围如下。仅比较这些范围内受支持的数量写法，差异、空范围和不确定形式须审阅；'
            '风险数不是译错数，数量相同也不证明机制正确。不得按扫描结果强改、删句或改写原文来过关。'
            'source/translation 的 block 为各自 CommonMark 顶层块的零起始索引，不自动对齐。'
            '\n机制数量范围：\n' + json.dumps(config, ensure_ascii=False))
