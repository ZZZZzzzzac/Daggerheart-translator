import unittest
import makeup

CASES = [
 ('恢复 1 生命点值','恢复 1 生命点'),
 ('恢复1生命点值','恢复 1 生命点'),
 ('游戏主持人恐惧点池中的数量','游戏主持人恐惧池中的数量'),
 ('标记一个生命点','标记 1 生命点'),
 ('标记1生命点','标记 1 生命点'),
 ('获得一希望','获得 1 希望点'),
 ('失去四压力','失去 4 压力点'),
 ('恢复2d8+1生命点','恢复 2d8+1 生命点'),
 ('恢复 2D8 + 1 生命点','恢复 2d8+1 生命点'),
 ('标记1d6生命点','标记 1d6 生命点'),
 ('标记一或更多生命点','标记 1 或更多 生命点'),
 ('花费至少1希望点','花费 至少 1 希望点'),
 ('花费等量的希望点','花费 等量的 希望点'),
 ('标记最后一个护甲槽','标记 最后一个 护甲槽'),
 ('**标记一个生命点**','**标记 1 生命点**'),
 ('**花费 **1** 恐惧点**','**花费 1 恐惧点**'),
 ('花费**1**希望点','**花费 1 希望点**'),
 ('回复1生命点','恢复 1 生命点'),
 ('清除 2 生命点','恢复 2 生命点'),
 ('移除1生命点','恢复 1 生命点'),
 ('恢复1压力点','清除 1 压力点'),
 ('恢复1护甲','清除 1 护甲槽'),
 ('消耗1希望点','花费 1 希望点'),
 ('标记1绝望点','标记 1 恐惧点'),
 ('标记1生命值','标记 1 生命点'),
 ('获得两希望点','获得 2 希望点'),
 ('获得七希望点','获得 7 希望点'),
 ('标记十压力点','标记 10 压力点'),
 ('恢复所有生命点','恢复 所有 生命点'),
 ('PC可以重骰，GM也可以。','玩家角色可以重掷，游戏主持人也可以。'),
 ('**特性：**标记1压力点。\n*谁来帮助你？*','**特性：**标记 1 压力点。\n*谁来帮助你？*'),
]
UNCHANGED = [
 '游戏主持人（“GM”），玩家角色（“PC”）',
 '恢复和清除所有生命点和压力点。',
 '清除1生命点和压力点',
 '获得1护甲值','失去2护甲值','获得1希望槽','获得一种希望之光',
 '消耗敌人的生命','获得一把护甲','获得1希望骰','标记1压力点数','恢复生命',
 '标记1压力池','标记1希望点上限','失去1点护甲值','获得1护甲',
 'PC1 GM2 NPC PC_name (PC) （GM）','**特性名 Heavy - 被动：**',
 '`标记1生命点`','``代码 ` 标记1生命点``',
 '```md\n标记1生命点\n```','~~~\n标记1生命点\n~~~',
 '```\n标记1生命点','    标记1生命点\n','\t标记1生命点\n',
 '---\ntitle: 标记1生命点\n---\n',
 '[标记1生命点](https://example.com/a_(b))',
 '[标记1生命点][ref]','[标记1生命点]',
 '[ref]: https://example.com/PC标记1生命点',
 '![卡图](images/card.png)','![](_page_0_Picture_2.jpeg)',
 '<span id="section-test" data-anchor="section-test"></span>',
 '<span title="PC标记1生命点"></span>',
 '<pre>标记1生命点</pre>','<!-- PC标记1生命点 -->',
 '### 花费1希望点 {#stable-anchor}',
 'https://example.com/PC标记1生命点',
 '护甲值+2，闪避值-1；生命槽+1。','1d6+2，2/HP，11/23',
]

class TestMakeup(unittest.TestCase):
    def test_expected_and_idempotent(self):
        for old,new in CASES:
            with self.subTest(old=old):
                self.assertEqual(makeup.process_markdown(old),new)
                self.assertEqual(makeup.process_markdown(new),new)
    def test_no_false_positives(self):
        for old in UNCHANGED:
            with self.subTest(old=old):self.assertEqual(makeup.process_markdown(old),old)
    def test_structure_and_line_endings(self):
        source='| 名称 | 特性 |\r\n| --- | --- |\r\n| 测试 | 标记1压力点 |\r\n'
        self.assertEqual(makeup.process_markdown(source),source.replace('标记1压力点','标记 1 压力点'))
        source='```\n标记1压力点\n```\n标记1压力点'
        self.assertEqual(makeup.process_markdown(source),'```\n标记1压力点\n```\n标记 1 压力点')
    def test_spans_stay_untouched(self):
        source='链接 [PC标记1生命点](some(a).md)，正文标记1生命点。'
        output=makeup.process_markdown(source)
        self.assertIn('[PC标记1生命点](some(a).md)',output)
        self.assertTrue(output.endswith('正文标记 1 生命点。'))

if __name__=='__main__':unittest.main()
