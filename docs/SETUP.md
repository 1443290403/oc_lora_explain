# 环境与路径

新设备的完整步骤见 [MIGRATION](MIGRATION.md)，云端无 GPU 的辅助开发见 [CLOUD](CLOUD.md)。Windows `scripts/setup.ps1`、Linux `bash scripts/setup.sh` 共用 `scripts/bootstrap.py`，创建独立 `.venv` 并验证辅助工具；不安装 OneTrainer、ComfyUI 或 Torch。

## 分开维护三个环境

1. `oc-lora-tools`：本仓库的轻量数据审查、配置生成和 ComfyUI API 工具。可用 `environment.yml`，或在 Python 3.12 环境执行 `python -m pip install -r requirements.txt`。
2. OneTrainer：按 [OneTrainer 上游安装说明](https://github.com/Nerogar/OneTrainer) 建立独立 GPU 环境。训练入口必须用这个环境的 Python 执行；不能只安装本仓库的四个辅助依赖后直接训练。
3. ComfyUI：使用 [ComfyUI 上游](https://github.com/Comfy-Org/ComfyUI)或已安装的 Stability Matrix 包。评估脚本只连接已有服务，不安装、启动或停止服务。

实验版本记录在 `env/tested_versions.json`。OneTrainer 配置以该记录中的提交为依据；升级上游后先解析配置、检查依赖和 CUDA，再做短训练。依赖版本记录不是跨平台锁文件，也不保证新的显卡驱动组合兼容。

本轮训练环境为 Python 3.12、PyTorch 2.12.0+cu130；ComfyUI 的 PyTorch 环境独立。不能用显卡驱动显示的 CUDA 版本替代 `torch.cuda.is_available()` 和实际算子检查。

## 本机配置

复制 `configs/local.example.toml` 为 `configs/local.toml`，后者始终被 Git 忽略。字段如下：

| 字段 | 用途 |
|---|---|
| `paths.onetrainer` | OneTrainer 源码目录，含 `modules/` |
| `paths.comfyui` | ComfyUI 安装目录，仅用于个人部署记录 |
| `paths.base_model` | 已自行取得的 SDXL 底模 |
| `paths.dataset` | 图片与同名 TXT 数据集目录 |
| `paths.run` | 新运行目录 |
| `paths.output_model` | 新的最终 LoRA 路径 |
| `comfyui.url` | 已有 ComfyUI 的地址，默认回环地址 8188 端口 |

路径也可由 `OC_ONETRAINER`、`OC_BASE_MODEL`、`OC_DATASET`、`OC_RUN`、`OC_OUTPUT_MODEL` 等环境变量覆盖，服务地址使用 `OC_COMFYUI_URL`。相对文件路径统一以仓库根目录为基准。

未知配置表/字段、空值和非法服务 URL 会报错；显式传入但不存在的配置不会回退默认值。未指定配置且默认文件缺失时，辅助工具可以使用默认值；自检会给出提示。URL 不接受内嵌凭据。

## 环境自检

在辅助环境中运行 `python scripts/doctor.py --profile helper`；它只检查 Python、辅助依赖、配置和仓库所在盘空间。训练使用 `--profile training --training-python <OneTrainer环境的Python>`，检查源代码、模型/标签路径、输出是否空闲，并在指定解释器做小型 CUDA 算子探测。`--profile comfyui` 只查询已有服务的队列和底模下拉列表。

`--json` 输出机器可读结果；`--output runs/doctor.json` 留存私人报告。自检不能代替图片复核、完整训练依赖检查和实际短训练；整盘剩余空间也不是其他模型/缓存磁盘空间的保证。

不要把认证值写入跟踪的 JSON / TOML。确有模型下载认证需要时，使用对应工具自己的登录机制或进程环境；本仓库示例配置不含令牌字段。

## 大文件

底模、LoRA、分词器/模型缓存和 ComfyUI 放大模型由用户另行管理。工作流中的模型下拉名称必须与本机安装名称匹配。当前发布不使用 Git LFS，也不会借助 LFS 上传这些数据。
