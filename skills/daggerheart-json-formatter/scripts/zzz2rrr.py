#!/usr/bin/env python3
"""
zzz2rrr.py - 处理JSON文件或文件夹，合并数据并应用工作函数。

用法:
    python zzz2rrr.py <输入路径> [--zzz | --rrr]

参数:
    <输入路径>          JSON文件或包含JSON文件的文件夹
    --zzz              使用zzz模式调用工作函数
    --rrr              使用rrr模式调用工作函数

描述:
    读取输入路径下的所有JSON文件。每个JSON文件可以是字典或列表。
    如果是字典，将其添加到输出列表中；如果是列表，则将其元素合并到输出列表中。
    然后将输出列表和工作模式传递给工作函数。
"""

import argparse
import json
import os
import sys
import zipfile
import datetime
import uuid
from typing import Union, List, Dict, Any


def load_json_file(filepath: str) -> Union[Dict, List]:
    """读取JSON文件，返回解析后的字典或列表。"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_dhcb_file(filepath: str) -> Union[Dict, List]:
    """
    读取.dhcb（ZIP）文件，提取根目录下的card.json并解析。
    返回解析后的字典或列表。
    """
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            # 寻找根目录下的card.json
            # 可能位于根目录或一级子目录，这里简单处理
            candidates = [name for name in zf.namelist() if name.lower().endswith('cards.json')]
            if not candidates:
                # 尝试寻找任何.json文件
                candidates = [name for name in zf.namelist() if name.lower().endswith('.json')]
                if not candidates:
                    raise ValueError(f"ZIP文件中未找到cards.json或任何JSON文件")
            # 选择第一个（假设是card.json）
            target = candidates[0]
            with zf.open(target) as f:
                content = f.read().decode('utf-8')
                return json.loads(content)
    except zipfile.BadZipFile:
        raise ValueError(f"文件不是有效的ZIP压缩包: {filepath}")
    except json.JSONDecodeError as e:
        raise ValueError(f"ZIP内的JSON文件解析失败: {e}")


def collect_data(input_path: str) -> List[Any]:
    """
    从输入路径收集数据。
    如果输入是文件，根据扩展名处理：
        - .json: 使用 load_json_file
        - .dhcb 或 .zip: 使用 load_dhcb_file
    如果输入是文件夹，递归遍历所有.json文件。
    返回合并后的列表。
    """
    all_data = []
    if os.path.isfile(input_path):
        # 检查扩展名
        lower_path = input_path.lower()
        if lower_path.endswith('.json'):
            data = load_json_file(input_path)
        elif lower_path.endswith('.dhcb') or lower_path.endswith('.zip'):
            data = load_dhcb_file(input_path)
        else:
            raise ValueError(f"不支持的文件扩展名: {input_path}，仅支持 .json, .dhcb, .zip")
        # 处理数据
        if isinstance(data, dict):
            all_data.append(data)
        elif isinstance(data, list):
            all_data.extend(data)
        else:
            raise ValueError(f"文件 {input_path} 的根元素既不是字典也不是列表")
    elif os.path.isdir(input_path):
        # 遍历文件夹
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith('.json'):
                    filepath = os.path.join(root, file)
                    try:
                        data = load_json_file(filepath)
                        if isinstance(data, dict):
                            all_data.append(data)
                        elif isinstance(data, list):
                            all_data.extend(data)
                        else:
                            print(f"警告: {filepath} 的根元素既不是字典也不是列表，已跳过", file=sys.stderr)
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        print(f"警告: 无法解析 {filepath}: {e}", file=sys.stderr)
    else:
        raise FileNotFoundError(f"输入路径不存在: {input_path}")
    return all_data

def gen_uuid() -> int:
    """生成唯一ID（使用UUID v4）。"""
    return str(uuid.uuid4().int) # pyright: ignore[reportReturnType]

def work_zzz(data: List[Any], input_path: str = "") -> Any:
    """
    将zzz格式转换为rrr格式。
    使用输入文件名作为包名称，当前日期时间作为版本。
    """
    # 从输入路径派生包名称（不带扩展名和路径）
    if input_path:
        name = os.path.splitext(os.path.basename(input_path))[0]
    else:
        name = "扩展包"
    # 版本使用当前日期时间，格式如 YYYYMMDD_HHMMSS
    version = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 初始化结果结构
    dict_out = {
        "name": name,
        "version": version,
        "description": "",
        "author": "",
        "customFieldDefinitions": {
            "professions": [],
            "ancestries": [],
            "communities": [],
            "domains": [],
            "variants": []
        },
        "profession": [],
        "ancestry": [],
        "community": [],
        "subclass": [],
        "domain": [],
        "variant": []
    }
    for d in data:
        type_ = d.get("类型", "")
        name_ = d.get("名称", "")
        dict_in = {}
        dict_in["id"] = gen_uuid()
        dict_in["名称"] = name_
        if type_ == "主职":
            if name_ not in dict_out["customFieldDefinitions"]["professions"]:
                dict_out["customFieldDefinitions"]["professions"].append(name_)
            domain = d.get("领域", "").replace(" ", "").replace("&", "+").replace("与", "+").replace("和", "+").replace("，", "+").replace(",", "+")
            domain_parts = domain.split("+")
            dict_in["领域1"] = domain_parts[0] if len(domain_parts) > 0 else ""
            dict_in["领域2"] = domain_parts[1] if len(domain_parts) > 1 else ""
            dict_in["起始生命"] = int(d.get("初始生命点", ""))
            dict_in["起始闪避"] = int(d.get("初始闪避值", ""))
            dict_in["起始物品"] = d.get("初始物品") or d.get("职业物品") or " "
            dict_in["简介"] = d.get("简介") or d.get("描述") or "N/A"
            dict_in["希望特性"] = d.get("希望特性", "")
            dict_in["职业特性"] = d.get("职业特性", "")
            dict_in["imageUrl"] = ""
            dict_out["profession"].append(dict_in)
        elif type_ == "种族":
            if name_ not in dict_out["customFieldDefinitions"]["ancestries"]:
                dict_out["customFieldDefinitions"]["ancestries"].append(name_)
            intro_lines = []
            features = []
            for raw_line in d.get("描述", "").replace(":", "：").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if "：" in line:
                    feature_name, effect = line.split("：", 1)
                    features.append([feature_name.strip(), effect.strip()])
                elif features:
                    features[-1][1] += "\n" + line
                else:
                    intro_lines.append(line)

            if len(features) != 2:
                raise ValueError(
                    f"种族 {name_} 的描述中应有两项特性，实际找到 {len(features)} 项"
                )

            intro = d.get("简介") or "\n".join(intro_lines) or "无"
            for category, (feature_name, effect) in enumerate(features, start=1):
                dict_in = {
                    "id": gen_uuid(),
                    "名称": feature_name,
                    "种族": name_,
                    "简介": intro,
                    "效果": effect,
                    "类别": category,
                    "imageUrl": "",
                }
                dict_out["ancestry"].append(dict_in)
        elif type_ == "社群":
            if name_ not in dict_out["customFieldDefinitions"]["communities"]:
                dict_out["customFieldDefinitions"]["communities"].append(name_)
            feature = d.get("描述", "").replace(":", "：")
            f_name, f_desc = feature.split("：", 1) if "：" in feature else (feature, "")
            dict_in["特性"] = f_name
            dict_in["简介"] = d.get("简介") or d.get("描述") or "N/A"
            dict_in["描述"] = f_desc
            dict_in["imageUrl"] = ""
            dict_out["community"].append(dict_in)
        elif type_ == "子职":
            dict_in["描述"] = d.get("描述", "")
            dict_in["主职"] = d.get("主职", "")
            dict_in["子职业"] = name_.split("-")[0] if "-" in name_ else name_
            dict_in["等级"] = d.get("等级", "").replace("基础","基石").replace("进阶","专精").replace("精通","大师")
            cast = d.get("施法属性", "")
            dict_in["施法"] = cast if cast else "不可施法"
            dict_in["imageUrl"] = ""
            dict_out["subclass"].append(dict_in)
        elif type_ == "领域卡":
            domain = d.get("领域", "")
            if domain not in dict_out["customFieldDefinitions"]["domains"]:
                dict_out["customFieldDefinitions"]["domains"].append(domain)
            dict_in["领域"] = domain
            dict_in["等级"] = int(d.get("等级", ""))
            dict_in["属性"] = d.get("属性", "")
            recall = d.get("回想", "")
            dict_in["回想"] = int(recall) if str(recall).isdigit() else recall
            dict_in["描述"] = d.get("描述", "")
            dict_in["imageUrl"] = ""
            dict_out["domain"].append(dict_in)
        else:
            if type_ not in dict_out["customFieldDefinitions"]["variants"]:
                dict_out["customFieldDefinitions"]["variants"].append(type_)
            info = d.get("简略信息", "")
            attr_parts = info.split("/") if info else []
            feat = d.get("特性", "") or d.get("描述", "")
            d["效果"] = feat if isinstance(feat, str) and feat else "无"
            d["简略信息"] = {f"item{i}": attr_parts[i] for i in range(len(attr_parts))}
            dict_in.update(d)
            dict_out["variant"].append(dict_in)            
    return dict_out

def work_rrr(data: List[Any]) -> Any:
    dict_out = []
    race_dict = {}
    for dat in data:
        for key in ["profession", "ancestry", "community", "subclass", "domain", "variant"]:
            da = dat.get(key, None)
            if da:
                if isinstance(da, dict):
                    da = [da]
                for d in da:                    
                    dict_in = {}
                    if key == "profession":
                        dict_in["名称"] = d.get("名称", "")
                        dict_in["原名"] = d.get("id", "")
                        dict_in["类型"] = "主职"
                        dict_in["领域"] = d.get("领域1", "") + "+" + d.get("领域2", "")
                        dict_in["初始闪避值"] = d.get("起始闪避", "")
                        dict_in["初始生命点"] = d.get("起始生命", "")
                        dict_in["希望特性"] = d.get("希望特性", "")
                        dict_in["职业特性"] = d.get("职业特性", "")
                        dict_in["背景问题"] = d.get("背景问题", [])
                        dict_in["关系问题"] = d.get("关系问题", [])
                        dict_in["简介"] = d.get("简介", "")
                    elif key == "ancestry":
                        race_name = d.get("种族", "")
                        if race_dict.get(race_name, False):
                            race_dict[race_name]["描述"] = race_dict[race_name]["描述"] + "\n" + d.get("名称", "") + "：" + d.get("效果", "")
                        else:
                            r = {}
                            r["名称"] = race_name
                            r["原名"] = ""
                            r["类型"] = "种族"
                            r["简介"] = d.get("简介", "")
                            r["描述"] = d.get("名称", "") + "：" + d.get("效果", "")
                            race_dict[race_name] = r
                        continue
                    elif key == "community":
                        dict_in["名称"] = d.get("名称", "")
                        dict_in["原名"] = d.get("id", "")
                        dict_in["类型"] = "社群"
                        dict_in["简介"] = d.get("简介", "")
                        dict_in["性格"] = ""
                        dict_in["描述"] = d.get("特性", "") + "：" + d.get("描述", "")
                    elif key == "subclass":
                        lv = d.get("等级", "").replace("基石","基础").replace("专精","进阶").replace("大师","精通")
                        dict_in["名称"] = d.get("子职业", "") + "-" + lv
                        dict_in["原名"] = ""
                        dict_in["类型"] = "子职"
                        dict_in["主职"] = d.get("主职", "")
                        dict_in["等级"] = lv
                        dict_in["施法属性"] = d.get("施法", "")
                        dict_in["描述"] = d.get("描述", "")
                    elif key == "domain":
                        dict_in["名称"] = d.get("名称", "")
                        dict_in["原名"] = d.get("id", "")
                        dict_in["类型"] = "领域卡"
                        dict_in["领域"] = d.get("领域", "")
                        dict_in["等级"] = str(d.get("等级", ""))
                        dict_in["属性"] = d.get("属性", "")
                        dict_in["回想"] = str(d.get("回想", ""))
                        dict_in["描述"] = d.get("描述", "")
                    elif key == "variant":
                        d.pop("id", None)
                        d.pop("imageUrl", None)
                        attr = ""
                        for k,v in d.get("简略信息", "").items():
                            if v:
                                attr = attr + f"{v}/"
                        d["简略信息"] = attr[:-1] if attr else ""
                        for k,v in d.items():
                            if v:
                                dict_in[k] = v
                    dict_out.append(dict_in)

    for _,r in race_dict.items():
        dict_out.append(r)

    return dict_out

def work_function(data: List[Any], mode: str, filepath: str = "") -> Any:
    """
    工作函数 - 用户应自定义此函数。
    默认实现仅打印数据大小和模式，并返回原数据。
    """
    print(f"工作函数被调用，模式={mode}，数据条数={len(data)}")
    if mode == 'rrr':
        return work_rrr(data)
    elif mode == 'zzz':
        return work_zzz(data, filepath)
    raise ValueError(f"未知模式: {mode}")

def main():
    parser = argparse.ArgumentParser(description="处理JSON文件或文件夹，合并数据并应用工作函数。")
    parser.add_argument('input', help='JSON文件或包含JSON文件的文件夹路径')
    group = parser.add_mutually_exclusive_group(required=False)  # 改为可选，因为.dhcb文件固定模式
    group.add_argument('--zzz', action='store_true', help='使用zzz模式')
    group.add_argument('--rrr', action='store_true', help='使用rrr模式')
    args = parser.parse_args()

    # 检查输入文件扩展名
    input_lower = args.input.lower()
    is_dhcb = input_lower.endswith('.dhcb') or input_lower.endswith('.zip')
    
    # 确定模式
    if is_dhcb:
        # .dhcb文件固定使用rrr模式
        mode = 'rrr'
        if args.zzz or args.rrr:
            print(f"警告: 输入为.dhcb文件，已固定使用rrr模式，忽略命令行模式参数", file=sys.stderr)
    else:
        # 非.dhcb文件需要明确指定模式
        if not args.zzz and not args.rrr:
            parser.error("必须指定 --zzz 或 --rrr 参数（.dhcb文件除外）")
        mode = 'zzz' if args.zzz else 'rrr'
    
    to_mode = 'zzz' if mode == 'rrr' else 'rrr'


    data = collect_data(args.input)
    result = work_function(data, mode, args.input)
    json_output_path = os.path.splitext(args.input)[0] + f"_{to_mode}.json"
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"结果已保存到 {json_output_path}")


if __name__ == '__main__':
    main()
