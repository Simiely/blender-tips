# Blender 远程控制桥(跨机器复用包)

从 Blender 外部(命令行/脚本/WorkBuddy)远程操控运行中的 Blender:
读取场景、修改对象属性、调关键帧、设置驱动、查渲染配置等,无需在 GUI 里手动操作。

## 文件清单

| 文件 | 作用 | 运行位置 |
|---|---|---|
| `blender_bridge.py` | **桥服务端**。监听 9877 端口,把收到的 Python 代码调度到 Blender 主线程执行 | **Blender 内部**(Scripting 工作区运行) |
| `send.py` | **发送客户端**。把本地 .py 文件内容发给桥执行,打印返回结果 | 外部命令行(Python 3) |
| `example_probe.py` | 通用示例:探查场景所有相机及其关键帧(兼容 Blender 4.x / 5.x) | 外部,配合 send.py 使用 |

## 工作原理

```
外部 Python (send.py) ──9877 socket──▶ Blender 内的桥 (blender_bridge.py)
                                          │
                                          ├─ 收到代码 → 加入队列
                                          ├─ bpy.app.timers 每 0.05s 在主线程执行
                                          │   (安全读写 bpy.context/场景数据)
                                          └─ 结果(含 print 输出/异常)返回发送端
```

**为什么需要主线程执行**:Blender 的 `bpy.context` 和场景修改**只能在主线程安全操作**。v2 桥用 `bpy.app.timers` 调度,避免了旧版(9876)子线程改场景导致的崩溃/未定义行为。端口用 9877 与旧版区分。

## 环境要求(跨机器复用核对清单)

- Blender(实测 5.2;4.x 的 fcurves API 也兼容)
- 外部 Python 3(任意安装,`send.py` 只用标准库 socket,无第三方依赖)
- 桥与发送端**在同一台机器**(127.0.0.1),或改 `HOST` 支持远程

## 使用步骤

### 1. 启动桥(每台机器 / 每次重启 Blender 都要做一次)

1. Blender 切到 **Scripting** 工作区
2. 文本编辑器 → **Open** → 打开 `blender_bridge.py`
3. 点 **Run Script**(或 Alt+P)
4. 控制台输出 `[Bridge v2] BRIDGE READY ... port 9877` 即成功
   - 重复运行安全:自动关闭旧监听,不会重复注册

### 2. 发送代码(任意时刻,不需要碰 Blender)

```bash
python send.py example_probe.py          # 跑示例:探查相机和关键帧
python send.py 你的脚本.py                # 跑你自己的脚本
```

- 发送端自动加 `<END>` 帧协议,最长等待 120 秒
- 返回格式:`OK\n<print 输出>` 或 `ERR\n<traceback>`

### 3. 写自己的脚本

桥端执行环境预置了这些名字:

| 名字 | 含义 |
|---|---|
| `bpy` | `import bpy` |
| `C` | `bpy.context` |
| `D` | `bpy.data` |
| `scene` | `bpy.context.scene` |
| `mathutils` | `import mathutils` |

示例(保存为 `.py`,用 send.py 发送):

```python
# 把所有相机的渲染可见性关掉
for cam in [o for o in D.objects if o.type == 'CAMERA']:
    cam.hide_render = True
print('已隐藏', len([o for o in D.objects if o.type == 'CAMERA']), '个相机')
```

## 注意事项(踩过的坑)

1. **Blender 5.2 Slotted Action**:`action.fcurves` 不存在!读取/创建曲线用 `action.fcurve_ensure_for_datablock(datablock, data_path, index=i)`,`index` 必须关键字传参。参考 `example_probe.py` 的兼容写法。
2. **远程脚本不要写合成器节点树**(新建/删除 File Output 节点、操作槽)→ 触发 5.x 已知崩溃 bug(进程直接消失)。合成器写操作一律 GUI 手动,远程只读探查。
3. **渲染是阻塞操作**:在桥里跑 `bpy.ops.render.render()` 会阻塞主线程,队列里的其他任务会排队,超时上限 120s。渲染动画请用命令行 `blender -b` 方式,不要走桥。
4. **窗口句柄对象不能跨线程**:不要在脚本里直接引用 UI 元素;只操作 `bpy.data` / `bpy.context` 场景数据。
5. 修改完记得 Ctrl+S 保存(桥只改内存,不自动存盘)。

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `Connection refused` | 桥没启动,或 Blender 重启后没重新跑桥脚本 |
| 返回 `ERR ...` | 脚本有异常,看 traceback 定位 |
| 结果正常但 GUI 没变化 | 某些属性需要 `bpy.context.view_layer.update()` 或切帧刷新 |
| 想开机免手动 | 把桥注册为 Blender 启动脚本(`~/.config/blender/5.2/scripts/startup/` 或用户偏好),或用 `blender --python blender_bridge.py` 带参启动 |
