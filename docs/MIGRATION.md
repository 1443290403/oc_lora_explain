# 换机安装与私有资源迁移

## 1. 克隆并准备 Python

```text
git clone https://github.com/1443290403/oc_lora_explain.git
cd oc_lora_explain
git branch --show-current
git log -1 --oneline
git ls-files
```

应能看到 README、scripts、configs 等文件；不要用仓库的旧检查结果判断当前是否为空。需要 Python 3.12；已有 Anaconda 可使用它的 Python，无需再安装一套全局 Python。

## 2. 安装辅助工具

Windows PowerShell（先激活 Python 3.12 Conda 环境也可）：

```powershell
./scripts/setup.ps1 -Python (Get-Command python).Source
./.venv/Scripts/python.exe -X utf8 scripts/doctor.py --profile helper
```

Linux / 云端：

```bash
bash scripts/setup.sh
.venv/bin/python scripts/doctor.py --profile helper
```

可指定解释器：Windows `-Python <解释器>`；Linux `bash scripts/setup.sh --python <解释器>`。环境目录通过 `-EnvDir` / `--env-dir` 指定，相对路径基于仓库根。脚本可以从其他工作目录调用。

安装器只安装 `requirements.txt` 的四个辅助依赖，执行自检和 CPU 测试。重复安装复用已有 Python 3.12 venv，保留 `configs/local.toml`；不会修改系统执行策略、下载 GPU 组件或启动训练。若 PowerShell 策略阻止脚本，直接用 Python 3.12 执行 `python scripts/bootstrap.py`。

离线重复验证用 `python scripts/bootstrap.py --skip-install`，前提是目标 venv 已安装依赖。Linux 如缺少 venv/ensurepip，先按操作系统说明安装 Python 3.12 的 venv 支持。不要复制旧电脑的 `.venv`；应在新机器重建。

## 3. 迁移私有资源并填写路径

资源清单模板在 `configs/assets.example.json`。它只描述角色、用途和建议位置，不包含私人文件列表。可另存为被忽略的 `configs/assets.local.json`，填写校验值以供私下迁移核对。

| 资源 | 准备方式 | 是否必需 |
|---|---|---|
| SDXL 底模 | 从合法来源取得相同版本，核对文件摘要 | 训练和生成 |
| 图片与同名 TXT | 通过私人备份搬运，保留来源和使用权限 | 训练 |
| V6 LoRA | 从个人备份搬运，保持评估计划名称一致 | V6 生成比较 |
| OneTrainer | 按上游安装独立环境，版本记录见 env/tested_versions.json | 训练 |
| ComfyUI | 独立安装或使用 Stability Matrix；核对模型下拉名称 | 生成比较 |
| 原始参考、旧权重和检查点 | 按需私下备份；不进入 Git | 追溯或恢复 |

编辑 `configs/local.toml` 后检查路径。迁移数据先复制，保留旧机器原件；不要把缓存、Conda 环境导出中的本机路径或下载认证一并提交。

文件 SHA-256 可用 PowerShell `Get-FileHash <文件> -Algorithm SHA256` 或 Linux `sha256sum <文件>` 核对。示例中的空校验值不代表已验证；私人数据的摘要清单也留在本地。替换同名模型权重后必须新建评估输出目录，API 图摘要不能识别服务器上同名文件内容的变化。

## 4. 按用途验收

```text
python scripts/doctor.py --profile training --training-python <OneTrainer环境的Python>
python scripts/audit_dataset.py <数据集目录> --output runs/dataset-audit.json
python scripts/doctor.py --profile comfyui
```

这些命令由辅助环境执行。训练自检在指定训练解释器中导入 Torch、分配很小的 CUDA 张量并执行算子；不加载模型，不代表完整依赖兼容或显存足够。然后按 [TRAINING](TRAINING.md) 生成新目录下的短训练配置，明确需要训练时才运行它。ComfyUI 自检只读已有服务，忙队列会报告失败而不打断任务。

`--json` 输出结构化结果；`--output runs/doctor.json` 保存私有报告。`FAIL` 表示该用途未就绪，`WARN` 表示需关注，`SKIP` 表示该用途不需要检查。辅助模式无需 GPU 或私有资源。

GPU 环境安装按 [OneTrainer](https://github.com/Nerogar/OneTrainer) 和 [ComfyUI](https://github.com/Comfy-Org/ComfyUI) 上游说明选择驱动与 Torch 组合；本仓库不把某台机器的 CUDA 组合强制套用到所有设备。
