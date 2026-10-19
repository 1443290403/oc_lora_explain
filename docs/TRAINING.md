# 训练配置与监控

`configs/train_v6.example.json` 是经过路径占位符处理的 SDXL LoRA 基线。没有云端配置或密钥，OneTrainer 中未列出的字段使用上游默认值。

| 参数 | V6 基线 |
|---|---|
| 模式 | 从底模新建 LORA，不载入旧 LoRA / 优化器 |
| 分辨率 | 896，长宽比分桶 |
| rank / alpha | 16 / 16 |
| 训练层 | UNet 的 attn1、attn2；两个文本编码器不训练 |
| 精度 | BF16 计算，FP16 文本编码器，FP32 VAE |
| 优化器 | AdamW 8-bit |
| 学习率 | 5e-5，constant，warmup 80 步 |
| epoch / repeats | 8 / 2 |
| batch / accumulation | 1 / 1 |
| 预览 / 保存 | 每 400 步 |
| offset noise | 0.03，仅为本次实验参数 |

在 100 张、两次重复的情况下共 1600 步。修改数据数量、重复或 batch 后，应重新核对总步数和 warmup；这些数值不是所有数据集的最优解。

## 配置生成

先修改忽略的 `configs/local.toml`，确保底模和完整同名标签存在，输出文件名未被已有 LoRA 占用：

```powershell
python scripts/make_train_config.py --run-dir runs/v6-new
```

占位符在本地展开为绝对路径，结果位于被忽略的 `runs/`。`train_config.json`、`concepts.json` 和 `samples.json` 都是运行文件，不应提交。模板默认允许在线获取必要的模型结构配置；缓存齐全时可以在本地配置生成结果中改成离线模式。

短测会复制前 N 张有标签图片到独立目录，保留原始数据：

```powershell
python scripts/make_train_config.py --run-dir runs/smoke-new --smoke-images 12
conda run -n onetrainer python scripts/run_training.py runs/smoke-new/train_config.json
```

这对应一轮、一次重复、12 张图片；用于验证环境、缓存、显存和保存流程，不能当作最终角色 LoRA。

## 实际训练

```powershell
conda run -n onetrainer python scripts/run_training.py runs/v6-new/train_config.json
```

只有这一命令会启动训练。包装器使用 OneTrainer 的 Trainer / Callback 接口，每 10 步更新 `progress.json`，记录 step、epoch、阶段、运行时间、显存和进程内存。完成后检查输出 safetensors 的张量均为有限值，写入 `result.json`；失败返回非零退出码。

输出文件存在时拒绝覆盖。恢复已有 LoRA 会校验实际载入张量，但基线默认不恢复。现有运行目录也不会被配置生成器复用。

运行结束应检查 `completed`、实际步数、异常和模型大小，而不是仅根据 loss 判断人设或曝光。不要因近景样图良好就跳过全身眼部、手部和左右设定检查。

896 配置在本轮 8GB GPU 完成，不是显存承诺。遇到 OOM 应先降低分辨率并保持 batch1、关闭文本编码器训练；不得把含错误细节的增训当作通用修复。
