# parameter-popup-door

参数化弹出门与角色控制系统的可复用脚本包。来源：9877 桥工程实战，Blender 5.3，工程 `E:\desktop\261123\高地聚场主装置最终定稿\261123.blend`。

## 用途

用一个空对象控制器 `3点钟_弹出控制["弹出进度"]` 的 0–10 参数，同步驱动：

- 3点钟方向的左右门 Z 旋转与角色 Y 位移
- 10点钟方向的左右门 Z 旋转与角色 Y 位移

## 文件

| 文件 | 用途 |
|---|---|
| `probe_current_pose.py` | 只读探当前子树状态，防止用户已改场景 |
| `capture_3oclock.py` | 抓 3点钟方向基线 JSON/TXT |
| `build_3oclock.py` | 建控制器与 3 条驱动 |
| `fix_radians_expr.py` | 修复门表达式误套 `radians()` |
| `verify_3oclock.py` | 3点钟方向独立核验 |
| `capture_10oclock.py` | 抓 10点钟方向当前状态 |
| `build_10oclock.py` | 复用同一控制器挂 3 条驱动 |
| `verify_10oclock.py` | 10点钟方向独立核验 |

## 使用顺序

```text
probe_current_pose.py
capture_3oclock.py
build_3oclock.py
fix_radians_expr.py    # 仅当出现角度被除 57.3 的错误时
verify_3oclock.py
capture_10oclock.py
build_10oclock.py
verify_10oclock.py
```

## 桥客户端

```text
python bl.py <脚本.py>
```

`bl.py` 连接 `127.0.0.1:9877`。

## 配置注意

- 执行前必须让用户确认哪一端是初始、哪一端是最终
- baseline JSON/TXT 是本脚本包的安全闸，不要跳过
- 驱动表达式里的角度常量是弧度，不要套 `radians()`
- 控制空物体无子级，后续清理 EMPTY 时必须保留
- 第二组必须复用同一个控制器属性
- 角色 Y 在 10点钟方向是递减，核验判据不要写反
- 桥只改内存，执行完必须提醒用户 Ctrl+S

## 实测端点

| 对象 | 通道 | p=0 | p=10 |
|---|---|---:|---:|
| 3点钟右门 | rotZ | 3.141592741 | 0.968994 |
| 3点钟左门 | rotZ | 0 | 2.207841 |
| 3点钟角色 | locY | -8.837891 | -343.205627 |
| 10点钟右门 | rotZ | 0 | -2.775074 |
| 10点钟左门 | rotZ | 0 | 2.722714 |
| 10点钟角色 | locY | 31.439859 | 31.018097 |

控制器关键帧最终为用户调整的 `(30,0) → (75,10)`。
