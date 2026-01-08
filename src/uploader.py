"""数据上传模块：将导出的数据上传到 SwanLab"""

from typing import Optional, Dict, List, Any, Set
import pandas as pd
import swanlab


class SwanLabUploader:
    """SwanLab 上传器：负责将数据上传到 SwanLab 项目"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化上传器
        
        Args:
            config: 配置字典，包含目标项目设置
        """
        self.cfg = config

    def _find_step_column(self, df: pd.DataFrame, preferred: str = 'step') -> str:
        """
        查找 DataFrame 中的 step 列
        
        Args:
            df: 数据 DataFrame
            preferred: 优先使用的列名
            
        Returns:
            找到的 step 列名
        """
        if preferred in df.columns:
            return preferred
        
        # 尝试常见的 step 列名
        candidates = ['_step', 'global_step', 'Step', 'step']
        for col in candidates:
            if col in df.columns:
                return col
        
        # 如果都没找到，使用索引
        print(f"[!] 警告: 未找到 Step 列，使用索引代替")
        return 'index'

    def _check_metrics_alignment(
        self,
        df: pd.DataFrame,
        aligned_metrics: Set[str],
        fw_name: str,
        metric_mapping: Dict[str, str]
    ) -> None:
        """
        检查指标对齐情况
        
        Args:
            df: 数据 DataFrame
            aligned_metrics: 对齐指标集合
            fw_name: 框架名称
            metric_mapping: 映射规则
        """
        if not aligned_metrics:
            return
        
        # 获取数据中实际存在的指标
        available_metrics = set(df.columns)
        
        # 找出哪些对齐指标可以通过映射获得
        available_aligned = set()
        for src_key, target_key in metric_mapping.items():
            if src_key in available_metrics:
                available_aligned.add(target_key)
        
        # 找出缺失的对齐指标
        missing_metrics = aligned_metrics - available_aligned
        
        if missing_metrics:
            print(f"[!] {fw_name} 指标对齐检查:")
            print(f"    缺失 {len(missing_metrics)} 个对齐指标:")
            for metric in sorted(missing_metrics):
                print(f"      - {metric}")
            print(f"    可用对齐指标: {len(available_aligned)}/{len(aligned_metrics)}")
        else:
            print(f"[✓] {fw_name} 指标对齐检查: 所有对齐指标都存在")

    def _upload_data(
        self,
        df: pd.DataFrame,
        exp_name: str,
        step_col: str,
        metric_mapping: Dict[str, str],
        aligned_metrics: Set[str]
    ) -> int:
        """
        上传数据到 SwanLab
        
        Args:
            df: 要上传的数据
            exp_name: 实验名称
            step_col: step 列名
            metric_mapping: 指标映射表（源指标 -> 对齐指标）
            aligned_metrics: 对齐指标集合
            
        Returns:
            成功上传的 step 数量
        """
        print(f"[-] 正在上传实验: {exp_name}")
        
        # 检查指标对齐
        self._check_metrics_alignment(df, aligned_metrics, exp_name, metric_mapping)
        
        # 初始化 SwanLab
        swanlab.init(
            project=self.cfg['target']['project'],
            experiment_name=exp_name,
            config={
                "source": "multi_framework_sync",
                "original_rows": len(df),
                "aligned_metrics_count": len(aligned_metrics)
            }
        )

        # 处理 step 列
        if step_col == 'index' or step_col not in df.columns:
            # 使用索引作为 step
            df = df.copy()
            df['step'] = range(len(df))
            step_col = 'step'
        
        # 按 step 排序
        df = df.sort_values(by=step_col).reset_index(drop=True)

        # 上传数据
        uploaded_count = 0
        for _, row in df.iterrows():
            step_val = row[step_col]
            if pd.isna(step_val):
                continue
            
            payload = {}
            
            # 使用映射表转换指标
            for src_key, target_key in metric_mapping.items():
                if src_key in row and pd.notna(row[src_key]):
                    payload[target_key] = row[src_key]
            
            # 上传有效数据
            if payload:
                try:
                    swanlab.log(payload, step=int(step_val))
                    uploaded_count += 1
                except Exception as e:
                    print(f"[!] 上传 step {step_val} 时出错: {e}")

        # 结束上传
        swanlab.finish()
        print(f"[+] 实验 {exp_name} 完成，共上传 {uploaded_count} 个 step")
        
        return uploaded_count

    def sync_framework_data(
        self,
        fw_name: str,
        df: pd.DataFrame,
        fw_config: Dict[str, Any]
    ) -> None:
        """
        同步框架数据
        
        Args:
            fw_name: 框架名称
            df: 框架导出的数据
            fw_config: 框架配置
        """
        if df is None or df.empty:
            print(f"[*] {fw_name} 数据为空，跳过上传")
            return
        
        # 查找 step 列
        step_col = self._find_step_column(df, preferred='step')
        
        # 获取对齐指标集合
        aligned_metrics = set(self.cfg['aligned_metrics'])
        
        # 获取映射规则
        metric_mapping = fw_config.get('mapping')
        
        # 如果没有映射规则，直接使用对齐指标
        if metric_mapping is None:
            print(f"[*] {fw_name} 未配置映射规则，将直接使用对齐指标")
            # 创建恒等映射（指标名 -> 指标名）
            metric_mapping = {metric: metric for metric in aligned_metrics}
        
        # 上传数据
        self._upload_data(
            df=df,
            exp_name=fw_config['target_exp_name'],
            step_col=step_col,
            metric_mapping=metric_mapping,
            aligned_metrics=aligned_metrics
        )