# deepseekflow-api

解决本地部署 deepseek-r1 流式输出没有符合官方思考流式格式的问题，对 API 进行符合要求的流式处理，对特殊标记（`<think>`/`</think>`）进行处理

## 开发

### 环境要求

Python 3.11+

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

Linux/Mac

```bash
cp start.sh.template start.sh
chmod +x start.sh
./start.sh
```

Windows

```powershell
Copy-Item start.ps1.template start.ps1
.\start.ps1
```

## 部署

拉取基础镜像后打包，运行时修改`UPSTREAM_API_URL`为你的R1地址。然后请求启动服务的地址，默认45677

```
make build
make up
```

## 效果

测试应用为FastGPT

![image-20250216161349170](D:\Desktop\deepseekflow-api\assets\image-20250216161349170.png)

## 总体流程

1. 客户端发送聊天请求到 `/v1/chat/completions` 接口，包含模型名称、流式选项和消息内容。

2. 服务器验证请求并将其转发至上游模型 API（如：`http://127.0.0.1:8000/v1/chat/completions`）。

3. 接收上游模型的流式响应，并解析返回的 JSON 数据。

4. 处理特殊标记（`<think>`/`</think>`），区分普通内容和推理内容。

5. 将处理后的数据转换为 SSE 格式，实时推送给客户端，同时确保异常情况下的错误处理。
