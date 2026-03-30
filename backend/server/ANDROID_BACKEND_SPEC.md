# 安卓端 x 后端交叉开发规格

## 1. 范围定义

本文档只覆盖你负责的两块交叉内容：

- 安卓农户端登记链路
- 为安卓端服务的后端字段、接口、产区校验逻辑

本文档明确**不覆盖**：

- 消费者 H5 扫码页需要的字段
- 管理端大屏需要的统计、日志、地图连线字段
- 非安卓端专用的后端接口设计

这些内容统一交给对应队友补充，本文件只保留交接边界。

---

## 2. 本阶段目标

先做成一条稳定的可信登记闭环：

1. 安卓端拉取可选产区
2. 农户填写商品信息
3. 安卓端获取定位与基础环境信号
4. 后端校验坐标是否在合法产区内
5. 后端按规则决定接受或拒绝登记
6. 接受后生成商品记录、token、签名、追溯链接、二维码
7. 安卓端展示成功结果或拒绝原因

比赛第一版只保这条链路，不在安卓端阶段引入消费者扫码和管理端统计逻辑。

---

## 3. 安卓端职责

安卓端只做下面这些事：

- 拉取产区列表和基础配置
- 填写商品登记表单
- 申请定位权限
- 获取当前位置、精度、定位来源、定位时间
- 采集基础环境风险信号
- 调用登记接口
- 展示登记结果

安卓端不负责：

- 生成核心签名
- 判定产区是否合法
- 生成二维码核心业务规则
- 保存真实溯源主数据

这些都应放在后端。

---

## 4. 后端职责

后端为安卓端提供三项核心能力：

### 4.1 产区配置

- 返回当前启用的产区列表
- 返回产区展示名、编码、产品类型
- 可选返回地图展示用中心点和边界简图

### 4.2 登记校验

- 校验请求字段完整性
- 校验坐标是否合法
- 校验坐标是否落在产区多边形内
- 汇总安卓端上传的风险信号
- 给出接受或拒绝结果

### 4.3 登记落库

- 成功时写入商品主表
- 记录每次登记尝试
- 生成 token
- 生成服务端签名
- 返回追溯链接与二维码地址

---

## 5. 推荐业务流

### 5.1 启动阶段

安卓端启动后调用：

- `GET /api/mobile/bootstrap`

用途：

- 获取可选产区
- 获取登记页需要的基础配置
- 获取风控提示文案

### 5.2 登记阶段

农户在登记页输入：

- 商品名称
- 批次号
- 产区
- 生产者名称

安卓端随后采集：

- 经度
- 纬度
- 精度
- 定位来源
- 定位时间
- mock 标记
- 调试环境信号
- 模拟器信号
- 开发者选项信号
- 设备基础信息

然后调用：

- `POST /api/mobile/validate-location`
- `POST /api/mobile/register-product`

### 5.3 结果阶段

后端返回两类结果：

- 接受登记：返回商品编号、token、trace_url、qr_code_url
- 拒绝登记：返回拒绝原因码和用户可展示文案

---

## 6. 接口设计

## 6.1 `GET /api/mobile/bootstrap`

### 作用

给安卓端初始化使用，不为其他端承担职责。

### 返回字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `app_name` | string | 是 | 应用展示名 |
| `register_enabled` | boolean | 是 | 当前是否允许登记 |
| `location_required` | boolean | 是 | 是否强制定位 |
| `risk_policy.reject_mock_location` | boolean | 是 | 是否拒绝 mock 定位 |
| `risk_policy.reject_emulator` | boolean | 是 | 是否拒绝模拟器 |
| `risk_policy.reject_debugger` | boolean | 是 | 是否拒绝调试环境 |
| `regions` | array | 是 | 可选产区列表 |
| `regions[].id` | integer | 是 | 产区主键 |
| `regions[].code` | string | 是 | 产区编码 |
| `regions[].name` | string | 是 | 产区名称 |
| `regions[].product_type` | string | 是 | 产品类型 |
| `regions[].province` | string | 否 | 省份 |
| `regions[].city` | string | 否 | 城市 |
| `regions[].center_lng` | number | 否 | 地图中心经度 |
| `regions[].center_lat` | number | 否 | 地图中心纬度 |

### 示例响应

```json
{
  "app_name": "Geo-Trust Farmer",
  "register_enabled": true,
  "location_required": true,
  "risk_policy": {
    "reject_mock_location": true,
    "reject_emulator": true,
    "reject_debugger": true
  },
  "regions": [
    {
      "id": 1,
      "code": "wuchang-rice-core",
      "name": "五常大米核心产区",
      "product_type": "大米",
      "province": "黑龙江省",
      "city": "哈尔滨市",
      "center_lng": 127.157,
      "center_lat": 44.919
    }
  ]
}
```

## 6.2 `POST /api/mobile/register-product`

### 作用

安卓端登记商品的唯一核心接口。

### 请求字段

#### 业务字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `product_name` | string | 是 | 商品名称 |
| `batch_no` | string | 是 | 批次号 |
| `region_id` | integer | 是 | 选中的产区 ID |
| `producer_name` | string | 是 | 生产者名称 |

#### 定位字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `location.lng` | number | 是 | 经度 |
| `location.lat` | number | 是 | 纬度 |
| `location.accuracy` | number | 否 | 精度，单位米 |
| `location.provider` | string | 否 | 定位来源，如 gps/network/fused/amap |
| `location.fix_time` | string | 是 | ISO8601 时间 |

#### 风控字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `risk_flags.is_mock` | boolean | 是 | 是否命中 mock 定位 |
| `risk_flags.is_emulator` | boolean | 是 | 是否疑似模拟器 |
| `risk_flags.is_debugger` | boolean | 是 | 是否检测到调试器 |
| `risk_flags.dev_options_enabled` | boolean | 否 | 是否开启开发者选项 |

#### 设备字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `device.android_id_hash` | string | 是 | 安卓设备标识哈希 |
| `device.brand` | string | 否 | 品牌 |
| `device.model` | string | 否 | 型号 |
| `device.os_version` | string | 否 | 系统版本 |

#### 应用字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `app.version_name` | string | 否 | 版本名 |
| `app.version_code` | integer | 否 | 版本号 |

### 请求示例

```json
{
  "product_name": "五常大米礼盒",
  "batch_no": "2026-03-30-A01",
  "region_id": 1,
  "producer_name": "张三合作社",
  "location": {
    "lng": 127.154321,
    "lat": 44.921234,
    "accuracy": 8.5,
    "provider": "amap",
    "fix_time": "2026-03-30T12:30:15+08:00"
  },
  "risk_flags": {
    "is_mock": false,
    "is_emulator": false,
    "is_debugger": false,
    "dev_options_enabled": false
  },
  "device": {
    "android_id_hash": "a6fb8d3e6d8e1c78b12f...",
    "brand": "Xiaomi",
    "model": "23049RAD8C",
    "os_version": "Android 14"
  },
  "app": {
    "version_name": "0.1.0",
    "version_code": 1
  }
}
```

### 响应字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `accepted` | boolean | 是 | 是否接受登记 |
| `register_result` | string | 是 | 处理结果码 |
| `message` | string | 是 | 给安卓端直接展示的结果文案 |
| `product_id` | integer | 否 | 成功时返回 |
| `product_code` | string | 否 | 成功时返回 |
| `token` | string | 否 | 成功时返回 |
| `trace_url` | string | 否 | 成功时返回 |
| `qr_code_url` | string | 否 | 成功时返回 |
| `region_name` | string | 否 | 成功时返回 |

### `register_result` 枚举

| 值 | 说明 |
|---|---|
| `accepted` | 登记成功 |
| `rejected_outside_region` | 坐标不在产区内 |
| `rejected_mock_location` | 命中 mock 定位 |
| `rejected_device_risk` | 命中模拟器或调试风险 |
| `rejected_invalid_payload` | 请求字段缺失或非法 |
| `rejected_service_disabled` | 当前不允许登记 |

### 成功响应示例

```json
{
  "accepted": true,
  "register_result": "accepted",
  "message": "定位坐标位于五常大米核心产区，登记成功。",
  "product_id": 1001,
  "product_code": "GT202603300001",
  "token": "gt_6f0f66e5bb7f4c4bbabde2f0",
  "trace_url": "https://example.com/trace/gt_6f0f66e5bb7f4c4bbabde2f0",
  "qr_code_url": "https://example.com/qrcodes/gt_6f0f66e5bb7f4c4bbabde2f0.png",
  "region_name": "五常大米核心产区"
}
```

### 拒绝响应示例

```json
{
  "accepted": false,
  "register_result": "rejected_outside_region",
  "message": "当前定位不在合法产区范围内，拒绝生成溯源码。"
}
```

## 6.3 `POST /api/mobile/validate-location`

### 作用

给安卓端在正式提交登记前先做一次位置和基础环境预校验。

### 请求字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `region_id` | integer | 是 | 选中的产区 ID |
| `location.lng` | number | 是 | 经度 |
| `location.lat` | number | 是 | 纬度 |
| `location.accuracy` | number | 否 | 精度，单位米 |
| `location.provider` | string | 否 | 定位来源 |
| `location.fix_time` | string | 是 | ISO8601 时间 |
| `risk_flags.is_mock` | boolean | 是 | 是否命中 mock 定位 |
| `risk_flags.is_emulator` | boolean | 是 | 是否疑似模拟器 |
| `risk_flags.is_debugger` | boolean | 是 | 是否检测到调试器 |
| `risk_flags.dev_options_enabled` | boolean | 否 | 是否开启开发者选项 |

### 返回字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `valid` | boolean | 是 | 是否允许继续登记 |
| `validation_result` | string | 是 | 校验结果码 |
| `message` | string | 是 | 给安卓端展示的文案 |
| `region_name` | string | 否 | 命中的产区名 |
| `in_region` | boolean | 是 | 是否在产区内 |
| `blocked_by_risk` | boolean | 是 | 是否被环境风险拦截 |

### 返回结果码

| 值 | 说明 |
|---|---|
| `accepted` | 可以继续登记 |
| `rejected_outside_region` | 坐标不在产区内 |
| `rejected_mock_location` | 命中 mock 定位 |
| `rejected_device_risk` | 命中模拟器或调试风险 |
| `rejected_invalid_payload` | 请求字段缺失或非法 |
| `rejected_service_disabled` | 当前不允许登记 |

---

## 7. 后端字段与表设计范围

安卓登记链路只需要 3 张表：

- `regions`
- `products`
- `register_attempts`

不在本阶段设计的表：

- 消费者扫码记录表
- 大屏事件日志表
- 大屏统计汇总表

这些统一交给 H5 / 管理端对应同学补充。

---

## 8. 数据表说明

## 8.1 `regions`

用于存合法产区。

关键字段：

- `id`
- `code`
- `name`
- `product_type`
- `province`
- `city`
- `boundary_geojson`
- `center_lng`
- `center_lat`
- `is_enabled`

说明：

- `boundary_geojson` 统一存 Polygon 或 MultiPolygon 的 GeoJSON 字符串
- 第一版后端直接读取该字段并用 `shapely` 做点在多边形内判断

## 8.2 `products`

只保存**通过登记校验后**生成的商品记录。

关键字段：

- `id`
- `product_code`
- `product_name`
- `batch_no`
- `region_id`
- `producer_name`
- `origin_lng`
- `origin_lat`
- `origin_accuracy`
- `origin_provider`
- `origin_fix_time`
- `device_id_hash`
- `device_brand`
- `device_model`
- `device_os_version`
- `app_version_name`
- `app_version_code`
- `risk_is_mock`
- `risk_is_emulator`
- `risk_is_debugger`
- `risk_dev_options_enabled`
- `token`
- `signature`
- `trace_url`
- `qr_code_url`
- `created_at`
- `updated_at`

## 8.3 `register_attempts`

用于记录每次安卓端发起的登记行为，无论成功还是失败都落库。

关键字段：

- `id`
- `product_name`
- `batch_no`
- `region_id`
- `producer_name`
- `request_lng`
- `request_lat`
- `request_accuracy`
- `request_provider`
- `request_fix_time`
- `risk_is_mock`
- `risk_is_emulator`
- `risk_is_debugger`
- `risk_dev_options_enabled`
- `device_id_hash`
- `device_brand`
- `device_model`
- `device_os_version`
- `app_version_name`
- `app_version_code`
- `result`
- `reason_code`
- `reason_message`
- `created_product_id`
- `created_at`

作用：

- 方便联调定位问题
- 方便比赛演示非法打卡被拦截
- 方便后续补大屏时对接异常日志

---

## 9. 产区校验方案

统一采用：

- 存储格式：`GeoJSON`
- 计算方式：`shapely`
- 判定目标：`Point(lng, lat)` 是否落在 `Polygon/MultiPolygon` 内

推荐后端处理顺序：

1. 校验 `region_id` 是否存在且启用
2. 校验经纬度格式是否合法
3. 解析对应产区 `boundary_geojson`
4. 使用 `shapely.shape()` 构建几何对象
5. 使用 `contains()` 或 `covers()` 判断点是否在区域内
6. 不在区域内则直接返回 `rejected_outside_region`

说明：

- 第一版建议用 `covers()`，这样边界点也算合法，避免比赛现场边界误差导致误拒绝

---

## 10. 服务端判定逻辑

推荐顺序：

1. 检查系统是否开放登记
2. 检查必填字段
3. 检查 mock 定位风险
4. 检查模拟器和调试环境风险
5. 检查产区合法性
6. 生成 `product_code`
7. 生成 `token`
8. 生成 `signature`
9. 生成 `trace_url`
10. 生成二维码图片或二维码地址
11. 写入 `products`
12. 写入 `register_attempts`
13. 返回成功结果

失败时也要写 `register_attempts`，但不写 `products`。

---

## 11. 安卓端页面建议

只保留 4 个页面：

### 11.1 启动页

- 拉取 `bootstrap`
- 检查基础网络状态
- 检查定位权限

### 11.2 商品登记页

- 选择产区
- 输入商品名
- 输入批次号
- 输入生产者名称
- 展示当前定位状态
- 展示环境风险状态

### 11.3 提交中状态页

- 展示“正在校验定位与环境”
- 防止重复点击

### 11.4 结果页

成功展示：

- 登记成功文案
- 商品编号
- token
- trace_url
- 二维码

失败展示：

- 被拒原因
- 风险类型
- 重试建议

---

## 12. 安卓端本地模块建议

建议拆成 4 个模块职责：

- `network`
  - Retrofit 接口
  - DTO
  - 错误码映射
- `location`
  - 权限处理
  - 定位采集
  - 精度与时间信息封装
- `device-risk`
  - mock 检测
  - 调试器检测
  - 模拟器检测
  - 开发者选项检测
- `register`
  - 表单状态
  - 提交流程
  - 成功失败页面状态

---

## 13. 你先做的开发顺序

第一步：

- 建数据库表
- 录入一份真实产区测试数据
- 实现 `GET /api/mobile/bootstrap`

第二步：

- 实现 `POST /api/mobile/register-product`
- 打通产区校验
- 打通 token 与二维码生成

第三步：

- 新建安卓工程
- 拉取产区列表
- 实现登记表单
- 实现定位采集
- 联调登记接口

第四步：

- 做拦截文案
- 做失败状态展示
- 补演示用测试数据

---

## 14. 交接给队友的内容

下面这些内容不属于本文档设计范围，需要其他同学补：

### 14.1 交给消费者端 / H5 同学

- 扫码查询接口字段
- 扫码结果状态字段
- 首次扫码 / 重复扫码 / 风险扫码页面字段
- 消费者定位上传字段

### 14.2 交给管理端同学

- dashboard 汇总字段
- 地图点位字段
- 异常连线字段
- 实时日志字段
- 图表统计字段

### 14.3 交给统筹或安全说明同学

- 作品说明书里的安全表述
- 演示脚本中的攻防文案
- PPT 里的业务包装语言

---

## 15. 当前结论

你这部分先不要扩成“全系统后端设计”，只要先保住：

- 安卓端能拉到产区
- 安卓端能上报定位和环境信息
- 后端能做产区校验
- 后端能拒绝非法登记
- 后端能生成 token 和二维码
- 安卓端能稳定展示结果

这条链路打通后，你负责的核心部分就稳了。
