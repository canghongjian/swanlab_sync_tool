# 多框架指标对齐同步工具

用于从多个训练框架（VERL、ROLL、SLIME）拉取实验数据，按统一的指标名称对齐，并上传到 SwanLab 进行对比分析。

## 功能特性

- ✓ 支持多个框架的数据同步（VERL、ROLL、SLIME）
- ✓ 支持 SwanLab 和 WandB 两种数据源
- ✓ 统一的指标对齐机制
- ✓ 灵活的映射规则配置
- ✓ 本地缓存机制，避免重复下载
- ✓ 自动指标对齐检查
- ✓ 完善的错误处理和日志输出
- ✓ **WandB 智能数据处理**：
  - 按步骤类型分组（train/step、rollout/step、eval/step）
  - 并行获取每个指标数据，避免数据丢失
  - 自动创建完整的 step 索引
  - 智能聚合，保留最后一个非空值

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置文件

复制配置模板并填入实际信息：

```bash
cp config.yaml.example secrets/config.yaml
```

**重要提示**：为了保护敏感信息（如 API Key），配置文件应放在 `secrets/` 目录下，该目录已被 `.gitignore` 忽略，不会被提交到 Git 仓库。

编辑 `secrets/config.yaml` 文件，配置以下内容：

- **认证信息**：设置 SwanLab API Key（WandB 使用本地已登录凭证）
- **对齐指标**：定义所有框架最终都要对齐到的统一指标名称
- **框架配置**：为每个框架配置数据源和映射规则
- **目标设置**：设置上传到的 SwanLab 项目名称

### 3. 运行程序

```bash
python main.py
```

### 4. 测试环境（可选）

```bash
python test_config.py
```

## 配置说明

### 对齐指标定义

这是所有框架最终都要对齐到的统一指标名称：

```yaml
aligned_metrics:
  - "algorithm/reward"
  - "algorithm/entropy"
  - "algorithm/policy_loss"
  # ... 更多指标
```

### 框架配置

每个框架都需要配置以下信息：

```yaml
frameworks:
  verl:
    enabled: true                    # 是否启用
    platform: "swanlab"             # 数据源平台
    exp_id: "YOUR_EXP_ID"           # SwanLab 实验ID
    output_file: "data/verl.csv"    # 缓存文件路径
    target_exp_name: "verl_experiment"  # 目标实验名称
    mapping:                         # 映射规则
      "源指标名": "对齐指标名"
      # ... 更多映射
```

**支持的框架**：
- **VERL**: 使用 SwanLab
- **ROLL**: 使用 SwanLab
- **SLIME**: 使用 WandB（支持自动计算 throughput 指标）

**映射规则**：
- 格式：`"框架的指标名": "对齐指标名"`
- 如果框架的指标名称已经是对齐指标名称，可以设置为 `null`
- 所有框架的映射规则最终都会指向 `aligned_metrics` 中定义的统一指标名

**示例**：
```yaml
# 需要映射的情况
mapping:
  "deepinsight_algorithm/reward": "algorithm/reward"

# 不需要映射的情况（指标名称已经是对齐指标）
mapping: null
```

### 目标设置

```yaml
target:
  project: "framework-comparison"  # 目标项目名称
```

## 工作流程

1. **加载配置**：读取并验证 `config.yaml` 配置文件
2. **导出数据**：
   - 遍历所有启用的框架
   - 从对应平台（SwanLab 或 WandB）导出数据
   - 数据自动缓存到 `data/` 目录，避免重复下载
3. **上传数据**：
   - **指标对齐检查**：检查每个框架的对齐指标是否存在
   - 按映射规则转换指标名称
   - 上传到 SwanLab 目标项目
4. **完成**：在 SwanLab 中查看对比结果

## 配置示例

### 示例 1：只同步 VERL 和 ROLL

```yaml
frameworks:
  verl:
    enabled: true
    # ... 配置
  
  roll:
    enabled: true
    # ... 配置
  
  slime:
    enabled: false  # 禁用
    # ... 配置
```

### 示例 2：只同步 SLIME

```yaml
frameworks:
  verl:
    enabled: false  # 禁用
  
  roll:
    enabled: false  # 禁用
  
  slime:
    enabled: true   # 只启用 SLIME
    # ... 配置
```

## 指标对齐检查

系统会自动检查每个框架的对齐指标是否存在：

**所有指标都存在时**：
```
[✓] VERL 指标对齐检查: 所有对齐指标都存在
```

**有指标缺失时**：
```
[!] ROLL 指标对齐检查:
    缺失 2 个对齐指标:
      - algorithm/grad_norm
      - infra/throughput
```

## 注意事项

- **认证信息**：
  - SwanLab API Key：用于上传数据到 SwanLab
  - WandB：使用本地已登录凭证，请先运行 `wandb login`
- **配置文件安全**：
  - 配置文件应放在 `secrets/config.yaml`，该目录已被 `.gitignore` 忽略
  - 切勿将包含 API Key 的配置文件提交到 Git 仓库
  - `config.yaml.example` 是配置模板，可以安全提交
- 数据会缓存到 `data/` 目录，如需重新下载请删除对应的 CSV 文件
- SwanLab 的 `exp_id` 可以从实验网页 URL 中获取
- WandB 的 `run_path` 格式为：`entity/project/run_id`
- 映射规则的源指标名必须在原始数据中存在
- 上传的数据会创建新的实验，不会覆盖现有数据
- **WandB 数据处理**：
  - 系统会自动按 `train/step`、`rollout/step`、`eval/step` 分组处理指标
  - 使用并行获取策略，避免 WandB API 合并时丢失数据
  - 自动创建连续的 step 索引，确保数据完整性
- **SLIME Throughput 计算**：
  - 需要在配置中指定 `n_gpus` 参数
  - 系统会自动计算 `perf/throughput` 指标
  - 计算公式：`throughput = (actor_train_tok_per_s × actor_train_time) / (step_time × n_gpus)`

## 项目结构

```
swanlab_sync_tool/
├── secrets/                # 敏感信息目录（不提交）
│   └── config.yaml         # 配置文件（包含 API Key）
├── config.yaml.example     # 配置模板
├── main.py                 # 主程序入口
├── test_config.py          # 测试脚本
├── requirements.txt        # 依赖列表
├── README.md               # 项目说明文档
├── .gitignore              # Git 忽略规则
├── data/                   # 数据缓存目录（不提交）
│   ├── verl.csv            # VERL 缓存
│   ├── roll.csv            # ROLL 缓存
│   └── slime.csv           # SLIME 缓存
└── src/
    ├── __init__.py
    ├── exporter.py         # 数据导出模块
    └── uploader.py         # 数据上传模块
```

## 常见问题

**Q: 如何获取 SwanLab 实验ID？**  
A: 打开实验网页，URL 中的 ID 部分即为实验ID，例如：`https://swanlab.cn/@user/project/exp/7s7hg9w5tuwcf7jzvu5rg`

**Q: 如何获取 WandB Run 路径？**  
A: 打开 Run 网页，URL 格式为 `https://wandb.ai/entity/project/runs/run_id`，对应的 run_path 为 `entity/project/run_id`

**Q: 如何清除缓存重新下载数据？**  
A: 删除 `data/` 目录下的对应 CSV 文件即可

**Q: 配置文件应该放在哪里？**  
A: 推荐放在 `secrets/config.yaml`，这样可以防止 API Key 泄漏到 Git 仓库。程序会自动查找配置文件，查找顺序为：`secrets/config.yaml` → `config.yaml`

**Q: 如何保护 API Key 不被提交？**  
A: `secrets/` 目录已在 `.gitignore` 中配置，不会被 Git 跟踪。确保不要将配置文件放在项目根目录，或确保根目录的 `config.yaml` 也在 `.gitignore` 中

**Q: 映射规则如何配置？**  
A: 映射规则的格式是 `"框架的指标名": "对齐指标名"`，确保右侧的指标名在 `aligned_metrics` 中定义

**Q: 如果某个框架缺少某些指标怎么办？**  
A: 系统会自动检测并提示缺失的指标，你可以选择：
1. 检查映射规则是否正确
2. 从配置中移除该指标
3. 确认原始数据中确实没有该指标

## 技术栈

- Python 3.7+
- pandas: 数据处理
- swanlab: SwanLab SDK
- wandb: WandB SDK
- pyyaml: 配置文件解析
- concurrent.futures: 并行数据处理

## WandB 数据处理说明

本工具针对 WandB 的数据特性进行了特殊优化，参考了 `zhangji_parsing.py` 的实现：

### 处理流程

1. **指标分组**：根据 step 类型将指标分为三组
   - `train/step` 组：包含所有 `train/*` 指标
   - `rollout/step` 组：包含 `rollout/*`、`multi_turn/*`、`passrate/*`、`perf/*` 指标
   - `eval/step` 组：包含所有 `eval/*` 指标

2. **并行获取**：使用 `ThreadPoolExecutor` 并行获取每个指标的数据
   - 避免了 WandB API 在合并多个指标时可能丢失数据的问题
   - 参考：https://github.com/wandb/wandb/issues/5391

3. **创建完整索引**：为每个组创建从 0 到 max_step 的连续索引
   - 确保数据的完整性，不会因为 step 不连续而丢失数据

4. **智能聚合**：使用自定义聚合函数处理数据
   - 对于同一个 step，保留最后一个非空值
   - 使用 `bfill()` 填充缺失的 step 值

5. **合并数据**：以 `train/step` 为主，合并其他组的数据
   - 最终输出包含所有指标的统一 DataFrame

6. **SLIME Throughput 计算**：针对 SLIME 框架自动计算 throughput 指标
   - 仅在配置中指定 `n_gpus` 参数且包含必要列时计算
   - 计算公式：`throughput = (actor_train_tok_per_s × actor_train_time) / (step_time × n_gpus)`
   - 需要的列：`perf/actor_train_tok_per_s`、`perf/actor_train_time`、`perf/step_time`

### 输出格式

导出的 WandB 数据包含以下列：
- `step`：统一的 step 列（来自 train/step）
- `train_id`、`rollout_id`、`eval_id`：各组的 step 标识
- 所有原始指标列（按组分类）
- `perf/throughput`：SLIME 框架自动计算的吞吐量指标（仅当配置了 n_gpus 时）

### 示例输出

```
[*] 指标分组:
  train/step: 12 个指标
  rollout/step: 36 个指标
  eval/step: 7 个指标
[*] 处理 train/step 组...
[+] train/step 组: 500 行
[*] 处理 rollout/step 组...
[+] rollout/step 组: 500 行
[*] 处理 eval/step 组...
[+] eval/step 组: 13 行
[*] 计算 throughput 指标 (n_gpus=8)...
[+] throughput 指标计算完成
[+] 合并后数据: 500 行
```