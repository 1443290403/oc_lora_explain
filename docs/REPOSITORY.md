# 发布范围和检查

## 白名单发布

仓库根目录原先是本地实验工作区，含底模、多个版本的训练集、旧脚本、运行配置和生成结果。整理时保留这些原件，仅把可移植、必要的代码复制或整理到 `scripts/`，把配置模板、工作流和文档放入对应目录。

`.gitignore` 默认排除根目录所有项目，再允许必要目录和根文件；同时继续排除这些目录内的模型、图片、归档、日志、缓存和私人配置。即使旧目录里有可读的Python或JSON，也不会因此自动进入提交。

发布范围：

- `scripts/`、`tests/`中的UTF-8源代码；
- `configs/`中的不含认证值、使用路径占位符的模板；
- `workflows/`中的可加载JSON，选图输入已替换为占位符；
- 经过整理的文档、依赖说明、版本记录和Git规则。

保留本地：原始/训练/生成图片，作者参考图，逐图caption和素材清单，模型与中间权重，训练缓存和优化器状态，API执行历史，实验日志/报告原件，旧脚本和机器专用配置。不会使用强制添加或Git LFS绕过这些规则。

## 路径与密钥

脚本使用项目相对路径、`configs/local.toml`和环境变量。模板在本机展开后的运行配置会包含绝对路径，但位于忽略的运行目录，不参与发布。

不提交令牌、私钥、带凭据URL或GitHub CLI登录信息。上游配置中的空secrets和不用的cloud部分也从发布模板移除。依赖列表只描述辅助工具和已观察版本，不提交含本机环境prefix或临时构建路径的原始Anaconda导出。

## 检查实际提交内容

```powershell
git add .gitignore .gitattributes README.md requirements.txt environment.yml scripts configs workflows docs env tests
python scripts/check_publish.py
git diff --cached --check
git diff --cached --stat
git status --short
```

`check_publish.py`读取Git索引中的blob，检查目录/扩展名白名单、单文件大小、UTF-8、常见认证格式、填值的JSON密钥字段及本机路径。只报告文件、行号和类别，不打印发现的认证值。

它是项目专用的保守检查器，不是完整的密钥检测服务：自定义命名的秘密、经过编码的值和人工误判仍需审阅。已有跟踪文件不受`.gitignore`保护，所以每次发布仍应检查暂存区。

首次提交推送前应核实远端地址、仓库是否为空以及当前GitHub身份。使用仓库级提交身份，不覆盖用户全局Git配置；不强制推送、不改变仓库可见性、不创建其他仓库。
