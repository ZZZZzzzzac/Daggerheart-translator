#!/usr/bin/env python3
"""
zzz2keyword.py - 读取JSON文件，应用工作函数生成关键词列表，并保存为 _keyword.json 文件。

用法:
    python zzz2keyword.py <输入JSON文件路径>

描述:
    读取指定的JSON文件（根元素可以是列表或字典），将其传递给工作函数 work()，
    工作函数返回一个列表，然后将该列表写入与输入文件相同目录下的新文件，
    新文件名为 <输入文件基础名称>_keyword.json。

工作函数:
    用户应自定义 work() 函数以实现具体的处理逻辑。
    默认实现返回一个空列表作为示例。    
"""

import argparse
import json
import os
import sys
from typing import Any, List, Union


def load_json_file(filepath: str) -> Union[dict, list]:
    """读取JSON文件，返回解析后的字典或列表。"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def work(data: Union[dict, list]) -> List[Any]:
    """
    工作函数 - 用户应自定义此函数。

    参数:
        data: 从JSON文件加载的原始数据（字典或列表）

    返回:
        一个列表，包含处理后的结果（例如关键词列表）。
    """
    lst = []
    if isinstance(data, dict):
        data = [data]
    for d in data:
        dic = {}
        dic["keyword"] = d.get("名称", "")
        
        for k in ["原名", "背景问题", "关系问题"]:
            d.pop(k, None)
        
        typ = d.pop("类型", "默认类型")
        if typ == "领域卡":
            typ += "-" + d.get("领域", "")
        dic["category"] = typ

        desc = ""
        for k,v in d.items():
            if k != "名称":
                desc += f"{k}:{v}\n"
        dic["description"] = desc.strip()
        dic["display"] = "normal"
        lst.append(dic)
    return lst



def main():
    parser = argparse.ArgumentParser(
        description="读取JSON文件，应用工作函数生成关键词列表，并保存为 _keyword.json 文件。"
    )
    parser.add_argument('input', help='输入JSON文件路径')
    args = parser.parse_args()

    input_path = args.input
    if not os.path.isfile(input_path):
        print(f"错误: 文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    # 加载JSON数据
    try:
        raw_data = load_json_file(input_path)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"错误: 无法解析JSON文件: {e}", file=sys.stderr)
        sys.exit(1)

    # 调用工作函数
    result_list = work(raw_data)

    # 确保结果是列表
    if not isinstance(result_list, list):
        print(f"警告: 工作函数返回的类型不是列表，已将其包装成列表", file=sys.stderr)
        result_list = [result_list]

    # 构建输出文件路径
    input_dir = os.path.dirname(input_path)
    input_basename = os.path.basename(input_path)
    # 移除扩展名（如果有多个点，只移除最后一个）
    name_without_ext = os.path.splitext(input_basename)[0]
    output_filename = f"{name_without_ext}_keyword.json"
    output_path = os.path.join(input_dir, output_filename)

    # 写入JSON文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result_list, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到 {output_path}")
    print(f"共生成 {len(result_list)} 条记录")


if __name__ == '__main__':
    main()