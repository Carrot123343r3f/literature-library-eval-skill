# 学术论文下载队列 MCP

这是一个本地、受限的 MCP 服务原型，用于：

1. 接收 Gmail 工作流产生的论文标题、DOI 和下载链接；
2. 在学校网络内从允许的主机下载公开可访问的 PDF；
3. 查询队列和下载状态；
4. 读取已下载 PDF 的文本，交给 ChatGPT 做摘要。

它不会处理密码、Cookie、验证码或 MFA，也不会绕过付费墙。需要机构登录的出版社页面应接入单独的本地浏览器适配器，或由用户先在本地浏览器完成登录。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

设置允许下载的主机。没有显式 allow-list 时，服务会拒绝下载：

```powershell
$env:ACADEMIC_MCP_ROOT = "C:\AcademicLibrary"
$env:ACADEMIC_MCP_ALLOWED_HOSTS = "doi.org,link.springer.com,sciencedirect.com,wiley.com"
$env:ACADEMIC_MCP_TRANSPORT = "streamable-http"
python -m paper_download_mcp.server
```

MCP 地址为：`http://127.0.0.1:8000/mcp`。

## 本地测试

```powershell
$env:ACADEMIC_MCP_TRANSPORT = "stdio"
python -m paper_download_mcp.server
```

在 ChatGPT 自定义 MCP App 中注册时，使用你实际部署的、受认证保护的 MCP 地址。ChatGPT 云端不能直接访问 `127.0.0.1`；私有网络部署应使用 OpenAI 支持的 Secure MCP Tunnel，或在符合学校政策的前提下配置其他受控通道。

## 工具

- `add_to_download_queue`
- `list_download_queue`
- `start_download`
- `get_download_status`
- `list_completed_files`
- `read_downloaded_pdf`

当前下载器使用直接 HTTP 下载。它适合公开 PDF 或不需要交互登录的 URL；出版社 SSO、MFA、校园代理和复杂 JavaScript 页面需要后续添加浏览器适配器。

