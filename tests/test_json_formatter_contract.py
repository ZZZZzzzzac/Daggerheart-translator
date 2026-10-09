"""Check formatter guidance against its examples, not a production JSON schema.

The examples intentionally contain comments and trailing commas. This small
test-only reader supports their current notation; it is not an input parser.
"""
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
FORMATTER = ROOT / 'skills/daggerheart-json-formatter'


def template_examples():
    text = (FORMATTER / 'examples/template.md').read_text(encoding='utf-8')
    examples = []
    for block in re.findall(r'```\n(.*?)```', text, flags=re.DOTALL):
        # Only the current examples' end-of-line comments after commas.
        block = re.sub(r'(?m)(?<=,)[ \t]*//[^\n]*$', '', block)
        block = re.sub(r',(\s*[}\]])', r'\1', block)
        examples.extend(json.loads('[' + block.strip().rstrip(',') + ']'))
    return text, examples


def documented_body_keys(skill):
    result = {}
    for categories, key in re.findall(
            r'^  \| ([^|]+) \| (描述|简介) \|$', skill, flags=re.MULTILINE):
        for category in categories.split('、'):
            if category in result:
                raise AssertionError(f'Duplicate body-key guidance: {category}')
            result[category] = key
    return result


class JsonFormatterContractTests(unittest.TestCase):
    def setUp(self):
        self.skill = (FORMATTER / 'SKILL.md').read_text(encoding='utf-8')
        self.template, self.examples = template_examples()
        self.body_keys = documented_body_keys(self.skill)

    def test_all_example_categories_have_matching_required_body_keys(self):
        # Includes all three subclass levels and both item examples.
        self.assertEqual(len(self.examples), 13)
        example_types = {card['类型'] for card in self.examples}
        self.assertEqual(example_types, {
            '领域卡', '主武器', '护甲', '社群', '种族', '主职',
            '子职', '敌人', '环境', '物品', '消耗品',
        })
        self.assertEqual(set(self.body_keys), example_types | {'副武器'})
        # The weapon template explicitly names this alternative type.
        self.assertIn('注意还有"副武器"类型', self.template)
        self.assertEqual(self.body_keys['副武器'], self.body_keys['主武器'])
        for card in self.examples:
            with self.subTest(name=card['名称']):
                for key in ('名称', '类型', self.body_keys[card['类型']]):
                    self.assertIn(key, card)
                    self.assertTrue(card[key])

    def test_encounter_templates_do_not_require_or_duplicate_description(self):
        for card in self.examples:
            if card['类型'] in ('敌人', '环境'):
                with self.subTest(category=card['类型']):
                    self.assertEqual(self.body_keys[card['类型']], '简介')
                    self.assertNotIn('描述', card)
        self.assertIn('不能一律要求 `"描述"`', self.skill)
        self.assertIn('不得为了满足通用必填规则新增 `"描述"`', self.skill)
        self.assertIn('不要把 `"简介"` 重命名或复制为 `"描述"`', self.skill)

    def test_community_and_ancestry_keep_distinct_background_and_rules(self):
        for card in self.examples:
            if card['类型'] in ('社群', '种族'):
                with self.subTest(category=card['类型']):
                    self.assertEqual(self.body_keys[card['类型']], '描述')
                    self.assertIn('简介', card)
                    self.assertNotEqual(card['简介'], card['描述'])
        self.assertIn('前者映射背景介绍，后者映射特性正文', self.skill)
        self.assertIn('不得互相覆盖或复制填充', self.skill)


if __name__ == '__main__':
    unittest.main()
