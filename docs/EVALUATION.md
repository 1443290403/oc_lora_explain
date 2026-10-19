# ComfyUI 对照与工作流

## 服务与模型

本仓库的评估脚本连接已存在的 ComfyUI，不负责启动或停止进程。队列忙时拒绝插入测试，不清空历史、不发送中断。`--free-cache` 在测试完成且队列空闲时释放模型缓存，它不等于关闭服务。

测试前自行安装底模和所需 LoRA，并核对下拉列表名称。计划中的 V4/V5 是可选对照，仓库不分发这些权重。现有 ComfyUI 服务由用户启动时保留；另行启动专用调试服务的操作者应在调试结束后关闭自己创建的进程。

## 对照计划

```powershell
python scripts/comfy_evaluate.py --plan configs/evaluation_exposure.example.json --output runs/exposure-check --free-cache
python scripts/comfy_evaluate.py --plan configs/evaluation_fullbody.example.json --output runs/fullbody-check --free-cache
```

曝光计划保留三组场景的提示词、种子和采样参数；全身计划保留 18 个全身、权重、底模、近景和分辨率控制。运行前根据可用模型编辑计划或另存计划；缺少 LoRA 时脚本会报错，不会偷偷换模型。

输出包括 PNG、API 图、history、结果 JSON 和联系表，全在私有运行目录。已有输出目录默认拒绝覆盖。显式 `--resume` 只有在有效 API 图摘要和已保存图片 SHA-256 均一致时，才跳过完成项；允许保留已完成项并添加新名称。参数变化、图片缺失/被修改、计划删除旧完成项或旧结果缺少摘要时，会在连接服务前拒绝续跑，要求使用新输出目录，保留旧结果。

API 图摘要包括提示词、种子、模型名称、强度、采样器、分辨率及实际使用的默认参数；也能识别图构建代码改变导致的有效参数变化。它不能识别服务器上同名权重被替换的情况；此时仍须新建输出目录。固定种子用于复现实验；想生成新图应改 seed 并使用新目录或新的任务名称。

所有基线均不带画师词、不启用 RescaleCFG。相同场景内固定种子、分辨率、CFG、采样器和步数。改变分辨率或 LoRA 强度后，相同 seed 也可能产生不同构图，不能当作像素级对应实验。

## 可加载工作流

| 文件 | 用途与限制 |
|---|---|
| `portrait_v6.json` | 近景通用，LoRA0.7、832×1216、28步、CFG5.5 |
| `portrait_v6_strength100.json` | 强度1.0对照；暗场可能更受训练风格影响 |
| `fullbody_direct1024.json` | 直接1024×1536全身，构图可能变化 |
| `fullbody_pixel_hires.json` | 先832×1216，再Lanczos到1248×1824，重绘16步、denoise0.30；分别保存原图和结果 |
| `face_refine_manual.json` | 选择本地图片、手动定位脸部，裁剪224×224放大到768，重绘24步、denoise0.40，再软融合回原图 |

工作流使用现有核心节点。`face_refine_manual.json` 中的图片名为占位符，必须先从本机选择图片，再调整裁剪 X/Y 让脸处于区域中央。裁剪与融合坐标同步；换图后同一坐标不会自动跟随脸部。脸大小差异大时还需调整裁剪尺寸与遮罩。

局部768px预览不是最终全图分辨率；回贴后的图仍保持输入尺寸。该流程不是自动 FaceDetailer，也不能保证所有瞳孔、左右设定或复杂角度都正确。采样器种子默认随机变化，便于同提示词连续生成新图；实验复现时改成固定。

两遍放大方案参考 [ComfyUI 作者的 Hires Fix 示例](https://comfyanonymous.github.io/ComfyUI_examples/2_pass_txt2img/)。本次低重绘强度的 latent 放大出现条纹，故工作流保留的是图像空间放大方案；不能据此否定所有潜空间放大配置。
