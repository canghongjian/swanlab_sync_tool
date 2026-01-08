"""SwanLab 同步工具主程序"""

import sys
import os
from typing import Dict, Any, Optional
import yaml
import pandas as pd
from src.exporter import DataExporter
from src.uploader import SwanLabUploader


def load_config(path: str = None) -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        path: 配置文件路径，如果为 None 则自动查找
        
    Returns:
        配置字典
        
    Raises:
        SystemExit: 当配置文件不存在或格式错误时
    """
    # 自动查找配置文件
    if path is None:
        # 优先从 secrets 目录查找
        possible_paths = [
            "secrets/config.yaml",
            "config.yaml",
        ]
        for possible_path in possible_paths:
            if os.path.exists(possible_path):
                path = possible_path
                break
        else:
            print("错误: 找不到配置文件")
            print("请将配置文件放在以下位置之一：")
            print("  - secrets/config.yaml (推荐)")
            print("  - config.yaml")
            sys.exit(1)
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        # 验证必要的配置项
        required_keys = ['auth', 'aligned_metrics', 'frameworks', 'target']
        for key in required_keys:
            if key not in config:
                print(f"错误: 配置文件缺少必要字段 '{key}'")
                sys.exit(1)
        
        # 验证至少有一个框架启用
        enabled_frameworks = [
            name for name, fw in config['frameworks'].items()
            if fw.get('enabled', False)
        ]
        if not enabled_frameworks:
            print("错误: 没有启用的框架，请在 frameworks 中至少启用一个")
            sys.exit(1)
        
        return config
        
    except FileNotFoundError:
        print("错误: 找不到 config.yaml 文件")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"错误: 配置文件格式错误 - {e}")
        sys.exit(1)


def main() -> None:
    """主函数：协调整个数据同步流程"""
    print("=" * 60)
    print("多框架指标对齐同步工具")
    print("=" * 60)
    
    # 1. 加载配置
    try:
        cfg = load_config()
        print(f"[✓] 配置加载完成")
        print(f"    对齐指标数量: {len(cfg['aligned_metrics'])}")
        print(f"    启用的框架: {', '.join([name for name, fw in cfg['frameworks'].items() if fw.get('enabled', False)])}")
    except Exception as e:
        print(f"[✗] 配置加载失败: {e}")
        sys.exit(1)
    
    print("-" * 60)
    
    # 2. 导出数据
    print("\n[步骤 1/2] 导出数据")
    print("-" * 60)
    
    exporter = DataExporter(cfg)
    framework_data = {}
    
    # 遍历所有框架，导出启用的数据
    for fw_name, fw_config in cfg['frameworks'].items():
        if not fw_config.get('enabled', False):
            continue
        
        print(f"\n[{fw_name.upper()}] 开始导出...")
        
        if fw_config['platform'] == 'swanlab':
            df = exporter.export_swanlab(fw_config)
        elif fw_config['platform'] == 'wandb':
            df = exporter.export_wandb(fw_config)
        else:
            print(f"[✗] {fw_name} 不支持的平台: {fw_config['platform']}")
            continue
        
        if df is not None:
            framework_data[fw_name] = df
    
    # 检查是否有数据需要上传
    if not framework_data:
        print("\n[✗] 没有成功导出任何数据，程序终止")
        sys.exit(1)
    
    print(f"\n[✓] 成功导出 {len(framework_data)} 个框架的数据")
    
    print("-" * 60)
    
    # 3. 上传数据
    print("\n[步骤 2/2] 上传数据")
    print("-" * 60)
    
    uploader = SwanLabUploader(cfg)
    
    # 遍历所有框架，上传数据
    for fw_name, df in framework_data.items():
        fw_config = cfg['frameworks'][fw_name]
        
        print(f"\n[{fw_name.upper()}] 开始上传...")
        try:
            uploader.sync_framework_data(fw_name, df, fw_config)
        except Exception as e:
            print(f"[✗] {fw_name} 上传失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 4. 打印对齐情况总结
    print("\n" + "=" * 60)
    print("[对齐情况总结]")
    print("=" * 60)
    
    print(f"\n对齐指标总数: {len(cfg['aligned_metrics'])}")
    print(f"\n各框架对齐情况:")
    
    for fw_name, fw_config in cfg['frameworks'].items():
        if not fw_config.get('enabled', False):
            continue
        
        print(f"\n  [{fw_name.upper()}]")
        print(f"    平台: {fw_config['platform']}")
        print(f"    目标实验: {fw_config['target_exp_name']}")
        
        # 读取导出的数据
        if os.path.exists(fw_config['output_file']):
            df = pd.read_csv(fw_config['output_file'])
            print(f"    数据行数: {len(df)}")
            
            if 'step' in df.columns:
                print(f"    Step 范围: {int(df['step'].min())} - {int(df['step'].max())}")
            
            # 检查对齐指标
            mapping = fw_config.get('mapping')
            if mapping:
                # 有映射：检查映射后的目标指标
                available_metrics = set()
                for src_key, target_key in mapping.items():
                    if src_key in df.columns:
                        available_metrics.add(target_key)
            else:
                # 无映射：直接使用对齐指标
                available_metrics = set()
                for metric in cfg['aligned_metrics']:
                    if metric in df.columns:
                        available_metrics.add(metric)
            
            missing_metrics = set(cfg['aligned_metrics']) - available_metrics
            
            print(f"    对齐指标: {len(available_metrics)}/{len(cfg['aligned_metrics'])}")
            
            if missing_metrics:
                print(f"    缺失指标 ({len(missing_metrics)}):")
                for metric in sorted(missing_metrics):
                    print(f"      - {metric}")
            else:
                print(f"    状态: ✓ 所有对齐指标都存在")
        else:
            print(f"    状态: ✗ 数据文件不存在")
    
    # 5. 完成
    print("\n" + "=" * 60)
    print("[✓] 所有任务执行完毕")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] 用户中断程序")
        sys.exit(0)
    except Exception as e:
        print(f"\n[✗] 程序异常退出: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)