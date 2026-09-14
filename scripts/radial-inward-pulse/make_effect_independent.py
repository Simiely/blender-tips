# -*- coding: utf-8 -*-
"""发射灯/收缩射灯/收缩灯 空对象名下的共享网格数据 → 按对象独立化（v2，先快照后动手）

v1 的两个 bug（都实测踩到）：
  ① 一边复制一边判 `users>1`：前面的复制把 users 掉到 1 ⇒ 后面共用同份数据的兄弟被跳过
     ⇒ 正解：先按数据块分组做【快照】，被共享的组里【每个对象都无条件复制】
  ② 关键词只匹配了 发射灯/收缩灯，漏了【收缩射灯效果】这种写法 ⇒ 整组漏处理
"""
import bpy
import collections

D = bpy.data
C = bpy.context
KEYS = ["发射灯", "收缩射灯", "收缩灯"]
log = []
fails = []


def chk(cond, msg):
    (log if cond else fails).append(("  ok " if cond else "  xx ") + msg)


def walk(o, acc):
    for ch in o.children:
        acc.append(ch)
        walk(ch, acc)


# ---------- 收集
groups = collections.defaultdict(list)
for o in D.objects:
    if o.type == 'EMPTY' and any(k in o.name for k in KEYS):
        key = next(k for k in KEYS if k in o.name)
        groups[key].append(o)
log.append("匹配到的空对象：")
for k, lst in groups.items():
    log.append("  [%s] %d 个: %s" % (k, len(lst), [o.name for o in lst]))

targets = []
seen_obj = set()
for k, lst in groups.items():
    for o in lst:
        acc = [o]
        walk(o, acc)
        for x in acc:
            if x.type == 'MESH' and x.data is not None and x.name not in seen_obj:
                seen_obj.add(x.name)
                targets.append((k, o.name, x))
log.append("名下网格对象 %d 个（去重后）" % len(targets))

# ---------- 快照：按数据块分组（先快照，后动手）
snap = collections.defaultdict(list)
for k, on, ob in targets:
    snap[ob.data.name].append((k, on, ob))
to_copy = []
for dname, lst in snap.items():
    if len(lst) > 1:
        to_copy.extend(lst)          # ★ 整组无条件复制（不看当下 users）
log.append("快照：%d 个对象 / %d 份网格数据；被共享的数据 %d 份 ⇒ 需独立化对象 %d 个"
           % (len(targets), len(snap),
              sum(1 for v in snap.values() if len(v) > 1), len(to_copy)))

# ---------- 动手
n = 0
for k, on, ob in to_copy:
    me = ob.data
    if me.users > 1:                 # 幂等：已经独立的不再复制
        ob.data = me.copy()
        n += 1
log.append("本轮实际复制 %d 份" % n)

C.view_layer.update()

# ---------- 复核
after = collections.defaultdict(list)
for k, on, ob in targets:
    after[ob.data.name].append(ob.name)
shared_after = {k_: v for k_, v in after.items() if len(v) > 1}
chk(not shared_after, "★ 复核：这 %d 个对象之间已无任何网格数据共享（仍共享 %s）"
    % (len(targets), shared_after or "无"))
not1 = [ob.name for _k, _on, ob in targets if ob.data.users != 1]
chk(not not1, "★ 每个对象的网格数据 users == 1（例外 %s）" % not1 or "无")
lost = [on for _k, on, ob in targets if len(ob.material_slots) == 0]
chk(not lost, "材质槽全保留（空槽 %s）" % lost or "无")

# 各组统计
log.append("")
for k, lst in groups.items():
    cnt = collections.Counter()
    for o in lst:
        acc = [o]
        walk(o, acc)
        for x in acc:
            if x.type == 'MESH' and x.data:
                cnt[x.data.users] += 1
    log.append("  [%s] 名下网格数据的 users 分布 = %s" % (k, sorted(cnt.items())))

log.append("")
log.append("对象 %d | 网格数据 %d" % (len(D.objects), len(D.meshes)))

print("\n".join(log))
print()
print("FAILS=%d" % len(fails))
for f in fails:
    print(f)
