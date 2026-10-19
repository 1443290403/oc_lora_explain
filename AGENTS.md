# OC LoRA 项目操作指引

本仓库维护奈卡尔 Illustrious/SDXL LoRA 的辅助工具、配置和评估流程。它不是 Web 应用，也不包含训练素材、底模或 LoRA 权重。

## 接手顺序

1. 先看 `docs/PROJECT_STATUS.md`，了解当前基线、未解决问题和下一步。
2. 按任务读取 `docs/SETUP.md`、`DATASET.md`、`TRAINING.md` 或 `EVALUATION.md`。
3. 新设备用 `docs/MIGRATION.md`，云端辅助开发用 `docs/CLOUD.md`。
4. 以实际文件、Git 状态和命令结果核实情况，不把旧聊天记录当作当前运行状态。

## 环境和入口

- 辅助工具固定 Python 3.12；Windows 用 `scripts/setup.ps1`，Linux 用 `bash scripts/setup.sh`。统一实现是 `scripts/bootstrap.py`，创建/复用 `.venv`，不覆盖 `configs/local.toml`。
- 可以用 Anaconda 的 Python 3.12 启动安装器；也可以按 `environment.yml` 单独创建 Conda 辅助环境。不要把辅助依赖装进用户的训练或 ComfyUI 环境。
- Python 命令应使用正确环境的解释器；本地 PowerShell 输出中文时加 `-X utf8`。
- `python scripts/doctor.py --profile helper` 不需要 GPU、数据、模型或服务。云端没有这些资源是正常情况。
- 训练检查使用 `--profile training --training-python <OneTrainer的Python>`；连接检查使用 `--profile comfyui`。自检不是完整训练或显存验证。
- 路径以仓库根为基准；本机设置放在被忽略的 `configs/local.toml` 或 `OC_*` 环境变量中。显式指定但不存在的配置必须报错。

## 数据与实验约束

- 触发词 `naikaer_oc`。固定设定见 `docs/DATASET.md`，左右指角色自身；不要水平翻转不对称人设。
- 保留作者参考、原始图片和人工标签。审查只读；修正图或标签另存并保留来源。
- 曝光基线去掉所有画师词，不暗中加入画风或曝光补偿。控制种子和采样参数，记录更改。
- V6 从底模新建，不能把训练入口自动改成接续 V4/V5。新一轮训练以用户当前任务为依据，不因修改工具自动开始训练。
- 使用新的运行目录和输出文件名，禁止覆盖已有模型、训练状态或评估结果。
- 评估 `--resume` 只接受有效图参数和图片摘要都一致的完成项；旧格式或参数改变时使用新目录。模型同名替换后也必须新建评估目录。

## 进程和资源

- 修改文档、安装辅助依赖、CPU 测试不需要启动 GPU 服务或训练。
- 使用已有 ComfyUI 时先检查队列；不清队列、不打断用户任务。
- 只关闭本次调试自行启动且能确认归属的进程；结束时主动清理它们。保留用户原先启动的服务。释放显存不等于关闭进程。
- 训练/生成任务需记录状态、输出和失败原因，不能把“配置已生成”报告为“训练成功”。

## 验证和提交

```text
python -m unittest discover -s tests -v
python scripts/doctor.py --profile helper
git add <本次明确修改的可发布文件>
python scripts/check_publish.py
git diff --cached --check
git diff --cached --stat
```

GPU 改动应在相应环境额外验证；CPU 检查通过不代表 GPU 训练已验证。测试用临时合成素材，不能依赖私人训练集。

发布允许范围由 `.gitignore` 和 `scripts/check_publish.py` 共同维护。新增顶层文件、目录或扩展名时同步调整两者，不能强制添加被排除的数据。不得上传图片、逐图标签、权重、缓存、运行历史、认证信息或机器绝对路径。

不要更改全局 Git 身份。推送前核对远端、分支和当前账号，保留用户指定账号。重大实验结论更新 `docs/PROJECT_STATUS.md` 和相应专题文档；只记录可核实事实和局限，不复制聊天全文。
