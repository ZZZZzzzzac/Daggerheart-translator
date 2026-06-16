# makeup.py — Markdown 后处理（资源短语格式化、图片清理、排版修正）
import re
import os


def remove_image_filename(markdown_text):
    """删除 ![](_page_0_Picture_2.jpeg) 格式的图像链接"""
    return re.sub(r'!\[\]\(_page.*?\)', '', markdown_text)


def remove_span(markdown_text):
    """删除 <span.*></span> 标签"""
    return re.sub(r'<span.*?></span>', '', markdown_text, flags=re.DOTALL)


def format_resource_phrases_fn(markdown_text):
    """标准化资源短语为 "动词 数量 资源点" 格式。

    >>> f = format_resource_phrases_fn
    >>> # 基本: 中文数词/数字 + 个/点 → 数字
    >>> f('标记一个生命点')
    '标记 1 生命点'
    >>> f('标记1生命点')
    '标记 1 生命点'
    >>> f('获得一希望')
    '获得 1 希望点'
    >>> f('失去四压力')
    '失去 4 压力点'
    >>> # 骰子表达式
    >>> f('标记1d6生命点')
    '标记 1d6 生命点'
    >>> f('恢复2d8+1生命点')
    '恢复 2d8+1 生命点'
    >>> # 非简单数量 - 原样保留
    >>> f('标记一或更多生命点')
    '标记 一或更多 生命点'
    >>> f('花费至少1希望点')
    '花费 至少1 希望点'
    >>> # 穿透 ** 加粗标记
    >>> f('**标记一个生命点**')
    '**标记 1 生命点**'
    >>> f('**花费 **1** 恐惧点**')
    '**花费 1 恐惧点**'
    >>> # 动词标准化: 回复→恢复, 移除→清除, 消耗→花费
    >>> f('回复1生命点')
    '恢复 1 生命点'
    >>> f('消耗1希望点')
    '花费 1 希望点'
    >>> # 资源标准化: 绝望→恐惧, 护甲→护甲槽, 生命值→生命点
    >>> f('标记1绝望点')
    '标记 1 恐惧点'
    >>> f('恢复1护甲')
    '恢复 1 护甲槽'
    >>> f('标记1生命值')
    '标记 1 生命点'
    >>> # 幂等
    >>> f('标记 1 生命点')
    '标记 1 生命点'
    >>> # 不匹配 - 无数量
    >>> f('恢复生命')
    '恢复生命'
    """
    verbs = r'恢复|回复|标记|清除|移除|获得|花费|消耗|失去|承受'
    resources_base = r'生命|希望|压力|恐惧|绝望|恩宠|专注|回响|充能|护甲'

    pattern = rf'({verbs})(.{{1,10}}?)({resources_base})(点|值|槽)?'

    verb_map = {'回复': '恢复', '移除': '清除', '消耗': '花费'}
    num_map = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6'}
    simple_num = re.compile(r'^[一二三四五六七八九十两]?[个点]?$|^\d{1,2}[个点]?$|^\d{1,2}d\d{1,2}([+\-]\d+)?$')

    def normalize(match):
        verb = match.group(1)
        mid_raw = match.group(2)
        res = match.group(3)
        suffix = match.group(4) or ''

        verb = verb_map.get(verb, verb)
        if res == "绝望":
            res = "恐惧"

        mid_clean = mid_raw.replace('*', '').strip()
        if simple_num.match(mid_clean):
            mid_clean = mid_clean.rstrip('个点')
            mid_clean = num_map.get(mid_clean, mid_clean)

        if "护甲" in res:
            suffix = "槽"
        elif not suffix or suffix == "值":
            suffix = "点"

        return f"{verb} {mid_clean} {res}{suffix}"

    return re.sub(pattern, normalize, markdown_text)


def add_space_around_italics_fn(markdown_text):
    pattern = r'(?<=[一-龥,.，。])\*{1}[一-龥]{1,5}\*{1}(?=[一-龥,.，。])'
    return re.sub(pattern, lambda m: f" {m.group(0)} ", markdown_text)


def simplify_markdown_links_fn(markdown_text):
    if markdown_text.startswith("![]"):
        return markdown_text
    pattern = r'\[([^\]]+)\]\([^\)]*\)'
    return re.sub(pattern, lambda match: match.group(1), markdown_text)


REPLACEMENTS = [
    (r'(?<![A-Za-z\(（])PC(?![A-Za-z\)）])', '玩家角色'),
    (r'(?<![A-Za-z\(（])GM(?![A-Za-z\)）])', '游戏主持人'),
    (r'重骰', '重掷'),
]


def replace_keywords_fn(markdown_text):
    """按 REPLACEMENTS 列表执行关键词替换"""
    text = markdown_text
    for pattern, replacement in REPLACEMENTS:
        text = re.sub(pattern, replacement, text)
    return text


replace_pc_gm_fn = replace_keywords_fn


def bold_numbers_and_dice_fn(markdown_text):
    """在中文上下文中加粗数字和骰子表达式。"""
    chinese_chars_and_punctuation = r'一-龥'
    find_pattern = r'([-−+]?)\s*(\d*d\d+(?:[-−+]\s*\d+)?|\d+)'

    dice_or_number_pattern_no_space = r'[-−+]?\d*d\d+(?:[-−+]\d+)?|[-−+]?\d+'
    pattern_pre_bold = f'([{chinese_chars_and_punctuation}])(?<!\\s)\\*\\*({dice_or_number_pattern_no_space})\\*\\*'
    processed_text = re.sub(pattern_pre_bold, r'\1 **\2**', markdown_text)
    pattern_post_bold = f'\\*\\*({dice_or_number_pattern_no_space})\\*\\*(?!\\s)([{chinese_chars_and_punctuation}])'
    processed_text = re.sub(pattern_post_bold, r'**\1** \2', processed_text)

    parts = processed_text.split('**')
    new_parts = []
    for i, part in enumerate(parts):
        if i % 2 != 0:
            new_parts.append(part)
            continue

        new_sub_part = ""
        last_end = 0
        for match in re.finditer(find_pattern, part):
            new_sub_part += part[last_end:match.start()]
            start, end = match.start(), match.end()
            pre_char = part[start - 1] if start > 0 else ''
            post_char = part[end] if end < len(part) else ''

            if (pre_char == '(' and post_char == ')') or \
               (pre_char == '（' and post_char == '）'):
                new_sub_part += match.group(0)
                last_end = end
                continue

            is_pre_chinese = re.search(f'[{chinese_chars_and_punctuation}]', pre_char)
            is_post_chinese = re.search(f'[{chinese_chars_and_punctuation}]', post_char)

            if is_pre_chinese or is_post_chinese:
                cleaned_match = re.sub(r'\s', '', match.group(0))
                pre_space = '' if pre_char.isspace() or not pre_char else ' '
                post_space = '' if post_char.isspace() or not post_char else ' '
                new_sub_part += f"{pre_space}**{cleaned_match}**{post_space}"
            else:
                new_sub_part += match.group(0)
            last_end = end

        new_sub_part += part[last_end:]
        new_parts.append(new_sub_part)

    return '**'.join(new_parts)


def remove_escaped_underscore(markdown_text):
    """将 PDF 转义的 \\_ 恢复为普通 _"""
    return markdown_text.replace('\\_', '_')


makeup_list = [
    remove_image_filename,
    remove_span,
    remove_escaped_underscore,
    format_resource_phrases_fn,
    # bold_numbers_and_dice_fn,
    add_space_around_italics_fn,
    simplify_markdown_links_fn,
    replace_keywords_fn,
]


def process_markdown(content, suffix="_makeup"):
    """对 Markdown 文本内容应用 makeup_list 中的所有转换函数，返回处理后的内容。"""
    paragraphs = content.split('\n\n')
    processed_paragraphs = []
    for paragraph in paragraphs:
        processed_paragraph = paragraph
        for func in makeup_list:
            processed_paragraph = func(processed_paragraph)
        processed_paragraphs.append(processed_paragraph)
    return '\n\n'.join(processed_paragraphs)


def process_markdown_file(input_filepath, suffix="_makeup"):
    """读取文件、处理、写入新文件。返回输出文件路径。"""
    if not os.path.exists(input_filepath):
        print(f"错误：文件 '{input_filepath}' 不存在。")
        return None

    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"读取文件 '{input_filepath}' 时出错: {e}")
        return None

    processed_content = process_markdown(content, suffix)

    base, ext = os.path.splitext(input_filepath)
    output_filepath = f"{base}{suffix}{ext}"

    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.write(processed_content)
        print(f"处理完成，结果已写入 '{output_filepath}'")
    except Exception as e:
        print(f"写入文件 '{output_filepath}' 时出错: {e}")
        return None

    return output_filepath


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="对 Markdown 文件应用后处理排版")
    parser.add_argument("input", help="输入的 .md 文件路径")
    parser.add_argument("--suffix", default="", help="输出文件后缀（默认: 覆盖原文件）")
    args = parser.parse_args()
    process_markdown_file(args.input, suffix=args.suffix)
