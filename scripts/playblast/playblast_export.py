# playblast_export.py —— Blender 视口预览录制(录屏式,非全渲染)
#
# 用法: Blender 文本编辑器打开本文件 → Alt+P 运行(也能存进 .blend 文本块)
#
# 特点:
#   - 从「场景相机」出画面(view_context=False),即你打的相机视角(会带上机位切换动画)
#   - 抓当前显示样式(实体/SOLID 等),不进灯光渲染,相当于录屏,速度快
#   - Blender 5.2 新输出系统: 必须先 media_type='VIDEO' 再 file_format='FFMPEG'
#     (顺序反了会报 "XXX not found in enum" 错误)
#
# 可调参数见下方 ===== 可调参数 ===== 块

# ===== 可调参数 =====
OUTPUT_PATH = r'E:/desktop/视口预览.mp4'   # 输出文件名(改成你想要的保存路径)
WIDTH, HEIGHT = 1920, 1080                 # 输出分辨率(改这里换尺寸)
# ====================

import bpy

s = bpy.context.scene

# Blender 5.2 新输出系统: 先 VIDEO 再 FFMPEG(顺序不能反,否则报枚举无此值)
isx = s.render.image_settings
isx.media_type = 'VIDEO'
isx.file_format = 'FFMPEG'
s.render.ffmpeg.format = 'MPEG4'
s.render.ffmpeg.codec = 'H264'
s.render.ffmpeg.audio_codec = 'NONE'
s.render.resolution_x = WIDTH
s.render.resolution_y = HEIGHT
s.render.resolution_percentage = 100
s.render.filepath = OUTPUT_PATH

# 用当前场景相机(确保你的工程里 s.camera 指向想要机位;如有按帧切换机位的动画,预览会带上)
if s.camera is None:
    cam = next((o for o in s.objects if o.type == 'CAMERA'), None)
    if cam:
        s.camera = cam
        print('SET_CAMERA', cam.name)
    else:
        print('WARN 场景没有相机,预览会用当前视口(等价于 view_context=True)')

# 视口录制: 抓当前显示样式,不进灯光渲染,相当于录屏
bpy.ops.render.opengl(animation=True, view_context=False)
print('PLAYBLAST_DONE ->', s.render.filepath)
