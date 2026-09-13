# 空物体收敛清理（可复用包）

第三方模型导入的工程里，Outliner 常躺着几千个**空物体层级容器**（`Untitled.*` / `Group-*` / `Line*` / `Arc*` …），
不渲染、不参与动画，只让 Outliner 与选择操作变卡。本包给出**确定做法**：基线快照 → 不动点收敛清理 → 独立核验。

## 一句话原理

```
一个 EMPTY 需要保留  ⟺  它「支撑」某个非 EMPTY 对象
支撑 = a) 直接挂非 EMPTY 子级 / b) 子级里有需保留的 EMPTY
       / c) 被需保留的对象引用 / d) 被外部数据块引用（节点 socket、场景相机、DOF 焦点、粒子 …）
```

**不是只删"无子级"的** —— 删掉一批叶子后中转容器会变成新叶子，必须**迭代到不动点**：

| 方案 | 实删 | 说明 |
|---|---|---|
| 只删当前无子级 | 5006 | 删完"长出" 2026 个新的无子级 EMPTY |
| **迭代到收敛** | **7467** | 级联带出 2461 个纯容器（`Group-*` / `Arc*` / `Line*` 链） |

## 文件清单

| 文件 | 作用 | 运行位置 |
|---|---|---|
| `snapshot_baseline.py` | **① 基线**：清理前计数 → `cleanup_baseline.json` | 桥 `send.py` 或 Scripting 工作区 Run Script |
| `purge_empties.py` | **② 执行**：建继承图 + 引用图 → 不动点求解 → 落名单 → 删除 → 自检 | 同上 |
| `verify_purge.py` | **③ 独立核验**：读磁盘基线与名单做前后对比，出 7 组判定 | 同上（**必须另开一次请求**） |
| `../docs/空物体收敛清理.md` | 完整原理 / 实测数据 / 坑 | 阅读 |
| `../../skills/blender-scene-cleanup/` | 同一套脚本的 AI 作业规范版 | AI 加载 |

## 配置项（三个脚本顶部，**必须一致**）

```python
OUT_DIR = r"C:\path\to\workdir"   # 报告 / 名单 / 基线都写这里，建议 = 本次会话的 blender_control 工作目录
```

## 使用步骤

### 1. 基线

```python
# snapshot_baseline.py
OUT_DIR = r"...\blender_control"
```

`python send.py snapshot_baseline.py` → 产出 `cleanup_baseline.json`（含 `empty_no_child` 等 18 项计数）。

### 2. 执行清理

```python
# purge_empties.py
OUT_DIR = r"...\blender_control"
```

`python send.py purge_empties.py`。典型输出（真实工程，22315 对象）：

```
清理前: 总对象 22315   EMPTY 11775
扫描量: 约束 0 / 修改器 0 / 节点socket 0
不动点 2 轮；保留 4308 个（非 EMPTY 10540 + EMPTY 4308）
可删 EMPTY: 7467
  带 animation_data: 1876   有父级: 6965   有子级(级联): 2461
  按集合: {'Collection': 2490, '烟花灯': 1707, '水晶走廊': 1129, ...}
[核验] 总对象 22315 → 14848     EMPTY 11775 → 4308
       非 EMPTY 10540 → 10540  OK
       MESH 10527 → 10527      OK
       EMPTY 无子级 5006 → 0   OK 已收敛
[1] 名单里仍存在: 0 (应 0)
[2] 无目标约束(悬空): 0
[3] 父级丢失: 0
[4] 保留对象位置漂移: 0
[5] 真缺失贴图: 0  链接库: 0  字体: 0
is_dirty=True  （桥只改内存，需用户 Ctrl+S）
```

> ⏱ **删除耗时 71.88 s**（14848 对象规模）。桥 `exec` 在 Blender **主线程**跑，客户端 **120s 超时**后
> 结果即丢、且后续请求**只排队不执行** ⇒ 报告已逐阶段落盘，超时后直接读磁盘回捞。

### 3. 独立核验（**必须另开一次请求**）

`python send.py verify_purge.py` → `verify_final.txt`。判定口径见下节。

### 4. 收尾

* 提醒用户 **Ctrl+S**（桥只改内存）；不满意 `File > Revert`
* 被删名单 `purge_final_names.txt` 已落盘（`NAME / COLLECTIONS / PARENT / ANCESTOR_CHAIN / CHILDREN / HAS_ANIM`），可回溯
* 还原点：`<工程目录>\_backup\<名>.before-emptypurge.blend`（复制后**比对字节数**）

## 三重安全闸

| 闸 | 内容 |
|---|---|
| 1 | 只删 `ob.type == 'EMPTY'` |
| 2 | 删完**不会有非 EMPTY 对象失去父级**（不动点规则保证） |
| 3 | 删完**不会有保留对象产生悬空引用**（引用图保证） |

**为什么可以放心执行**：删除的永远是叶子链，父→子单向，删子不影响父 ⇒ 世界变换不可能变；
「非 EMPTY 对象数」删前删后**必须完全相等**。

## 实测数据（真实工程 `260910xAx01`）

| 判据 | 结果 |
|---|---|
| 总对象 | 22315 → **14848** |
| EMPTY | 11775 → **4308**（两轮共删 7467） |
| EMPTY 无子级 | 5006 → 2026 → **0**（收敛） |
| 非 EMPTY / MESH / CAMERA | 10540 / 10527 / 13 **逐个不变** |
| 材质 / 集合 | 236 / 10 → 236 / 9（另清空集合一个） |
| 可见几何包围盒 | `min(-1348.71, -428.05, -958.45)` / `max(1348.71, 428.05, 439.90)` **逐位一致** |
| 名单残留 / 悬空约束 / 父级丢失 / 位置漂移 | **0 / 0 / 0 / 0** |
| 真缺失贴图 / 库 / 字体 / 声音 | **0 / 0 / 0 / 0** |

留下来的 4308 个 EMPTY 中 **3064 个直接挂着网格或相机**，其余是支撑这些链条的中转节点。

## 注意事项（踩过的坑）

1. **删除后旧引用立即失效**：`bpy.data.objects.remove()` 之后连 `o.name` 都会抛
   `ReferenceError: StructRNA of type Object has been removed`。
   ⇒ 要用的字段**删除前冻结**成纯值；核验**重新取引用**，绝不复用删除前的列表。
2. **禁止 `bl_rna.properties` 全属性遍历**：22315 对象约 **7 分钟**，必超 120s。改**打靶式**扫描
   （约束 / 修改器指针 / 节点 OBJECT socket / 驱动 targets / 场景相机 / DOF 焦点 / 粒子）→ 12~20s。
3. **`Scene.objects` / `Collection.objects` / `ID.original` 不是引用**（成员关系与副本来源指针），必须排除。
4. **不要在循环里用 `ob.children`**（对全场景 O(n) 重算）⇒ 自己建 `parent.name -> [child]` 映射。
5. **空集合不是空对象**：`bpy.data.collections.remove(col, do_unlink=True)`；`objects=0` 但 `users=1` 的集合要单独问用户。
6. **`users == 0` 存盘不写盘** ⇒ "显式删除"与"存盘丢弃"等价；但**磁盘无副本**的打包数据变孤儿即永久丢失。
7. **判缺失贴图必须带 `not img.packed_file`**，否则"路径失效但已打包"的会被误报。
8. **桥环境没有 `__name__`** ⇒ 脚本结尾禁止 `if __name__ == "__main__"`，无条件 `main()`。
9. **改与验分两次请求**，同一次 `exec` 内改完立即读会读到未刷新缓存。

## 调试建议

* 不动点轮数 > 50 未收敛 → 引用图构建有问题（多半是把成员关系当成引用了）
* 非 EMPTY 对象数变了 → 立即停手，`File > Revert`，检查不动点的 b/c 两条
* 杀不掉性能 → 先确认 `scan_ptr()`（`bl_rna` 细扫）只作用在修改器这类**少量**对象上
* 删完 EMPTY 还很多 → 正常的：剩下的都是挂着几何或支撑几何的中转节点，想再清就是错删
