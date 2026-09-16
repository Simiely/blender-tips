# scripts/snowfall-scatter · 下雪动态系统

把「**参数化连续下落雪花(真实雪速) + 循环回卷 + 顶部入场缩放**」做成一坨可复用的节点组集合 + 宿主空物体。
完整架构、用法与注意事项见 [docs/雪花下落系统.md](../../docs/雪花下落系统.md)。

## 作用

在地面参考平面(`平面.005`)上方生成 **N_X×N_Y(默认 250×200=50000)** 片低模雪花,
从「天空(地面+30m)」匀速下落到「地面(-1.3m)」,**触地瞬间回卷到天空**(无半空消失),
顶部有 0→满 的入场缩放;全程实例化低模雪花源,源对象**隐藏渲染**、只当几何来源。

## 文件

| 文件 | 用途 |
|---|---|
| `build_snowfall.py` | **构建/重建**下雪节点组 `下雪_GN` 并挂到宿主 `下雪_宿主`;幂等(已存在则重建);顶部参数可改(数量/速度/高度/缩放/朝向,见文档 §四) |
| `pack_snow_collection.py` | **归拢**宿主/雪花源/地面参考到集合 `下雪_系统`,便于整体复制到其他工程 |
| `verify_snow.py` | **独立核验**：逐项核对不变量(宿主 EMPTY 且变换清零 / NODES 修改器挂载 / 源隐藏渲染 / 集合成员 / ObjectInfo RELATIVE / 栅格 250×200 / FLOORED_MODULO / 3 帧实例数==50000 且 Z 贴地[-1.3,28.7])，输出 PASS/FAIL 清单与 `VERIFY_RESULT` |
| `probe_snow.py` | **只读**探查：抽样 3 帧的实例数量、X/Y/Z 范围、贴地高度(读地平面世界包围盒) |

## 使用

1. 连接运行中的 Blender 桥(端口可 `-p` 指定,默认 9877；本项目常用 9878)：
   ```bash
   python ../blender-remote-control/send.py -p 9878 build_snowfall.py    # 构建/重建(必要时先备份 .blend)
   python ../blender-remote-control/send.py -p 9878 probe_snow.py        # 查当前实例数与贴地范围
   python ../blender-remote-control/send.py -p 9878 verify_snow.py       # 核验不变量
   python ../blender-remote-control/send.py -p 9878 pack_snow_collection.py  # 归拢到 下雪_系统(迁移用)
   ```
2. 脚本顶部 `HOST / SNOW / PLANE / GROUP / N_X,N_Y / FALL_SPAN / CYCLE / FLAKE_SCALE` 可改对象名与参数。

## 复用时注意(详见文档 §七)

- 源 `花瓣雪花_低模` 设 `hide_render=True` / `hide_viewport=True` / `visible_camera=False`：只隐藏"相机直接渲染"本尊，散布实例照常渲染。
- **宿主必须是 EMPTY 且变换清零(loc=0, rot=0, scale=1)** —— 雪区高度严格锚定地面参考平面;宿主若被移动(如 Z=-1.47)整个雪区会整体偏移、雪会埋进地面。
- 落点 X/Y 取地平面**世界包围盒**中心与半宽,Z 由 `prog=fmod(t/CYCLE+相位,1)` 在 `[地面, 地面+30m]` 间线性映射;`CYCLE=60s` 使速度≈0.5m/s(真实枝晶雪花末速度)。
- **RandomValue 必须显式接 Index**：相位/位置/朝向共用点唯一编号作 ID 输入,确保每片独立,防止顶部堆积/共线分布。
- 触地回卷靠 `FLOORED_MODULO`(一次性贴地后直达 0 相位回顶部),**不要加贴地淡出**,否则出现"雪花半空消失"。
- 朝向用 `合并XYZ`：X=倾角(默认 90°±15°≈垂直/平行 Z,平视也看得到平面)、Z=绕轴随机转,源雪花本体做成平展的平面网格。