"""测试配置文件和模块导入"""

import sys
import os
from typing import Dict, Any
import yaml


def test_config_loading():
    """测试配置文件加载"""
    print("=" * 60)
    print("测试配置文件加载")
    print("=" * 60)
    
    # 自动查找配置文件
    config_path = None
    possible_paths = [
        "secrets/config.yaml",
        "config.yaml",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            config_path = path
            break
    
    if config_path is None:
        print("✗ 找不到配置文件")
        print("  请将配置文件放在以下位置之一：")
        print("    - secrets/config.yaml (推荐)")
        print("    - config.yaml")
        return False
    
    print(f"[*] 使用配置文件: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        # 验证必要字段
        required_keys = ['auth', 'aligned_metrics', 'frameworks', 'target']
        missing_keys = [k for k in required_keys if k not in config]
        
        if missing_keys:
            print(f"✗ 配置文件缺少必要字段: {missing_keys}")
            return False
        
        print("✓ 配置文件加载成功")
        
        # 显示对齐指标
        print(f"  - 对齐指标数量: {len(config['aligned_metrics'])}")
        
        # 显示框架配置
        frameworks = config['frameworks']
        enabled_frameworks = [name for name, fw in frameworks.items() if fw.get('enabled', False)]
        print(f"  - 启用的框架: {', '.join(enabled_frameworks)}")
        
        for fw_name, fw_config in frameworks.items():
            if not fw_config.get('enabled', False):
                continue
            
            print(f"\n  [{fw_name.upper()}]:")
            print(f"    平台: {fw_config['platform']}")
            if fw_config['platform'] == 'swanlab':
                print(f"    实验ID: {fw_config['exp_id']}")
            elif fw_config['platform'] == 'wandb':
                print(f"    Run路径: {fw_config['run_path']}")
            
            mapping = fw_config.get('mapping')
            if mapping is None:
                print(f"    映射规则: 未配置（直接使用对齐指标）")
            else:
                print(f"    映射规则: {len(mapping)} 条")
            
            print(f"    目标实验: {fw_config['target_exp_name']}")
        
        print(f"\n  - 目标项目: {config['target']['project']}")
        
        return True
        
    except FileNotFoundError:
        print("✗ 找不到配置文件")
        print("  请复制 config.yaml.example 并移动到 secrets/config.yaml")
        print("  或者直接放在项目根目录下的 config.yaml")
        return False
    except yaml.YAMLError as e:
        print(f"✗ 配置文件格式错误: {e}")
        return False


def test_module_imports():
    """测试模块导入"""
    print("\n" + "=" * 60)
    print("测试模块导入")
    print("=" * 60)
    
    try:
        from src.exporter import DataExporter
        print("✓ DataExporter 导入成功")
        
        from src.uploader import SwanLabUploader
        print("✓ SwanLabUploader 导入成功")
        
        return True
        
    except ImportError as e:
        print(f"✗ 模块导入失败: {e}")
        return False


def test_data_directory():
    """测试数据目录"""
    print("\n" + "=" * 60)
    print("测试数据目录")
    print("=" * 60)
    
    import os
    
    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"✓ 创建数据目录: {data_dir}")
    else:
        print(f"✓ 数据目录已存在: {data_dir}")
    
    return True


def main():
    """运行所有测试"""
    print("\n多框架指标对齐同步工具 - 环境测试\n")
    
    tests = [
        ("配置文件加载", test_config_loading),
        ("模块导入", test_module_imports),
        ("数据目录", test_data_directory),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ 测试 '{name}' 异常: {e}")
            results.append((name, False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status} - {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n✓ 所有测试通过！可以运行 python main.py 开始同步数据")
        return 0
    else:
        print("\n✗ 部分测试失败，请检查配置和依赖")
        return 1


if __name__ == "__main__":
    sys.exit(main())