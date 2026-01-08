"""数据导出模块：从 SwanLab 和 WandB 导出实验数据"""

import os
from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd
import wandb
from swanlab.api.main import OpenApi


class DataExporter:
    """数据导出器：负责从 SwanLab 和 WandB 拉取实验数据"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化导出器
        
        Args:
            config: 配置字典，包含认证信息和框架设置
        """
        self.cfg = config
        # 确保数据目录存在
        os.makedirs("data", exist_ok=True)

    def export_swanlab(self, fw_config: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        从 SwanLab 导出实验数据
        
        Args:
            fw_config: 框架配置字典
            
        Returns:
            包含实验数据的 DataFrame，如果导出失败则返回 None
        """
        # 检查缓存
        if os.path.exists(fw_config['output_file']):
            print(f"[*] 检测到本地缓存文件，跳过下载")
            df = pd.read_csv(fw_config['output_file'])
            return df

        print(f"[-] 正在从云端下载实验: {fw_config['exp_id']}")
        
        try:
            # 初始化 API
            api = OpenApi(api_key=self.cfg['auth']['swanlab_api_key'])
            
            # 获取指标数据
            mapping = fw_config.get('mapping')
            if mapping:
                # 从映射中提取源指标
                source_metrics = list(mapping.keys())
            else:
                # 没有映射，直接使用对齐指标
                source_metrics = self.cfg['aligned_metrics']
                print(f"[*] 未配置映射规则，将导出对齐指标")
            
            response = api.experiment.get_metrics(
                exp_id=fw_config['exp_id'],
                keys=source_metrics
            )
            
            if response.errmsg:
                raise Exception(f"API 错误: {response.errmsg}")
            
            df = response.data
            
            # 重置索引，将 step 作为列
            df = df.reset_index()
            df = df.rename(columns={'index': 'step'})
            
            # 保存到本地
            df.to_csv(fw_config['output_file'], index=False)
            print(f"[+] 导出成功，共 {len(df)} 行数据")
            return df
            
        except Exception as e:
            print(f"[!] 导出失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def export_wandb(self, fw_config: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        从 WandB 导出实验数据，参考 zhangji_parsing.py 的处理方式
        按 step 类型分组处理，逐个指标获取数据，并创建完整的 step 索引
        
        Args:
            fw_config: 框架配置字典
            
        Returns:
            包含实验数据的 DataFrame，如果导出失败则返回 None
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from collections import defaultdict
        
        # 检查缓存
        if os.path.exists(fw_config['output_file']):
            print(f"[*] 检测到本地缓存文件，跳过下载")
            return pd.read_csv(fw_config['output_file'])

        print(f"[-] 正在从云端下载 Run: {fw_config['run_path']}")
        
        try:
            # 获取 Run 数据（使用本地已登录的凭证）
            api = wandb.Api()
            run = api.run(fw_config['run_path'])
            
            # 定义 step 类型分组
            keys_mapping = {
                "train/step": ["train/"],
                "rollout/step": ["rollout/", "multi_turn/", "passrate/", "perf/"],
                "eval/step": ["eval/"],
            }
            
            # 获取所有指标键
            metric_keys = []
            for key in run.history_keys['keys'].keys():
                if key.startswith('system') or key == '_timestamp':
                    continue
                metric_keys.append(key)
            
            # 分组指标
            grouped_metrics = defaultdict(list)
            for k, v in keys_mapping.items():
                for metrics_key in metric_keys:
                    if metrics_key == k:
                        grouped_metrics[k].append(metrics_key)
                        continue
                    for v_ in v:
                        if metrics_key.startswith(v_):
                            grouped_metrics[k].append(metrics_key)
            
            print(f"[*] 指标分组:")
            for step_key, metrics in grouped_metrics.items():
                print(f"  {step_key}: {len(metrics)} 个指标")
            
            # 逐个获取指标数据（避免 wandb 合并时丢失数据）
            def fetch_single_metric(key: str) -> Optional[pd.DataFrame]:
                try:
                    res = pd.DataFrame(run.scan_history(keys=[key, '_step']))
                    return res
                except Exception as e:
                    print(f"Error fetching {key}: {e}")
                    return None
            
            def fetch_one_group(group_metrics: List[str]) -> Dict[str, pd.DataFrame]:
                dfs = {}
                with ThreadPoolExecutor(max_workers=10) as executor:
                    future_to_key = {
                        executor.submit(fetch_single_metric, metrics): metrics
                        for metrics in group_metrics
                    }
                    
                    for future in as_completed(future_to_key):
                        key = future_to_key[future]
                        try:
                            df = future.result()
                            if df is not None:
                                dfs[key] = df
                        except Exception as e:
                            print(f"Failed to process {key}: {e}")
                            raise e
                return dfs
            
            def agg_one_df(new_key: str, main_key: str, dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
                # 为每个 (_step, main_key) 组合，合并所有指标
                # 创建从 0 到 max(_step) 的完整索引
                if main_key not in dfs or dfs[main_key].empty:
                    return pd.DataFrame()
                
                max_steps = int(dfs[main_key]['_step'].max())
                master_df = pd.DataFrame(index=np.arange(max_steps + 1))
                master_df.index.name = '_step'
                cleaned_dfs = []
                
                for key, df in dfs.items():
                    df = df[(df['_step'] >= 0) & (df['_step'] <= max_steps)]
                    df = df.drop_duplicates(subset='_step', keep='last')
                    df = df.set_index('_step')
                    cleaned_dfs.append(df)
                
                final_df = master_df.join(cleaned_dfs, how='left')
                final_df.reset_index(inplace=True)
                final_df[new_key] = final_df[main_key].bfill()
                
                def collect_non_null(x):
                    valid_values = x.dropna().tolist()
                    if len(valid_values) == 1:
                        return valid_values[0]
                    if not valid_values:
                        return None
                    return valid_values
                
                agg_dict = {
                    col: collect_non_null
                    for col in final_df.columns
                    if col not in [new_key, main_key, '_step']
                }
                
                result = final_df.groupby(new_key).agg(agg_dict)
                return result
            
            # 处理每个组
            result_dfs = {}
            
            for metric_step, group_metrics in grouped_metrics.items():
                print(f"[*] 处理 {metric_step} 组...")
                
                # 获取该组所有指标的数据
                dfs = fetch_one_group(group_metrics)
                
                # 聚合数据
                new_key = f"{metric_step.split('/')[0]}_id"
                df_group = agg_one_df(new_key, metric_step, dfs)
                
                if not df_group.empty:
                    # 添加 step 列
                    df_group = df_group.reset_index()
                    df_group['step'] = df_group[new_key]
                    result_dfs[metric_step] = df_group
                    print(f"[+] {metric_step} 组: {len(df_group)} 行")
            
            # 合并所有组（以 train/step 为主）
            if 'train/step' in result_dfs:
                df_final = result_dfs['train/step']
                
                # 合并其他组的数据
                for step_key in ['rollout/step', 'eval/step']:
                    if step_key in result_dfs:
                        df_other = result_dfs[step_key]
                        # 按 step 合并
                        df_final = pd.merge(
                            df_final,
                            df_other,
                            on='step',
                            how='outer',
                            suffixes=('', f'_{step_key.split("/")[0]}')
                        )
                
                # 去重列（移除重复的列）
                df_final = df_final.loc[:, ~df_final.columns.duplicated()]
                
                print(f"[+] 合并后数据: {len(df_final)} 行")
            else:
                # 如果没有 train/step，使用第一个可用的组
                df_final = list(result_dfs.values())[0] if result_dfs else pd.DataFrame()
            
            # 保存到本地
            df_final.to_csv(fw_config['output_file'], index=False)
            return df_final
            
        except Exception as e:
            print(f"[!] 导出失败: {str(e)}")
            print(f"    提示: 请确保已使用 'wandb login' 登录")
            import traceback
            traceback.print_exc()
            return None