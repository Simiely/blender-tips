# frame-window-time-switch —— 按帧区间开/关节点参数(渐变时间开关)

让材质里某个节点参数在**指定帧区间内生效、区间外关闭**。这里的例子是"同心圆渐变开关":
0–516 帧纯色(无渐变)→ 517–657 帧渐变 → 658 帧后纯色。

## 场景

- 想要某个发光/渐变效果只在时间线的某一段出现,其余时间退化为纯色/基础态;
- 播放动画时开关要**实时、逐帧正确**跟随时间线;
- 换了电脑/重开工程后,效果和开关都要稳定,驱动不报红。

## 用法

```bash
python send.py build_frame_window_switch.py     # 经 socket 桥远程执行
# 或在 Blender Scripting 工作区 Run Script
```

改顶部常量:`MAT_NAMES`(目标材质列表)、`NODE_NAME`(要驱动的 Value 节点名)、
`WINDOW=(开始, 结束)`(开=1 的闭区间)。

脚本做三件事:
1. 按 `WINDOW` 生成 `grad_window(fr)` 并写入 Register 文本块 `grad_window_driver.py`
   (use_module=True → 重开自动注册,驱动不报红);
2. 给每个目标材质的 Value 节点输出挂 SCRIPTED 驱动 `grad_window(fr)`,`fr` 读 `scene.frame_current`;
3. 用 **depsgraph 评估值**逐帧验证(0–开-1=0, 开~关=1, 关+1=0)。

## 关键坑(Blender 5.2 实测)

- **Value 节点别用关键帧**:对 `outputs[0].default_value` 用 `keyframe_insert` 打动画,
  关键帧虽写在 fcurve(求值对),但 **Slotted Action 下评估值恒定不变**(原始与评估都是默认值)→ 用户看开关一直是 1。
  → 正确做法:给该 socket 挂 **SCRIPTED 驱动**,表达式调用命名空间函数读 `scene.frame_current`。
- **重新注册命名空间函数后必须强制重编译驱动**:`d.expression = d.expression`,
  否则 depsgraph 缓存旧函数闭包(驱动不重算)。
- **5.2 的 Action 是 Slotted 结构**:`action.fcurves` 已移除,读取关键帧要走
  `action.layers[].strips[].channelbag.fcurves`;`action.slots[].fcurves` 也不存在。
- **验证读评估值**:`deps.id_eval_get(mat)` 拿到真实渲染值;直接读原始
  `node.outputs[0].default_value` 可能读到未动画的默认值.

## 文件

| 文件 | 说明 |
|---|---|
| `build_frame_window_switch.py` | 一键:注册函数 + 挂驱动 + 评估值验证 |
| `grad_window_driver.py` | Register 文本块载荷(重启持久) |