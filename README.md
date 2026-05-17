# Local_Pan
<img width="1555" height="1014" alt="image" src="https://github.com/user-attachments/assets/a6d5a495-e21d-4830-ba18-0c674f661d5d" />

## 简介

Local_Pan 是一个基于 Web 的文件管理系统，支持文件浏览、上传、下载、管理、分享以及多种协议共享（WebDAV、FTP、Samba）。

## 功能特性

- **文件管理**: 浏览、上传、下载、创建文件夹、重命名、删除
- **文件分享**: 生成分享链接，与他人共享文件
- **文件夹锁定**: 锁定文件夹，保护隐私内容
- **WebDAV 支持**: 通过 WebDAV 协议访问文件（支持 HTTP 和 HTTPS）
- **FTP 支持**: 通过 FTP 协议访问文件
- **Samba 支持**: 通过 SMB 协议访问文件（局域网共享）
- **HTTPS 支持**: 可配置 SSL 证书启用安全连接
- **用户认证**: Basic Auth 认证机制
- **搜索功能**: 快速搜索文件
- **日志记录**: 自动记录操作日志
- **多端口服务**: 支持 HTTP/HTTPS 以及 WebDAV HTTP/HTTPS



## 快速开始

**默认登录凭证:**
- 用户名: `admin`
- 密码: `123456`
- 应用启动后访问: `http://localhost:8080`


### 方式一：直接运行

```bash
#环境： Python 3.10+

#安装依赖
pip install -r requirements.txt

#运行脚本
python app.py
```

### 方式二：Docker部署 
- 使用bridge端口映射模式 （docker compose文件本地构建或docke pull 拉取镜像）
```yml
version: '3.8'

services:
  local_pan:
    build: .
    image: ffingcn/local_pan:1.0.0
    container_name: local_pan
    restart: unless-stopped
    ports:
      - "8080:8080"
      - "8443:8443"
      - "5001:5001"
      - "5002:5002"
      - "21:21"
      - "445:445"
      - "50000-50050:50000-50050"
    volumes:
      - ./uploads:/app/uploads
      - ./config:/app/config
      - ./logs:/app/logs
      - ./ssl:/app/ssl
      - ./img:/app/img
    environment:
      - TZ=Asia/Shanghai
    networks:
      - local_pan_net
    privileged: true


networks:
  local_pan_net:
    driver: bridge

```


- host网络模式，注意端口占用情况（docker compose文件本地构建或docke pull 拉取镜像）
```yml
version: '3.8'

services:
  local_pan:
    build: .
    image: ffingcn/local_pan:1.0.0
    container_name: local_pan
    restart: unless-stopped
    # 使用 host 网络模式（与宿主机共享网络，无需端口映射）
    network_mode: host
    volumes:
      - ./uploads:/app/uploads
      - ./config:/app/config
      - ./logs:/app/logs
      - ./ssl:/app/ssl
      - ./img:/app/img
    environment:
      - TZ=Asia/Shanghai
    privileged: true
```




## 默认配置

| 配置项 | 默认值 |
|--------|--------|
| 用户名 | admin |
| 密码 | 123456 |
| HTTP 端口 | 8080 |
| HTTPS 端口 | 8443 |
| WebDAV HTTP 端口 | 5001 |
| WebDAV HTTP 端口 | 5002 |
| FTP 端口 | 21 |
| FTP 被动端口范围 | 50000-50050 |
| Samba 端口 | 445 |
| 网络名称 | Local_Pan |


## 使用指南

### 登录

访问首页后，系统会弹出登录框。输入用户名和密码进行登录。

### 文件浏览

- 登录后显示上传文件夹的内容
- 点击文件夹可进入查看
- 点击"上级目录"可返回上一层

### 上传文件

1. 点击"上传"按钮
2. 选择要上传的文件
3. 文件将上传到当前目录

### 创建文件夹

1. 点击"新建文件夹"按钮
2. 输入文件夹名称
3. 点击确认创建

### 重命名

1. 选中要重命名的文件或文件夹
2. 点击"重命名"按钮
3. 输入新名称并确认

### 删除

1. 选中要删除的文件或文件夹
2. 点击"删除"按钮
3. 确认删除操作

### 搜索

1. 在搜索框中输入关键词
2. 系统将搜索所有匹配的文件和文件夹
3. 点击结果可直接访问

### 下载

点击文件名旁的下载图标即可下载文件

### 文件分享

创建分享链接与他人共享文件：

1. 选中要分享的文件
2. 点击"分享"按钮
3. 系统会生成一个永久分享链接
4. 复制链接发送给他人即可访问

**注意事项**：
- 仅支持分享文件，不支持分享文件夹
- 分享链接无需登录即可访问
- 可在分享列表中管理所有分享链接
- 可删除分享链接取消分享

### 文件夹锁定

锁定文件夹以保护隐私内容：

1. 选中要锁定的文件夹
2. 点击"锁定"按钮
3. 文件夹将被锁定

**锁定效果**：
- 未登录用户无法查看锁定文件夹的内容
- 锁定文件夹不会在文件列表中显示（未登录状态）
- 登录后可以正常访问锁定文件夹
- 可随时解锁文件夹

### 清理隐藏文件

批量删除以点开头的隐藏文件（如 .DS_Store、.thumbs.db 等）：

1. 点击"清理隐藏文件"按钮
2. 系统会扫描并删除所有隐藏文件
3. 显示删除结果

## WebDAV 访问

### HTTP WebDAV

访问 `http://localhost:5001/webdav/`

### HTTPS WebDAV

配置 SSL 证书并启用 HTTPS WebDAV 后，可通过 `https://localhost:5002/webdav/` 访问

### 使用 WebDAV 客户端

Windows:
```
net use Z: \\localhost@5001\davwwwroot /user:admin 123456
```

macOS:
```
mount -t webdav http://localhost:5001/webdav /Volumes/LocalPan
```

## FTP 访问

### 启用 FTP

在系统设置中启用 FTP 服务。

### FTP 客户端连接

- **服务器**: localhost
- **端口**: 21
- **用户名**: admin
- **密码**: 123456
- **被动模式**: 启用

### 使用命令行连接

```bash
ftp localhost
```

## Samba 访问

### 启用 Samba

在系统设置中启用 Samba 服务。

### Windows 访问

```
\\localhost\share
```

### macOS 访问

```
smb://localhost/share
```

### Linux 访问

```bash
mount -t cifs //localhost/share /mnt/localpan -o username=admin,password=123456
```

## Docker 部署

### 使用 docker-compose

```bash
docker-compose up -d
```

### 端口映射

| 端口 | 服务 |
|------|------|
| 8080 | HTTP Web 服务 |
| 8443 | HTTPS Web 服务 |
| 5001 | WebDAV HTTP |
| 5002 | WebDAV HTTPS |
| 21 | FTP |
| 445 | Samba |
| 51000-52000 | FTP 被动端口 |

### 数据持久化

- `./uploads` - 上传文件目录
- `./config` - 配置文件目录
- `./logs` - 日志文件目录
- `./ssl` - SSL 证书目录

## 系统配置

点击右上角设置图标进入系统配置页面

### 可配置项

- **HTTP 端口**: Web 服务监听端口
- **HTTPS 端口**: HTTPS 服务端口
- **启用 HTTPS**: 开启安全连接
- **WebDAV HTTP 端口**: WebDAV 服务端口
- **WebDAV HTTPS 端口**: WebDAV HTTPS 端口
- **启用 WebDAV HTTPS**: 开启 WebDAV 安全连接
- **FTP 启用**: 开启 FTP 服务
- **FTP 端口**: FTP 服务端口
- **FTP 被动端口范围**: FTP 被动模式端口范围
- **Samba 启用**: 开启 Samba 服务
- **Samba 端口**: Samba 服务端口
- **用户名/密码**: 登录凭据
- **网络名称**: 页面显示的网络名称
- **站点 Logo**: 自定义 Logo 路径
- **SSL 证书**: HTTPS 证书文件路径
- **SSL 密钥**: HTTPS 密钥文件路径
- **版权年份**: 页脚版权年份
- **版权域名**: 页脚版权域名

### 注意事项

- 修改端口后需要重启服务生效
- 修改密码后需要重新登录
- 启用 HTTPS 需要同时配置 SSL 证书和密钥
- 启用 HTTPS WebDAV 需要配置 WebDAV HTTPS 端口、SSL 证书和密钥
- Logo 文件需放置在 img 目录下
- FTP 被动端口范围需要在防火墙和 Docker 中开放

## 安全机制

### 登录锁定

连续 3 次密码输入错误后，账户将被锁定 300 秒（5 分钟）

### 路径安全

所有文件操作都限制在上传目录内，防止目录遍历攻击

### 文件夹锁定

锁定后的文件夹对未登录用户不可见，保护隐私内容

## 日志功能

系统会自动记录操作日志，包括：

- 用户登录
- 文件上传/下载
- 文件/文件夹创建、删除、重命名
- 分享操作
- 文件夹锁定/解锁
- 配置修改
- WebDAV 操作
- FTP 操作
- Samba 操作

日志文件存储在 `logs/` 目录下，按日期自动轮转，保留最近 7 天的日志。

## API 接口说明

### 基础信息

所有 API 接口均位于 `/api/` 路径下，部分接口需要 Basic Auth 认证（用户名：admin，密码：123456）。

### 接口列表

#### 1. 用户认证

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/login` | 是 | 验证用户名密码 |

**请求示例**：
```bash
curl -u admin:123456 http://localhost:8080/api/login
```

**响应示例**：
```json
{"success": true}
```

#### 2. 文件操作

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/files?path=<路径>` | 否 | 获取目录文件列表 |
| GET | `/api/search?keyword=<关键词>&limit=<数量>` | 否 | 搜索文件 |
| POST | `/api/upload` | 是 | 上传文件 |
| GET | `/api/download?path=<路径>` | 否 | 下载文件 |
| POST | `/api/mkdir` | 是 | 创建文件夹 |
| POST | `/api/mkdirs` | 是 | 创建多级文件夹 |
| DELETE | `/api/delete?path=<路径>` | 是 | 删除文件/文件夹 |
| POST | `/api/rename` | 是 | 重命名文件/文件夹 |

**获取文件列表**：
```bash
curl http://localhost:8080/api/files?path=/documents
```

**搜索文件**：
```bash
curl "http://localhost:8080/api/search?keyword=report&limit=20"
```

**上传文件**：
```bash
curl -u admin:123456 -X POST -F "file=@test.txt" -F "path=/" http://localhost:8080/api/upload
```

**创建文件夹**：
```bash
curl -u admin:123456 -X POST -H "Content-Type: application/json" \
  -d '{"path": "/", "name": "new_folder"}' \
  http://localhost:8080/api/mkdir
```

**重命名**：
```bash
curl -u admin:123456 -X POST -H "Content-Type: application/json" \
  -d '{"path": "/old_name.txt", "new_name": "new_name.txt"}' \
  http://localhost:8080/api/rename
```

#### 3. 文件分享

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/share/<token>/<filename>` | 否 | 通过分享链接下载文件 |
| GET | `/api/shares` | 否 | 获取所有分享列表 |
| POST | `/api/shares` | 是 | 添加分享链接 |
| DELETE | `/api/shares/<token>` | 是 | 删除单个分享 |
| DELETE | `/api/shares` | 是 | 批量删除分享 |

**添加分享**：
```bash
curl -u admin:123456 -X POST -H "Content-Type: application/json" \
  -d '{"token": "abc123", "path": "/documents/report.pdf"}' \
  http://localhost:8080/api/shares
```

**批量删除分享**：
```bash
curl -u admin:123456 -X DELETE -H "Content-Type: application/json" \
  -d '{"tokens": ["abc123", "def456"]}' \
  http://localhost:8080/api/shares
```

#### 4. 文件夹锁定

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/lock` | 是 | 锁定文件夹 |
| POST | `/api/unlock` | 是 | 解锁文件夹 |

**锁定文件夹**：
```bash
curl -u admin:123456 -X POST -H "Content-Type: application/json" \
  -d '{"path": "/private"}' \
  http://localhost:8080/api/lock
```

**解锁文件夹**：
```bash
curl -u admin:123456 -X POST -H "Content-Type: application/json" \
  -d '{"path": "/private"}' \
  http://localhost:8080/api/unlock
```

#### 5. 系统管理

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/api/config` | 是 | 获取系统配置 |
| POST | `/api/config` | 是 | 更新系统配置 |
| GET | `/api/public-config` | 否 | 获取公共配置 |
| GET | `/api/status` | 否 | 获取服务状态 |
| POST | `/api/restart` | 是 | 重启服务 |
| POST | `/api/restart-service` | 是 | 重启子服务 |
| GET | `/api/check-port?port=<端口>` | 否 | 检查端口占用 |
| POST | `/api/cleanup-hidden` | 是 | 清理隐藏文件 |

**获取配置**：
```bash
curl -u admin:123456 http://localhost:8080/api/config
```

**检查端口**：
```bash
curl "http://localhost:8080/api/check-port?port=8080"
```

**清理隐藏文件**：
```bash
curl -u admin:123456 -X POST http://localhost:8080/api/cleanup-hidden
```

### 响应格式

成功响应：
```json
{"success": true, ...}
```

失败响应：
```json
{"error": "错误信息"}
```

### 认证方式

需要认证的接口使用 HTTP Basic Auth：
- 用户名：`admin`（默认）
- 密码：`123456`（默认）

## 文件目录结构

```
/uploads/          # 文件上传目录
/config/           # 配置文件目录
  - config.json    # 系统配置
  - locks.json     # 文件夹锁定记录
  - shares.json    # 分享链接记录
/ssl/              # SSL 证书目录
/static/           # 静态资源目录
/templates/        # 模板文件目录
/img/              # 图片目录
/logs/             # 日志文件目录
/sub_py/           # 子服务模块
  - web_server.py  # Web 服务
  - webdav_server.py # WebDAV 服务
  - ftp_server.py  # FTP 服务
  - samba_server.py # Samba 服务
```

## 常见问题

### 忘记密码怎么办？

修改 `config/config.json` 文件中的 `password` 字段，重启服务即可。

### 如何启用 HTTPS？

1. 准备 SSL 证书文件（.crt）和密钥文件（.key）
2. 将文件放置在 `ssl/` 目录下
3. 在设置页面填写证书和密钥路径
4. 勾选"启用 HTTPS"
5. 保存设置，服务会自动重启

### 分享链接无法访问？

- 检查分享链接是否已被删除
- 确认分享的文件是否仍然存在
- 检查文件是否在锁定的文件夹内

### WebDAV 连接失败？

- 确认 WebDAV 服务已启用
- 检查端口是否被占用
- 确认用户名和密码正确
- 如使用 HTTPS，确保证书配置正确

### FTP 连接失败？

- 确认 FTP 服务已启用
- 检查端口 21 是否被占用
- 确认 FTP 被动端口范围（50000-50050）已开放，端口范围可以自定义
- 确认防火墙设置

### Samba 无法访问？

- 确认 Samba 服务已启用
- 检查端口 445 是否被占用
- 确认防火墙设置
- Docker 部署需启用 privileged 模式
