# 后端开发交接文档

## 1. 文档目的

本文档用于明确后端开发的分工边界：
- **已完成部分**：安卓农户端相关的后端接口和数据表（由安卓组负责）
- **待开发部分**：消费者扫码端和管理端相关的后端接口和数据表（由你负责）

---

## 2. 已完成部分（安卓组负责）

### 2.1 已实现接口

#### `GET /api/mobile/bootstrap`
- 作用：安卓端启动时拉取产区列表和配置
- 返回：产区列表、风控策略、系统配置

#### `POST /api/mobile/register-product`
- 作用：安卓端提交商品登记请求
- 功能：
  - 校验定位是否在产区内
  - 校验风控信号（mock定位、模拟器等）
  - 生成 token、签名、二维码
  - 返回登记结果

### 2.2 已建数据表

#### `regions` - 产区表
- 存储合法产区信息
- 包含产区边界（GeoJSON格式）
- 用于产区校验

#### `products` - 商品表
- 存储**通过校验**的商品记录
- 包含产地坐标、token、签名、二维码地址
- 核心溯源数据

#### `register_attempts` - 登记尝试表
- 记录所有登记行为（成功+失败）
- 用于审计和异常分析

---

## 3. 你需要负责的部分

### 3.1 消费者扫码端接口

#### `GET /api/trace/{token}`
查询商品溯源信息

**请求**：
- 路径参数：`token` - 商品唯一标识

**返回字段**：
- `product_id` - 商品ID
- `product_code` - 商品编号
- `product_name` - 商品名称
- `batch_no` - 批次号
- `region_name` - 产区名称
- `producer_name` - 生产者
- `origin_lng` / `origin_lat` - 产地坐标
- `origin_fix_time` - 登记时间
- `scan_count` - 扫码次数
- `first_scan_time` - 首次扫码时间
- `last_scan_time` - 最近扫码时间
- `status` - 商品状态（normal/opened/risky）
- `risk_level` - 风险等级（none/low/medium/high）

#### `POST /api/scan/{token}`
记录一次扫码事件

**请求字段**：
- `scan_lng` / `scan_lat` - 扫码位置（可选）
- `scan_time` - 扫码时间
- `device_info` - 设备信息（可选）

**返回字段**：
- `scan_id` - 扫码记录ID
- `status` - 扫码结果状态
- `message` - 提示文案
- `risk_detected` - 是否检测到异常

---

### 3.2 管理端接口

#### `GET /api/dashboard/summary`
获取总览统计数据

**返回字段**：
- `today_registered` - 今日登记数
- `today_scans` - 今日扫码数
- `today_rejected` - 今日拦截数
- `today_anomalies` - 今日异常数
- `total_products` - 累计商品数
- `total_scans` - 累计扫码数

#### `GET /api/dashboard/events`
获取最近事件日志

**查询参数**：
- `limit` - 返回条数（默认50）
- `event_type` - 事件类型过滤（可选）

**返回字段**：
- `events[]` - 事件列表
  - `event_id` - 事件ID
  - `event_type` - 事件类型（register_success/register_rejected/scan_normal/scan_anomaly）
  - `event_time` - 事件时间
  - `product_code` - 商品编号
  - `location` - 位置信息
  - `message` - 事件描述

#### `GET /api/dashboard/map-data`
获取地图展示数据

**返回字段**：
- `register_points[]` - 登记点位
  - `lng` / `lat` - 坐标
  - `product_code` - 商品编号
  - `region_name` - 产区名称
- `scan_points[]` - 扫码点位
  - `lng` / `lat` - 坐标
  - `product_code` - 商品编号
  - `scan_time` - 扫码时间
- `anomaly_lines[]` - 异常连线
  - `from_lng` / `from_lat` - 起点
  - `to_lng` / `to_lat` - 终点
  - `product_code` - 商品编号
  - `reason` - 异常原因

#### `GET /api/dashboard/trends`
获取趋势图数据

**查询参数**：
- `days` - 天数（默认7天）

**返回字段**：
- `dates[]` - 日期列表
- `register_counts[]` - 每日登记数
- `scan_counts[]` - 每日扫码数
- `anomaly_counts[]` - 每日异常数

---

### 3.3 需要新建的数据表

#### `scan_records` - 扫码记录表
存储消费者每次扫码行为

关键字段：
- `id` - 主键
- `product_id` - 关联商品
- `scan_time` - 扫码时间
- `scan_lng` / `scan_lat` - 扫码位置
- `scan_accuracy` - 位置精度
- `device_info` - 设备信息
- `is_first_scan` - 是否首次扫码
- `distance_from_last` - 距上次扫码距离（米）
- `time_from_last` - 距上次扫码时间（秒）
- `estimated_speed` - 推算移动速度（km/h）
- `risk_level` - 风险等级
- `created_at` - 创建时间

#### `dashboard_events` - 大屏事件表
存储管理端展示的事件日志

关键字段：
- `id` - 主键
- `event_type` - 事件类型
- `event_time` - 事件时间
- `product_id` - 关联商品
- `product_code` - 商品编号
- `location_lng` / `location_lat` - 位置
- `message` - 事件描述
- `severity` - 严重程度（info/warning/error）
- `created_at` - 创建时间

---

## 4. 核心业务逻辑

### 4.1 扫码状态判定

根据 `scan_records` 表的扫码次数判定：
- **0次**：首次扫码，状态 `normal`
- **1次**：已开封，状态 `opened`
- **2次及以上**：重复扫码，需检查异常

### 4.2 异地扫码异常检测

当同一商品被多次扫码时，计算：
1. **距离差**：使用 Haversine 公式计算两次扫码地点的球面距离
2. **时间差**：两次扫码的时间间隔（秒）
3. **推算速度**：距离 ÷ 时间 = 速度（km/h）

**判定规则**：
- 速度 > 800 km/h → 高风险（疑似克隆码）
- 速度 > 300 km/h → 中风险（疑似异常流转）
- 速度 ≤ 300 km/h → 正常

### 4.3 事件日志生成

以下事件需写入 `dashboard_events`：
- 商品登记成功
- 商品登记被拒绝
- 首次扫码
- 重复扫码
- 异常扫码（触发风险）

---

## 5. 数据依赖关系

你的接口需要读取已有的表：
- `products` - 查询商品基础信息
- `regions` - 查询产区名称
- `register_attempts` - 可选，用于统计拦截数据

你的接口需要写入新表：
- `scan_records` - 记录每次扫码
- `dashboard_events` - 记录事件日志

---

## 6. 推荐开发顺序

**第一步**：消费者扫码基础功能
- 实现 `GET /api/trace/{token}`
- 建 `scan_records` 表
- 实现 `POST /api/scan/{token}`
- 实现扫码次数统计

**第二步**：异常检测
- 实现 Haversine 距离计算
- 实现速度判定逻辑
- 实现风险等级返回

**第三步**：管理端统计
- 建 `dashboard_events` 表
- 实现 `GET /api/dashboard/summary`
- 实现 `GET /api/dashboard/events`

**第四步**：管理端地图
- 实现 `GET /api/dashboard/map-data`
- 实现 `GET /api/dashboard/trends`

---

## 7. 技术建议

### 7.1 Haversine 距离计算

```python
from math import radians, sin, cos, sqrt, atan2

def haversine_distance(lng1, lat1, lng2, lat2):
    """计算两点间球面距离（米）"""
    R = 6371000  # 地球半径（米）

    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c
```

### 7.2 扫码状态更新

每次扫码时需要：
1. 查询该商品的上一次扫码记录
2. 计算距离和速度
3. 判定风险等级
4. 更新 `products` 表的扫码统计字段
5. 写入 `scan_records`
6. 如有异常，写入 `dashboard_events`

### 7.3 性能优化

- `scan_records` 表建议对 `product_id` 和 `scan_time` 建索引
- `dashboard_events` 表建议对 `event_time` 建索引
- 管理端接口可考虑缓存（Redis），减少数据库查询

---

## 8. 接口联调说明

你的接口需要的 `token` 由安卓组的 `POST /api/mobile/register-product` 生成。

联调时可以：
1. 先调用安卓组接口生成测试商品
2. 获取返回的 `token`
3. 用该 `token` 测试你的扫码接口

---

## 9. 总结

**你负责的核心功能**：
- 消费者扫码查询和记录
- 异地扫码异常检测
- 管理端统计和可视化数据

**可复用的已有数据**：
- `products` 表（商品基础信息）
- `regions` 表（产区信息）
- `register_attempts` 表（登记拦截数据）

**需要新建的表**：
- `scan_records`（扫码记录）
- `dashboard_events`（事件日志）

有问题随时沟通，接口字段可以根据实际需求微调。
