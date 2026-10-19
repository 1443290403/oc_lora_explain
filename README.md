# 奈卡尔 OC LoRA：训练与验证记录

使用 OneTrainer 训练 Illustrious / waiIllustrious SDXL 角色 LoRA，并通过 ComfyUI 检查人设、曝光和全身眼部表现。本仓库保存可移植的辅助代码、配置模板、工作流及经过整理的实验结论。

**不包含**底模、LoRA 权重、训练图片、作者参考图、逐图标签、缓存、生成图片、机器配置或认证信息。原有本地实验仍保留在项目目录，通过 `.gitignore` 排除；不能仅靠克隆本仓库获得训练素材或复现实验图片。

## 目录

| 目录 / 文件 | 内容 |
|---|---|
| `scripts/` | 数据审查、配置生成、训练监控、ComfyUI 对照及提交检查 |
| `configs/` | 脱敏的 SDXL LoRA 配置、对照计划、本机配置示例 |
| `workflows/` | ComfyUI 近景、全身、图像放大和手动脸部修复工作流 |
| `docs/` | 环境、数据规范、训练流程、评估结论和发布规则 |
| `env/tested_versions.json` | 实验时观察到的版本，不是完整安装锁文件 |
| `tests/` | 路径替换、数据审查、采样图与发布检查的 CPU 测试 |

## 快速开始

需要 Python 3.12。辅助工具可以使用独立环境：

```powershell
conda env create -f environment.yml
conda activate oc-lora-tools
Copy-Item configs/local.example.toml configs/local.toml
```

编辑被 Git 忽略的 `configs/local.toml`，填写现有 OneTrainer、ComfyUI、底模和数据集的位置。配置中的相对路径统一相对于项目根目录，不依赖启动命令的工作目录。

```powershell
# 仅读取数据，报告写入私有运行目录。
python scripts/audit_dataset.py data/clean_dataset_v6 --output runs/audit.json

# 生成配置，不启动训练。数据和底模必须已经存在。
python scripts/make_train_config.py --run-dir runs/smoke --smoke-images 12

# 必须使用已安装 OneTrainer 依赖的 Python 环境；这一步会实际训练。
conda run -n onetrainer python scripts/run_training.py runs/smoke/train_config.json
```

完整训练使用新的运行目录和输出文件名：

```powershell
python scripts/make_train_config.py --run-dir runs/v6-new
conda run -n onetrainer python scripts/run_training.py runs/v6-new/train_config.json
```

`requirements.txt` 仅用于辅助工具，不能代替 OneTrainer 或 ComfyUI 自身的完整依赖。安装方式与 CUDA 注意事项见[环境说明](docs/SETUP.md)。

## 当前基线与限制

- 触发词：`naikaer_oc`；底模：`waiIllustriousSDXL_v170.safetensors`。
- V6 从底模新建 LoRA：100 张经人工复核的图片，896 分桶，rank/alpha 16/16，8 轮、每图 2 次重复，共 1600 步；不训练文本编码器。
- 本次 8GB 显卡实验完成训练，整卡显存峰值约 7.52 GiB。该数字不是所有机器或配置的显存保证。
- 无画师对照中，日常与灰背景发白改善；暗场、服装附加和视线服从仍有偏向。
- 0.7 / 1.0、三个种子的六张近景测试未再出现全绿发顶，但不能据此保证任意姿势和种子均正确。
- 额外 20 个全身/局部测试确认：全身小脸的瞳孔和眼形仍可能不规整。提高分辨率或图像放大改善清晰度，局部修复仍需检查。

这些是有限样本的实验观察，不是通用最优参数。[完整结论与局限](docs/RESULTS.md)

## 工作流与评估

ComfyUI 已启动、模型已安装且队列空闲时，可执行明确的对照计划：

```powershell
python scripts/comfy_evaluate.py --plan configs/evaluation_fullbody.example.json --output runs/fullbody-check --free-cache
```

示例计划包含 V4 / V5 等对照项。缺少相应 LoRA 时先从计划中删除这些项，或换成自己已安装的文件名；权重文件不在仓库中。

`workflows/face_refine_manual.json` **需要先选本地图并手动定位脸部**，不是自动人脸检测工作流。其他工作流的生成种子默认随机变化。详见[评估与工作流说明](docs/EVALUATION.md)。

## 提交前检查

```powershell
python -m unittest discover -s tests -v
git add .gitignore .gitattributes README.md requirements.txt environment.yml scripts configs workflows docs env tests
python scripts/check_publish.py
git diff --cached --stat
```

检查器扫描 Git 暂存区中的实际内容，不输出发现的密钥值。它不能替代人工审阅。[发布范围与敏感数据规则](docs/REPOSITORY.md)

角色设定与图片使用规范见[数据集说明](docs/DATASET.md)。本仓库没有发布参考素材、训练数据或模型，也不代为授予这些资源的使用权；上游工具按各自许可证使用。
