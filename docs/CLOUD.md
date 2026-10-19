# 云端辅助开发环境

本项目没有必须长期运行的 Web 服务。无 GPU、无模型和无私人数据的环境可用于代码维护、配置测试和发布检查；不能据此声称已完成 GPU 训练验证。

## 准备与验证

在仓库根执行：

```bash
git branch --show-current
git log -1 --oneline
git ls-files
bash scripts/setup.sh
.venv/bin/python scripts/doctor.py --profile helper --json
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/check_publish.py
```

环境需要 Python 3.12 和 venv 支持。安装器使用 `.venv`，执行依赖安装、自检和测试。后续步骤显式使用 `.venv/bin/python`，不依赖一次 shell 激活跨步骤保持。

## Codex Cloud 的环境说明

安装说明可以填写 `bash scripts/setup.sh`；启动说明记录“本仓库无常驻服务，后续用 .venv/bin/python 执行命令”。不要在启动步骤训练模型或启动 ComfyUI。

修改代码前读取根目录 `AGENTS.md` 和 `docs/PROJECT_STATUS.md`。确认环境挂载的是正确仓库和含项目文件的分支。如果最初挂载时远端为空，应先刷新到当前远端代码，再运行以上命令，不沿用旧的空仓库结论。

保存环境配置与发布环境是不同步骤；环境调整后保存并重新发布，后续任务才能使用准备好的环境。更新远端代码不等于重新运行安装步骤。具体操作以 [OpenAI 官方云端环境说明](https://learn.chatgpt.com/docs/environments/cloud-environments) 为准。

## 验收依据

- 文件树包含代码和配置，不只是一个空 Git 目录。
- 辅助依赖可导入，doctor helper 无 FAIL，CPU 测试全部通过。
- 上传检查通过；模型、图片、私人配置不在 Git 索引中。
- 记录实际执行地点和结果；本机测试、GitHub Actions 和某个云端环境的测试分别报告，不能相互代替。

GitHub Actions 会在 Windows 和 Ubuntu 上执行安装及重复安装验证，不需要认证令牌、模型下载或 GPU。
