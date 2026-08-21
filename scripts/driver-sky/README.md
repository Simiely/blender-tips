# scripts/driver-sky/ · 天空太阳控制驱动(权威脚本目录)

> 本目录是天空太阳驱动方案的**唯一权威脚本**。驱动天空纹理的
> 太阳高度 `sun_elevation` / 太阳角度 `sun_rotation`,统一走命名空间函数版。

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

## 排查

- 命名空间函数是否注册:`'sky_sun_angle' in bpy.app.driver_namespace` 为 True。
- 驱动是否有效:遍历 `nt.animation_data.drivers`,匹配含 `sun_elevation` / `sun_rotation`
  的条目,看 `driver.is_valid` 与 `driver.expression`。
- 详情报障碍见 `docs/天空太阳高度驱动.md`。