# 动画转移到父级空对象(动态转移 · 跨项目复用包)

把**某个对象自己的关键帧动画整份搬到新建的空对象上**,原对象退化为"纯被驱动"节点。
搬完之后,原对象的**世界运动逐帧完全不变**(可验证的恒等,不是"差不多")。

适用: 某个对象(典型是**相机**)自己带着关键帧动画,以后想改它的运动时**不想再给它本体 K 动画** ——
改成"改一个空对象就行"。也适用于任何"想把动态集中到控制对象上、让本体保持干净"的场合。

## 文件清单

| 文件 | 作用 | 运行位置 |
|---|---|---|
| `transfer_anim.py` | **执行转移**:建动态空对象 → 复制动画 → 原对象改挂并冻结 → (可选)插基点空对象归零 | 桥 `send.py` 或 Scripting 工作区 Run Script |
| `verify_transfer.py` | **验证器**:`MODE='record'` 转移前录世界矩阵基线 / `MODE='check'` 转移后逐帧对比 | 同上(两次请求) |
| `../docs/动画转移到父级空对象.md` | 完整原理 / 数学保证 / 踩坑 | 阅读 |

## 最终层级(默认 `ZERO_TARGET=True`,推荐)

```
原父级
└── <目标>_动态     ← 承载原动画(独立 action 副本)
    └── <目标>_基点  ← 无动画空对象,单位 MPI + 单位 basis(纯静态底座)
        └── <目标>   ← 本地变换彻底归零(action=None)
```

好处: 打开 N 面板一眼可见"动态全在上游",下次要加动态自然去 K **基点/动态空对象**,
不会再误 K 本体(尤其是本体原本那串"大数字"位姿)。

## 原理(一句话 + 恒等式)

世界变换恒等式: `matrix_world = parent.matrix_world @ matrix_parent_inverse @ matrix_basis`

1. 令空对象 **D** 与目标**同父级、同 `matrix_parent_inverse`、同 basis** → `D.world(t) ≡ M(t)`(全部帧)
2. 把目标的 action **复制**给 D(独立副本),D 就完整复刻了原世界运动
3. 把目标改挂到 D(或 D 下的基点 B)下并**摘掉自身动画**,冻结成静态 basis
   - `ZERO_TARGET=True` : 目标→B→D 三段全用单位 MPI+单位 basis → `M'(t) = D.world(t) = M(t)` **恒等(与参考帧无关)**
   - `ZERO_TARGET=False`: 目标→D,`MPI = B(F)⁻¹`、`basis = B(F)` → `M'(t) = M(t) @ B(F)⁻¹ @ B(F) = M(t)` **恒等**

> ⚠️ **通用解是 `B(F)⁻¹`(局部 basis 的逆),不是 `M(F)⁻¹`(世界矩阵的逆)**。
> 只有"参考帧 F 处局部 == 世界"(`mpi_old @ parent.world(F) == I`,例如 F 帧父级 Z 旋转为 0)时两者才相等。
> 自测实测: 让参考帧处 `M(F)` 与 `B(F)` 相差 6.35 单位时,用 `B(F)⁻¹` 结果 0 偏差,用 `M(F)⁻¹` 会把对象挪偏 6.35 单位。

## 环境要求

- Blender 5.2(实测);桥远程执行见 `../blender-remote-control/`
- 目标对象必须**自带 action 动画**(纯驱动对象没有 action 可搬,报错退出)

## 使用步骤

### 1. 转移前: 录基线(必做)

编辑 `verify_transfer.py` 顶部:
```python
TARGET = '摄像机x02_151-370'      # 要转移的对象
MODE = 'record'
```
运行(桥: `python send.py verify_transfer.py`,或 Scripting 工作区 Run Script),
得到 `//_anim_transfer_baseline.json`(相对 `//` = 工程文件目录)。

> 不录基线就无法证明"运动没变" —— 这是本方案唯一的验收依据。

### 2. 执行转移

编辑 `transfer_anim.py` 顶部:
```python
TARGET = '摄像机x02_151-370'   # 要转移动态的对象
FRAME = 151                    # 参考帧(取目标当前位姿做快照);None = 场景起始帧
ZERO_TARGET = True             # True: 插基点空对象,把本体本地变换归零(推荐)
DRIVER_NAME = None             # None = f'{TARGET}_动态'
BASE_NAME = None               # None = f'{TARGET}_基点'
KEEP_BACKUP = True             # 旧 action 加假用户留作备份
```
运行 `python send.py transfer_anim.py`。

脚本内置前置自检(与目标在参考帧世界位姿不一致就中止)与后置粗检;
**Ctrl+S 存盘**(桥只改内存)。

### 3. 转移后: 逐帧对基线

把 `verify_transfer.py` 的 `MODE` 改成 `'check'`,再跑一次:
```
位置分量最大偏差   : 7.629e-06 @f308
旋转块元素最大偏差 : 1.192e-07 @f166
角度最大偏差       : 1.741e-05 度 @f175
判定: ✅ 通过 —— 世界运动逐帧不变(float32 精度级)
```

判读阈值(场景坐标量级 ~25 单位):

| 指标 | 通过阈值 | 正常实测 |
|---|---|---|
| 位置分量最大偏差 | ≤ 1e-5 单位 | ~1e-6 量级(≈2 ulp) |
| 旋转块元素最大偏差 | ≤ 1e-6 | ≤ 1.19e-07(= float32 eps) |
| 角度最大偏差 | ≤ 1e-4 度 | ~1e-5 度 |

## 注意事项(踩过的坑)

1. **⚠️ `obj.parent` 赋值会把 `matrix_parent_inverse` 重置为单位矩阵!**
   必须**先设 `parent`、再设 `matrix_parent_inverse`**;写反了会被静默清掉
   (症状: 对象飞到别处、MPI 平移回读为 `(0,0,0)`)。隔离实验逐项验证过:

   | 操作 | MPI 是否被重置 |
   |---|---|
   | 设 MPI → 再赋 `obj.parent` | **是,变 (0,0,0)** |
   | 赋 `obj.parent` → 再设 MPI | 否 ✅ |
   | 赋 `parent_type` / `animation_data_clear()` / 写 loc·rot·scale / `frame_set()` | 否 |

2. **新建/改动对象后必须 `view_layer.update()` 再读 `matrix_world`**:否则读到单位矩阵,
   算出来的 `matrix_parent_inverse` 是 identity,子对象世界坐标翻倍偏移。
3. **复制 action 只搬"被关键帧覆盖的通道"**:没被覆盖的通道(`location[0]/[1]` 等)取的是
   **目标对象自己的静态 basis** → 所以 D 的静态 basis 必须与目标在参考帧的快照一致,
   脚本已自动快照(`_snapshot`/`_apply`,含 `delta_*`)。
4. **5.2 Slotted Action 复制后必须显式绑 slot**(`ad.action_slot = act.slots[0]`),
   否则曲线挂着却不生效。
5. **`animation_data_clear()` 不进 undo 栈**:旧 action 默认加假用户(`use_fake_user=True`)
   留作孤儿备份,可随时把 `ad.action` 指回去还原。
6. **不要删旧 action 数据块**:保留成假用户孤儿即可,删了就真没了。
7. **验收别用 `2*acos(dot)` 算角度**:`dot≈1` 时 acos 病态放大,实测会把 3.8e-06 的矩阵差
   虚报成 **0.04°**(放大 100+ 倍),误判成"有漂移"。用旋转矩阵元素最大差,或良态式
   `2*asin(sqrt(x²+y²+z²))`。(`mathutils.Quaternion` **没有 `.vector` 属性**,用 `.x/.y/.z`)
8. **同一次 exec 内"改完立即验证"会读到未刷新值**:验证一律另开一次请求(或重开文件)。
9. 目标若有**约束(constraint)/驱动(driver)/NLA**,本脚本只搬 action,不搬这些 —— 脚本会打印警告。
10. 参考帧 `FRAME` 建议取**父级 Z 旋转为 0 的那一帧**(局部==世界),快照最干净;
    但 `ZERO_TARGET=True` 下 `FRAME` 只影响快照取值,数学上任意帧都成立。

## 调试建议

- 验证不通过 → 依次查: ①基线是不是转移前录的 ②参考帧 F 是否与录基线时一致
  ③目标是否真的 `animation_data=None` ④层级是否符合预期(`_动态`→`_基点`→本体)
- 想还原 → 把本体挂回原父级、`matrix_parent_inverse` 设回原值、把备份 action 指回去
  (或直接 `Ctrl+Z` / 重新打开存盘前的 .blend)
- 想改运动 → **改 `_动态` 空对象的 action**,不要碰本体
