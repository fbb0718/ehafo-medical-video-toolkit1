#!/bin/bash

# ============================================
# 一键提交并推送到 GitHub
# ============================================

# 切换到脚本所在的目录
cd "$(dirname "$0")" || exit 1

echo "=========================================="
echo "   📤 准备提交更新..."
echo "=========================================="
echo ""

# 检查是否是 Git 仓库
if [ ! -d ".git" ]; then
    echo "❌ 错误：当前目录不是 Git 仓库"
    echo ""
    read -p "按任意键退出..."
    exit 1
fi

# 查看当前状态
echo "📋 检测到的变化："
echo "------------------------------------------"
git status --short
echo "------------------------------------------"
echo ""

# 检查是否有变化需要提交
if [ -z "$(git status --porcelain)" ]; then
    echo "✅ 没有检测到任何变化，无需提交"
    echo ""
    read -p "按任意键退出..."
    exit 0
fi

# 让用户输入版本号和更新说明
echo "📝 请输入更新说明："
echo "   (例如: v5.5: 修复了视频生成bug)"
echo ""
read -p "> " COMMIT_MSG

# 如果用户没输入，使用默认信息
if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="更新 $(date +%Y-%m-%d_%H:%M:%S)"
fi

echo ""
echo "📦 正在添加所有文件..."
git add .

echo "📦 正在提交..."
git commit -m "$COMMIT_MSG"

# 检查提交是否成功
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 提交失败，请检查是否有冲突"
    echo ""
    read -p "按任意键退出..."
    exit 1
fi

echo ""
echo "📤 正在推送到 GitHub..."
git push

# 检查推送是否成功
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "   ✅ 更新成功！"
    echo "=========================================="
    echo ""
    echo "📌 提交信息: $COMMIT_MSG"
    echo ""
else
    echo ""
    echo "❌ 推送失败，请检查网络连接"
    echo ""
fi

read -p "按任意键退出..."
