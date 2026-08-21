# scripts/driver-sky/ · 天空太阳控制驱动(权威脚本目录)

> 本目录是天空太阳驱动方案的**唯一权威脚本**。驱动天空纹理的
> 太阳高度 `sun_elevation` / 太阳角度 `sun_rotation`,统一走命名空间函数版。

**核心逻辑(重启自愈的官方机制)**:驱动表达式引用命名空间函数;函数**源码作为
`sky_driver.py` 文本块随 .blend 保存**;但运行期的 `driver_namespace` 映射不落盘——靠
文本块勾 **Register**(载入自动执行,受 **Auto Run Python Scripts** 控制)在打开文件时
重注册。所以自愈前提 = 文本块是**当前双函数版** + Register + Auto Run 三项。

## ⚠️ 只用这一个脚本,别用旧的

- ✅ **`sky_driver.py`**(推荐,必装):命名空间函数版,注册 `sky_sun_angle()` /
  `sky_sun_elev()`,实时读 `天空控制["太阳角度"/"太阳高度"]` 并转弧度。
  脚本 / UI 改值**都立即生效**;可同时驱动高度 + 旋转。
- ❌ **`build_sky_sun_driver.py`**(旧,禁用):数字驱动版(SINGLE_PROP 直接表达式)。
  有如下坑:脚本内改滑块值不重算(可能读到 0);且会把 `sun_elevation` 驱动**写回常量**
  (如 `.1`=5.73°)导致高度无反应。**不要再用它重建**。

## 用法

1. 建/复用空物体 `天空控制`,加自定义属性:
   - `太阳高度`(度)→ 驱动 `sun_elevation`
   - `太阳角度`(度)→ 驱动 `sun_rotation`
2. 在 Scripting 工作区新建文本块,命名 `sky_driver.py`,粘贴 `sky_driver.py` 内容,
   勾选 **Register**(+ 偏好设置开 **Auto Run Python Scripts**)→ 重开文件自动注册。
3. 给天空纹理 `sun_rotation` / `sun_elevation` 挂 SCRIPTED 驱动,表达式
   `sky_sun_angle()` / `sky_sun_elev()`(挂驱动写法见 `docs/天空太阳高度驱动.md`)。

## 排查(重启后断开优先看这个)

> **重启后最常见的断开原因不是 Auto Run 没开,而是 .blend 内嵌的 `sky_driver.py`
> 文本块是旧版**——只注册了 `sky_sun_angle`,没有 `sky_sun_elev`(旧版脚本不含高度函数)。
> 结果:重启后角度驱动正常、高度驱动红(invalid)。

建议按此顺序检查:

1. **文本块内容是不是当前版**:dump `bpy.data.texts['sky_driver.py'].as_string()`,
   确认同时含 `def sky_sun_angle` 和 `def sky_sun_elev`。缺高度函数 → 用仓库
   `sky_driver.py`(当前权威版)覆盖该文本块,保持 Register 勾选,再 `Ctrl+S`。
2. 命名空间是否注册:`'sky_sun_angle','sky_sun_elev' in bpy.app.driver_namespace` 都应为 True。
3. 驱动是否有效:遍历 `nt.animation_data.drivers`,匹配含 `sun_elevation` / `sun_rotation`
   的条目,看 `driver.is_valid` 与 `driver.expression`。
4. Auto Run 是否开启:偏好设置 **Auto Run Python Scripts** `(use_scripts_auto_execute)`。

> 判定标准(官方):文本块勾 Register 即"载入时自动执行",但受 Auto Run / Trusted Source
> 控制(见 Blender 手册 Scripting & Security)。若被忽略会弹 Allow Execution / Ignore 对话框。

详情报障碍见 `docs/天空太阳高度驱动.md`。