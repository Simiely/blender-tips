# 视口预览录制(录屏式,非全渲染) · 跨项目复用脚本

Blender 里一键导出**当前相机视角的视口预览视频**:走 `bpy.ops.render.opengl`,
抓的是视口显示样式(实体/SOLID 等),**不进灯光渲染**,速度快,相当于"录屏"。
用于给甲方 / 自己快速看动画效果,而不是等 Cycles 全渲染。

## 文件清单

| 文件 | 作用 | 运行位置 |
|---|---|---|
| `playblast_export.py` | 一键配置输出 + 触发视口录制;顶部可调输出路径 / 分辨率 | **Blender 内部**(Scripting 工作区 Run Script) |
| `../docs/视口预览录制录屏式.md` | 原理 / 用法 / 5.2 输出配置坑 | 阅读 |

## 用法

1. 在 Blender 里把你想要的机位设成**场景活动相机**(选中相机 → 右键 / `Ctrl+Numpad0`)；
   若工程里相机按帧切换机位,预览会自动带上机位切换。
2. 打开 `playblast_export.py`,按需求改顶部:
   - `OUTPUT_PATH` —— 输出文件名(默认 `E:/desktop/视口预览.mp4`)
   - `WIDTH, HEIGHT` —— 分辨率(默认 1920×1080)
3. 文本编辑器里 **Run Script**(Alt+P)。进度在 Blender 顶部状态栏,跑完打印 `PLAYBLAST_DONE`。

> 录制范围 = 时间轴的「预览范围 / 渲染范围」(frame_start ~ frame_end),和渲染动画一致。

## 注意事项(踩过的坑)

1. **Blender 5.2 输出配置顺序**:必须先 `image_settings.media_type = 'VIDEO'`,
   **再** `image_settings.file_format = 'FFMPEG'`;顺序反了直接报
   `'FFMPEG' not found in enum` 之类错误。脚本已按正确顺序写。
2. **`view_context=False` = 从相机出画面**:这正是你要的"我打的相机"视角。
   若误用 `view_context=True`,录的是当前 3D 视口(可能没锁定相机、带 UI)。
3. **分辨率 / 帧率是项目当前值**:脚本只显式设了分辨率与百分比;帧率取场景 `render.fps`,
   改帧率去输出属性面板。
4. **音频 `NONE`**:纯视口预览无声,符合"录屏看效果"用途;要带声再改 `audio_codec`。
5. **大场景 + 高分辨率可能卡**:这是实时视口抓取,复杂场景掉帧属正常;要稳就降分辨率或简化显示。

## 调试建议

- 想录"我当前看到的视口"而非相机 → 把 `view_context=False` 改成 `True`
- 输出空白 / 打不开 → 确认 `OUTPUT_PATH` 所在目录存在、路径无中文编码问题(Windows 建议英文路径)
- 想带透明 / 不同格式 → 改 `ffmpeg.format` / `ffmpeg.codec`(如 `QUICKTIME` + `QTRLE`)
