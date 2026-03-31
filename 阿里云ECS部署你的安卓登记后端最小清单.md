# 阿里云 ECS 部署你的安卓登记后端最小清单

## 1. 这次只部署什么

这次先只部署你负责的这部分：

- 安卓端登记接口
- 产区校验
- 商品登记
- 二维码生成

也就是这 4 个接口要能在云上访问：

- `GET /health`
- `GET /api/mobile/bootstrap`
- `POST /api/mobile/validate-location`
- `POST /api/mobile/register-product`

先不管：

- 消费者扫码页
- 管理端大屏
- 其他同学后续要补的接口

---

## 2. 你们最后想达到的效果

现在你们是：

- 电脑开后端
- 手机连电脑热点
- 安卓端访问电脑局域网 IP

部署到阿里云后会变成：

- 阿里云服务器开后端
- 手机直接走公网访问
- 所有人都能用同一个后端测试和生成二维码

---

## 3. 第一步：买一台阿里云 ECS

如果你们是第一次买，按下面选就够了。

### 推荐配置

- 地域：选离你们近一点的，例如华东或华中
- 操作系统：`Ubuntu 22.04`
- 公网 IP：一定要有
- 实例规格：先用轻量一点也行，只要能跑 Python
- 系统盘：20GB 左右够用

### 创建时注意两件事

1. 设置登录方式

推荐直接设置：

- `root` 密码

因为你们是第一次用，先保证能登上服务器。

2. 记住公网 IP

后面安卓端和浏览器都会用到这个地址。

---

## 4. 第二步：开放安全组端口

这是新手最容易漏掉的一步。

你不开放端口，服务器虽然启动了，手机也访问不到。

### 至少开放这两个端口

- `22`
  - 用来 SSH 登录服务器
- `8000`
  - 用来让 FastAPI 对外提供服务

### 操作思路

在阿里云 ECS 控制台里找到这台实例，然后找到：

- 安全组
- 入方向规则

新增两条规则：

1. SSH

- 协议：`TCP`
- 端口范围：`22/22`
- 授权对象：`0.0.0.0/0`

2. 后端服务

- 协议：`TCP`
- 端口范围：`8000/8000`
- 授权对象：`0.0.0.0/0`

注意：

- 比赛阶段为了省事，可以先这样开
- 如果后面想更安全，再把 `22` 改成只允许你自己的公网 IP

---

## 5. 第三步：登录服务器

Windows 可以直接用 PowerShell：

```powershell
ssh root@你的公网IP
```

第一次连接会提示确认，输入：

```text
yes
```

然后输入你设置的密码。

登录成功后，你就进入阿里云服务器了。

---

## 6. 第四步：在服务器上装基础环境

先执行：

```bash
apt update
apt install -y python3 python3-pip python3-venv
```

作用很简单：

- `python3`：跑后端
- `pip`：装依赖
- `venv`：建虚拟环境

---

## 7. 第五步：把项目传到服务器

你可以先用最简单的办法。

假设你把项目传到服务器这个目录：

```bash
/opt/geotrust
```

### 方法一：用 `scp`

在你自己的电脑上执行：

```powershell
scp -r "D:\Users\Administrator\Desktop\计算机设计" root@你的公网IP:/opt/geotrust
```

如果这个路径太大、太慢，也可以只传后端相关目录：

```powershell
scp -r "D:\Users\Administrator\Desktop\计算机设计\backend" root@你的公网IP:/opt/geotrust
```

### 建议

第一次只传：

- `backend/server`
- `backend/database`

就够了。

---

## 8. 第六步：进入后端目录并安装依赖

登录服务器后执行：

```bash
cd /opt/geotrust/backend/server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

这样就把你这部分后端环境装好了。

---

## 9. 第七步：先手动设置最关键的环境变量

这是部署里最关键的一步之一。

当前你们后端返回二维码图片地址和追溯链接时，会用到：

- `BASE_URL`

如果这个地址不对，手机虽然能调接口，但二维码图片和链接会错。

在服务器里执行：

```bash
export BASE_URL=http://你的公网IP:8000
export SIGNING_SECRET=换成一串你自己的随机字符串
export REGISTER_ENABLED=true
export LOCATION_REQUIRED=true
export REJECT_MOCK_LOCATION=true
export REJECT_EMULATOR=true
export REJECT_DEBUGGER=true
```

### 这里最重要的是：

```bash
export BASE_URL=http://你的公网IP:8000
```

比如：

```bash
export BASE_URL=http://47.xxx.xxx.xxx:8000
```

---

## 10. 第八步：启动后端

在服务器的 `backend/server` 目录下执行：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

启动后不要关这个终端，先保持它运行。

如果看到类似：

```text
Uvicorn running on http://0.0.0.0:8000
```

说明服务起来了。

---

## 11. 第九步：先在浏览器里测通

先不要急着跑手机。

先在你自己的电脑浏览器打开：

```text
http://你的公网IP:8000/health
```

如果返回：

```json
{"status":"ok"}
```

说明云服务器上的后端已经能被公网访问。

然后你也可以再试这个地址：

```text
http://你的公网IP:8000/api/mobile/bootstrap
```

如果能看到 JSON，就说明安卓端启动接口也通了。

---

## 12. 第十步：修改安卓端地址

现在要改你安卓端的访问地址。

改这个文件：

- [gradle.properties](D:/Users/Administrator/Desktop/计算机设计/backend/android-app/gradle.properties)

把原来本地热点的地址：

```properties
apiBaseUrl=http://192.168.xx.xx:8000/
```

改成云服务器公网地址：

```properties
apiBaseUrl=http://你的公网IP:8000/
```

比如：

```properties
apiBaseUrl=http://47.xxx.xxx.xxx:8000/
```

然后在 Android Studio 里：

1. `Sync`
2. 重新安装到手机

---

## 13. 第十一步：手机实际测试

这时候手机已经不需要连你电脑热点了。

直接用正常网络测试：

1. 打开 app
2. 看能不能拉到产区列表
3. 点“校验当前位置”
4. 点“提交登记”
5. 看能不能生成二维码

如果二维码也能显示，说明你这部分已经成功迁到阿里云了。

---

## 14. 如果启动成功但手机访问失败，优先查什么

按这个顺序查就行。

### 1. 安全组有没有放开 8000

这是最常见的问题。

### 2. `uvicorn` 是不是用的 `0.0.0.0`

必须是：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

不要写成：

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

### 3. `BASE_URL` 有没有写成公网地址

如果这里错了，二维码相关地址会错。

### 4. 安卓端 `apiBaseUrl` 有没有改对

很多时候后端部署好了，但 app 还在连旧的热点 IP。

### 5. 是否重新安装了 app

只改 `gradle.properties` 不重新安装，手机里的旧包还是旧地址。

---

## 15. 第一次部署成功后，推荐你马上做的两件事

### 1. 固定一份服务器启动命令

把你成功跑通的命令记下来，例如：

```bash
cd /opt/geotrust/backend/server
source .venv/bin/activate
export BASE_URL=http://你的公网IP:8000
export SIGNING_SECRET=你的密钥
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. 发给队友统一测试地址

告诉队友：

- 现在安卓登记后端已经上云
- 统一测试地址是什么
- 大家只需要把 app 里 `apiBaseUrl` 改成这个地址

这样其他人就能直接测你这部分。

---

## 16. 现阶段先不要急着做的事

你现在先不要一上来就折腾这些：

- 域名
- HTTPS
- Docker
- Nginx
- MySQL
- Redis

这些后面都能补。

第一次部署的目标只有一个：

**让你这部分后端稳定在线，大家都能连。**

---

## 17. 你现在最小要完成的实际任务

如果浓缩成最短版，其实就这 8 步：

1. 买阿里云 ECS
2. 开放 `22` 和 `8000`
3. SSH 登录
4. 安装 Python
5. 上传 `backend/server` 和 `backend/database`
6. 安装依赖
7. 设置 `BASE_URL` 和 `SIGNING_SECRET`
8. 启动 `uvicorn` 并把安卓端地址改成公网 IP

做到这里，你这部分就已经能独立跑在云上了。

---

## 18. 官方参考

我写这份清单时主要参考了阿里云官方关于 ECS 安全组和规则的文档：

- Security group rules: https://www.alibabacloud.com/help/en/ecs/user-guide/security-group-rules
- Use security groups: https://www.alibabacloud.com/help/en/ecs/user-guide/manage-security-group-rules
- Security group overview: https://www.alibabacloud.com/help/en/ecs/user-guide/overview-44

这些文档主要确认了：

- ECS 必须通过安全组控制入站流量
- 你们这种场景需要明确放开公网入站端口
- 规则修改会立即影响实例访问
