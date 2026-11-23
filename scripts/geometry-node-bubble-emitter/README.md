# geometry-node-bubble-emitter

几何节点泡泡发射系统的可复用脚本包。来源：9666 桥工程实战，Blender 5.3，工程 `E:\desktop\261123\气泡生成.blend`。

## 用途

从 `发射口` 发射大量球体泡泡，贴合网格 `泡泡范围` 的圆形边界，支持：

- 出生帧门控
- 圆形范围匹配
- 淡入淡出，避免地面突跳
- 下落随机消散
- 整体慢速倍率
- 控制器中文滑块驱动

## 文件

| 文件 | 用途 |
|---|---|
| `probe_state.py` | 只读读取控制器参数和节点状态 |
| `probe_gn_api.py` | 只读探测 Blender 5.3 GN 节点 socket / operation |
| `build_bubble_emitter.py` | 建基础系统：控制器、源球、系统对象、基础节点组 |
| `patch_01_range_match.py` | 接圆形范围匹配 |
| `patch_02_fade_kill.py` | 接淡入淡出与下落随机消散 |
| `patch_03_slow_all.py` | 整体降低生成密度与速度 |
| `patch_04_speed_multiplier.py` | 将整体速度参数化为 `慢速倍率` |
| `patch_optional_apex_ratio.py` | 可选：独立调节高度曲线顶点比例 |
| `verify_bubble_emitter.py` | 最终独立核验 |

## 使用顺序

这些是实际实战中使用过的增量脚本，必须按顺序执行：

```text
probe_state.py
probe_gn_api.py
build_bubble_emitter.py
patch_01_range_match.py
patch_02_fade_kill.py
patch_03_slow_all.py
patch_04_speed_multiplier.py
verify_bubble_emitter.py
```

`patch_optional_apex_ratio.py` 只在需要单独调顶点比例时插入。

## 桥客户端

脚本通过远程桥执行，桥客户端约定：

```text
python bl2.py <脚本.py>
```

其中 `bl2.py` 连接 `127.0.0.1:9666`，发送 Python 源码 + `<END>`，接收 `OK/ERR` 响应。

## 配置注意

- 脚本顶部 `OUT` 是本地报告输出路径，迁到新机器必须改
- 脚本会保留控制器当前参数；`build_bubble_emitter.py` 只在对象不存在时创建默认值
- 补丁脚本按节点 `label` 查找节点，不要随意改中文节点标签
- 所有脚本均禁止 `if __name__ == "__main__"` 守卫
- 桥只改内存，执行完必须提醒用户 Ctrl+S

## 实测结果

最终参数：`生命周期=96`、`慢速倍率=2.5`（有效 240 帧）、`泡泡数量=600`、`上升高度=1.0`、`起始帧=0`、`泡泡半径=0.03`、`下落消散=0.35`。

| 帧 | 数量 |
|---:|---:|
| 0 | 0 |
| 20 | 50 |
| 60 | 148 |
| 150 | 383 |
| 300 | 548 |

慢速倍率改成 `1.0` 时，帧 20 为 123 个，证明倍率驱动有效。
