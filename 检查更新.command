#!/bin/bash

# ============================================
# 切换到脚本所在的目录
# ============================================
cd "$(dirname "$0")" || exit 1

# ============================================
# 检查更新脚本 - 支持 ZIP 下载和 Git Clone 两种方式
# ============================================

echo "=========================================="
echo "   📦 检查更新中..."
echo "=========================================="
echo ""

# 检查网络连接
check_network() {
    ping -c 1 -W 3 github.com > /dev/null 2>&1
    return $?
}

# 尝试用不同方式获取更新
try_fetch() {
    local url=$1
    echo "🔄 尝试连接: $url"
    
    # 移除可能已存在的 remote
    git remote remove origin 2>/dev/null
    
    # 添加远程仓库
    git remote add origin "$url"
    
    # 尝试获取
    git fetch origin main --quiet 2>/dev/null
    return $?
}

# 检查是否是 Git 仓库
if [ ! -d ".git" ]; then
    echo "⚠️  检测到这是通过 ZIP 下载的版本"
    echo ""
    echo "🔄 正在初始化 Git 仓库以便支持更新..."
    echo ""
    
    # 初始化 Git 仓库
    git init
    
    # 尝试多个镜像源
    echo "🌐 正在连接服务器..."
    echo ""
    
    # 定义镜像源列表
    MIRRORS=(
        "https://github.com/fbb0718/ehafo-medical-video-toolkit1.git"
        "https://hub.fastgit.xyz/fbb0718/ehafo-medical-video-toolkit1.git"
        "https://ghproxy.com/https://github.com/fbb0718/ehafo-medical-video-toolkit1.git"
    )
    
    SUCCESS=0
    for mirror in "${MIRRORS[@]}"; do
        if try_fetch "$mirror"; then
            SUCCESS=1
            echo ""
            echo "✅ 连接成功！"
            break
        fi
        echo "   ❌ 连接失败，尝试下一个..."
        echo ""
    done
    
    if [ $SUCCESS -eq 1 ]; then
        # 强制拉取最新版本（覆盖本地文件）
        git reset --hard origin/main
        
        echo ""
        echo "✅ 已更新到最新版本！"
        echo ""
        echo "📌 当前版本日期: $(git log -1 --format=%cd --date=short 2>/dev/null || echo '未知')"
        echo ""
        read -p "按任意键退出..."
        exit 0
    else
        echo ""
        echo "=========================================="
        echo "❌ 所有连接方式均失败"
        echo "=========================================="
        echo ""
        echo "💡 可能的原因："
        echo "   1. 网络连接不稳定"
        echo "   2. 需要代理才能访问 GitHub"
        echo ""
        echo "📥 请手动前往 GitHub 下载最新 ZIP："
        echo "   https://github.com/fbb0718/ehafo-medical-video-toolkit1"
        echo ""
        echo "🔧 或者使用以下命令克隆（如果网络正常）："
        echo "   git clone https://github.com/fbb0718/ehafo-medical-video-toolkit1.git"
        echo ""
        read -p "按任意键退出..."
        exit 1
    fi
fi

# 以下是原有的 Git 仓库更新逻辑
# 获取当前版本
CURRENT_VERSION=$(git log -1 --format=%cd --date=short 2>/dev/null || echo "未知")
echo "📌 当前版本日期: $CURRENT_VERSION"

# 获取远程最新版本信息
echo ""
echo "🔄 正在连接服务器..."

# 检查网络
if ! check_network; then
    echo ""
    echo "⚠️  网络似乎不稳定，尝试使用镜像源..."
    
    # 尝试用镜像源更新
    git remote set-url origin https://hub.fastgit.xyz/fbb0718/ehafo-medical-video-toolkit1.git 2>/dev/null
    REMOTE_INFO=$(git ls-remote origin HEAD 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        # 恢复原始地址
        git remote set-url origin https://github.com/fbb0718/ehafo-medical-video-toolkit1.git 2>/dev/null
        echo ""
        echo "❌ 网络连接失败，请检查网络后重试"
        echo ""
        read -p "按任意键退出..."
        exit 1
    fi
else
    REMOTE_INFO=$(git ls-remote origin HEAD 2>/dev/null)
fi

REMOTE_HASH=$(echo "$REMOTE_INFO" | cut -f1)
LOCAL_HASH=$(git rev-parse HEAD 2>/dev/null)

echo ""
echo "🔍 比较版本..."

if [ "$LOCAL_HASH" = "$REMOTE_HASH" ]; then
    echo ""
    echo "✅ 当前已是最新版本！"
    echo ""
else
    echo ""
    echo "🆕 发现新版本！"
    echo ""
    echo "=========================================="
    echo "📋 更新日志:"
    echo "=========================================="
    
    git fetch origin --quiet 2>/dev/null
    git log --oneline HEAD..origin/main 2>/dev/null | head -10
    
    if [ $? -ne 0 ]; then
        echo "   (无法获取更新日志，请查看 GitHub)"
    fi
    
    echo ""
    echo "=========================================="
    echo ""
    echo "📥 是否现在更新？(y/n)"
    read -p "请输入: " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "⬇️  正在下载更新..."
        git pull origin main --quiet
        
        if [ $? -eq 0 ]; then
            echo ""
            echo "✅ 更新成功！"
            echo ""
            echo "📌 更新后的版本日期: $(git log -1 --format=%cd --date=short)"
        else
            echo ""
            echo "❌ 更新失败，请检查网络后重试"
        fi
    else
        echo ""
        echo "⏭️  已取消更新"
    fi
fi

echo ""
read -p "按任意键退出..."
