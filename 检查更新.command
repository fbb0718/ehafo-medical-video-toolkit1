#!/bin/bash

# ============================================
# 切换到脚本所在的目录（解决双击运行时路径问题）
# ============================================
cd "$(dirname "$0")" || exit 1

# ============================================
# 检查更新脚本 - 适用于 macOS
# ============================================

echo "=========================================="
echo "   📦 检查更新中..."
echo "=========================================="
echo ""

# 检查是否是 Git 仓库
if [ ! -d ".git" ]; then
    echo "⚠️  这不是 Git 仓库"
    echo ""
    echo "请前往 GitHub 下载最新 ZIP："
    echo "https://github.com/fbb0718/ehafo-medical-video-toolkit1"
    echo ""
    read -p "按任意键退出..."
    exit 1
fi

# 获取当前版本（从最新提交时间读取）
CURRENT_VERSION=$(git log -1 --format=%cd --date=short 2>/dev/null || echo "未知")
echo "📌 当前版本日期: $CURRENT_VERSION"

# 获取远程最新版本信息
echo ""
echo "🔄 正在连接服务器..."

# 尝试获取远程最新提交信息
REMOTE_INFO=$(git ls-remote origin HEAD 2>/dev/null)

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 网络连接失败，请检查网络后重试"
    echo ""
    read -p "按任意键退出..."
    exit 1
fi

# 获取远程最新提交哈希
REMOTE_HASH=$(echo "$REMOTE_INFO" | cut -f1)

# 获取本地当前提交哈希
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
    
    # 获取远程仓库的最新提交信息
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
