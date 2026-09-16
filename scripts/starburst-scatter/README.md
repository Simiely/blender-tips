# scripts/starburst-scatter · 星芒散射光效系统

把「**参数化星芒 + 沿相机朝向的亮片散射**」做成一坨可复用的数据块集合 + 控制空物体。
完整架构、用法与注意事项见 [docs/星芒散射光效系统.md](../../docs/星芒散射光效系统.md)。

## 作用

在活动场景中生成一组**始终朝向相机的发光星芒亮片**，散布在三个点云宿主上；
`星芒_控制器` 上 6 个中文滑块统一控形状 / 大小 / 循环脉冲。

## 文件

| 文件 | 用途 |
|---|---|
| `probe_star.py` | **只读**探查：控制器 6 参数、源 `星芒` 修改器与驱动表达式、三宿主散布偏移、ObjectInfo 空间、控制器循环动画 |
| `verify_star.py` | **独立核验**：逐项核对不变量（控制器参数 / 源隐藏渲染 / 星芒_GN 修改器 / scale 驱动含 `实际大小/1000` / 4 形状驱动 / ObjectInfo RELATIVE / 三组偏移 / material_override / Eevee），输出 PASS/FAIL 清单与 `VERIFY_RESULT` |
| `fix_star_scale.py` | **修复**源 scale 驱动：把 3 条表达式统一重置为 `实际大小/1000 + 动态缩放/1000`，让控制器 `动态缩放` 循环动画重新作用到整体大小；幂等、先打印旧表达式 |

## 使用

1. 连接运行中的 Blender 桥（端口可 `-p` 指定，默认 9877）：
   ```bash
   python ../blender-remote-control/send.py probe_star.py      # 查当前状态
   python ../blender-remote-control/send.py verify_star.py     # 核验不变量
   python ../blender-remote-control/send.py fix_star_scale.py  # 修复 scale 驱动(可选)
   ```
2. 脚本顶部 `SRC / CTRL / HOSTS / EXPECT_OFFSET` 可改对象名。

## 复用时注意（详见文档 §七）

- 源 `星芒.hide_render=True` 只隐藏本尊，散布实例照常渲染。
- `实际大小` 走源 scale，必须被散布组 `ObjectInfo` 以 **RELATIVE** 读取才生效；改动 `ObjectInfo` 空间会失效。
- 位置偏移要经 `设置位置` 施加在**实例化之前的点**上，别直接改 IOP scale/position。
- `动态缩放` 影响整体大小依赖 source scale 驱动表达式**含 `+ b/1000`**（`fix_star_scale.py` 一键恢复）。
- `生成数量` 在节点组接口 / 修改器面板调，不要用空对象属性去驱动几何 socket（5.2 读缓存值，不可靠）。
- 核验/读被驱动值一律走 depsgraph；脚本改动后 `update_tag()` + 另起一次请求回读断言。

脚本经桥执行、不带 `__main__` 守卫、UTF-8 无 BOM，可直接 `send.py` 送桥。