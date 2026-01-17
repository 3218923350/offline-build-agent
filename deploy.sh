#!/bin/bash
# 快速启动脚本

set -e

echo "离线构建 Agent 部署脚本"
echo "======================="

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "创建 .env 文件..."
    cp env.example .env
    echo "请编辑 .env 文件并填入 API Keys"
    exit 1
fi

# 加载环境变量
source .env

# 检查必要的环境变量
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "sk-your-key-here" ]; then
    echo "错误: 请在 .env 中设置 OPENAI_API_KEY"
    exit 1
fi

if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your-key-here" ]; then
    echo "错误: 请在 .env 中设置 GEMINI_API_KEY"
    exit 1
fi

# 创建网络命名空间
echo "创建网络命名空间..."
sudo ip netns add offline 2>/dev/null || echo "网络命名空间已存在"

# 选择部署方式
echo ""
echo "选择部署方式:"
echo "1) Docker Compose (推荐)"
echo "2) 直接运行"
echo "3) 仅安装依赖"
read -p "请选择 (1-3): " choice

case $choice in
    1)
        echo "使用 Docker Compose 部署..."
        docker-compose up --build -d
        echo ""
        echo "✅ 服务已启动"
        echo "API 地址: http://localhost:8000"
        echo "查看日志: docker-compose logs -f"
        echo "停止服务: docker-compose down"
        ;;
    2)
        echo "直接运行..."
        if [ ! -d "venv" ]; then
            echo "创建虚拟环境..."
            python3 -m venv venv
        fi
        source venv/bin/activate
        echo "安装依赖..."
        pip install -r requirements.txt -r requirements-api.txt
        pip install -e .
        echo ""
        echo "启动 API 服务..."
        python -m uvicorn offline_builder.api:app --host 0.0.0.0 --port 8000
        ;;
    3)
        echo "安装依赖..."
        if [ ! -d "venv" ]; then
            python3 -m venv venv
        fi
        source venv/bin/activate
        pip install -r requirements.txt
        pip install -e .
        echo ""
        echo "✅ 依赖安装完成"
        echo "运行 CLI: offline-build --input examples/example_tools.json"
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac

