"""Prompt-contract regression tests; not semantic-quality or accuracy tests."""
import hashlib
import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/daggerheart-translation-pipeline/scripts'
sys.path.insert(0, str(SCRIPTS))
import translation_prompt
import semantic_qa_prompt


class TranslationPromptTests(unittest.TestCase):
    def test_uses_complete_writing_skill_and_real_resources(self):
        prompt = translation_prompt.build_prompt('/trial/_chunks/01.md')
        skill = (ROOT / 'skills/daggerheart-chinese-writing/SKILL.md').read_text()
        self.assertIn(translation_prompt._strip_frontmatter(skill).strip(), prompt)
        for path in (translation_prompt.REFERENCE_PATH, translation_prompt.CORE_PATH,
                     translation_prompt.RESOURCE_GUIDE_PATH):
            self.assertTrue(Path(path).is_file())
            self.assertIn(path, prompt)
        self.assertEqual(prompt.count(translation_prompt.SEMANTIC_CHECKS), 1)

    def test_name_roles_and_context_are_distinguished(self):
        prompt = translation_prompt.build_prompt('/trial/_chunks/01.md')
        self.assertIn('世界内的人物、地名、组织和称号应译为中文', prompt)
        self.assertIn('作者署名 “Mira” 保留原文', prompt)
        self.assertIn('普通 broken', prompt)
        self.assertNotIn('保留作者名、作品名、URL 等专有名词原文', prompt)
        self.assertIn('只裁决同一含义的译名', prompt)
        self.assertIn('不默认加载 scoped/', prompt)

    def test_markers_output_and_notes_contract_retained(self):
        prompt = translation_prompt.build_prompt('/trial/_chunks/01.md', chunk_notes='源文版本：试验版')
        self.assertIn('/trial/_translated_chunks/01.md', prompt)
        self.assertIn('【当前译文｜推荐译文｜注释】', prompt)
        self.assertIn('[[[KILO_TARGET_START]]]', prompt)
        self.assertIn('不得删除、重排、合并、拆分', prompt)
        self.assertIn('源文版本：试验版', prompt)

    def test_shared_semantic_invariants_and_version_boundary(self):
        qa = semantic_qa_prompt.build_prompt('/trial/project')
        self.assertIn(translation_prompt.SEMANTIC_CHECKS, qa)
        for word in ('肯定/否定', '实际行动与行动意愿', '效果接受者', '骰式', '持续时间', '资源动词', '比较边界'):
            self.assertIn(word, qa)
        self.assertIn('不凭记忆或新版本静默改规则', qa)
        self.assertIn('没有标记的句子', qa)
        self.assertIn('采用推荐译名', qa)

    def test_both_prompts_preserve_consequential_ambiguity(self):
        # Contract tests only: these do not establish actual model compliance.
        for prompt in (translation_prompt.build_prompt('/trial/_chunks/01.md'),
                       semantic_qa_prompt.build_prompt('/trial/project')):
            with self.subTest(prompt=prompt.splitlines()[0]):
                self.assertIn(translation_prompt.SEMANTIC_CHECKS, prompt)
                for guard in ('会改变规则的歧义', '提供的更广上下文能消歧',
                              '保留源文歧义', '正文外报告准确位置、短引文和具体候选解释',
                              '不得为行文流畅擅自补定主语或范围',
                              '普通且指向明确的代词不必报疑'):
                    self.assertIn(guard, prompt)

    def test_both_prompts_keep_contextual_template_contract(self):
        for prompt in (translation_prompt.build_prompt('/trial/_chunks/01.md'),
                       semantic_qa_prompt.build_prompt('/trial/project')):
            with self.subTest(prompt=prompt.splitlines()[0]):
                self.assertIn('完整保留名称格式与机制', prompt)
                self.assertIn('条件模板只用于其限定语境', prompt)
                self.assertIn('不得从特性名套用于经历', prompt)
                self.assertIn('模板与源文含义冲突时以源文为准，并报告冲突', prompt)

    def test_pronoun_number_and_role_contract(self):
        for prompt in (translation_prompt.build_prompt('/trial/_chunks/01.md'),
                       semantic_qa_prompt.build_prompt('/trial/project')):
            for guard in ('单数、性别中性的 TA', '不能自动译成“他们”',
                          '不得机械采用“最近名词”规则', '受影响角色与行动/掷骰的协助者',
                          '项目内用户已审定解释', '以当前源文为准，不套用旧例', '泛指复数不能单独证明一次发动或花费会作用于多个目标'):
                self.assertIn(guard, prompt)

    def test_reviewed_decision_is_opt_in_and_scoped(self):
        path = '/trial/project/reviewed-decisions.json'
        for builder, arg in ((translation_prompt.build_prompt, '/trial/_chunks/01.md'),
                             (semantic_qa_prompt.build_prompt, '/trial/project')):
            self.assertNotIn(path, builder(arg))
            prompt = builder(arg, reviewed_decisions_path=path)
            self.assertIn(path, prompt)
            self.assertIn('先核对项目、完整源文/摘要及适用情境', prompt)
            self.assertIn('不重复报为未决问题', prompt)

    def test_semantic_trial_packet_is_source_only_and_has_controls(self):
        fixtures = ROOT / 'tests/fixtures'
        key = json.loads((fixtures / 'pronoun_roles.json').read_text())
        packet = json.loads((fixtures / 'pronoun_source_only_trial.json').read_text())
        cases = {c['id']: c for c in key['cases']}
        self.assertEqual([c['source'] for c in key['cases']], [c['source'] for c in packet['cases']])
        self.assertEqual([c['id'] for c in packet['cases']], ['p01', 'p02', 'p03', 'p04', 'p05', 'p06'])
        self.assertTrue(all('expectation' not in c and 'zh' not in c for c in packet['cases']))
        self.assertEqual(cases['singular-neutral']['expectation']['number'], 'singular')
        self.assertEqual(cases['plural-group']['expectation']['number'], 'plural')
        self.assertEqual(cases['helper-not-captive']['expectation']['stress_payer'], 'restrained PC')
        decision = packet['reviewed_decisions']['reviewed_decisions'][0]
        self.assertEqual(hashlib.sha256(decision['source'].encode()).hexdigest(), decision['source_sha256'])
        self.assertEqual(decision['source'], cases['reviewed-rescue']['source'])
        self.assertNotEqual(decision['source'], cases['changed-explicit-actor']['source'])
        self.assertFalse(cases['changed-explicit-actor']['expectation']['old_decision_applies'])
        self.assertEqual(cases['coordinated-plural']['expectation']['number'], 'plural')

    def test_v2_separates_coordinated_plural_from_real_ambiguity(self):
        fixtures = ROOT / 'tests/fixtures'
        key = json.loads((fixtures / 'pronoun_roles_v2.json').read_text())
        packet = json.loads((fixtures / 'pronoun_source_only_trial_v2.json').read_text())
        self.assertEqual(len(packet['cases']), 7)
        self.assertEqual([c['source'] for c in key['cases']], [c['source'] for c in packet['cases']])
        self.assertEqual(key['cases'][5]['expectation']['number'], 'plural')
        self.assertEqual(key['cases'][6]['id'], 'genuine-unresolved')
        self.assertTrue(all('expectation' not in c and 'zh' not in c for c in packet['cases']))
        self.assertEqual(packet['reviewed_decisions']['project'], 'Synthetic rescue fixture')
        self.assertIn('first PC or second PC', key['cases'][6]['expectation']['resolution'])

    def test_qa_schema_and_release_boundary(self):
        qa = semantic_qa_prompt.build_prompt('/trial/project')
        for field in ('input_digest', 'issues', 'chunk', 'problem', 'source_context', 'translated_context'):
            self.assertIn('"' + field + '"', qa)
        self.assertIn('不执行 --release', qa)
        self.assertIn('不要编造或沿用修复前摘要', qa)
        self.assertIn('不生成表示全量完成的空问题文件', qa)
        self.assertIn('不覆盖已有备份', qa)
        self.assertIn('已修复问题仅写日志', qa)

    def test_qa_cli_writes_prompt_only(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'qa.md'
            project = Path(d) / 'project'
            subprocess.run([sys.executable, str(SCRIPTS / 'semantic_qa_prompt.py'), str(project),
                            '--output', str(output)], check=True)
            self.assertTrue(output.is_file())
            self.assertFalse(project.exists())


if __name__ == '__main__':
    unittest.main()
