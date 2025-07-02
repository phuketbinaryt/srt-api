#!/bin/bash

echo "🚀 SRT API - GitHub Push Script"
echo "================================"
echo ""

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

echo "📋 Instructions to push to GitHub:"
echo ""
echo "1. Go to https://github.com and create a new repository:"
echo "   - Repository name: srt-api"
echo "   - Description: Audio Transcription API that converts audio files to SRT subtitles using FastAPI and OpenAI Whisper"
echo "   - Make it Public"
echo "   - DO NOT initialize with README, .gitignore, or license"
echo ""
echo "2. After creating the repository, run these commands:"
echo ""
echo "   git remote add origin https://github.com/YOUR_USERNAME/srt-api.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "3. Replace YOUR_USERNAME with your actual GitHub username"
echo ""

# Check current git status
echo "📊 Current Git Status:"
echo "======================"
git status --short
echo ""

# Show commit history
echo "📝 Commit History:"
echo "=================="
git log --oneline
echo ""

echo "✅ Repository is ready to push!"
echo "📁 Total files ready: $(git ls-files | wc -l | tr -d ' ')"
echo ""
echo "🔗 After pushing, your repository will be available at:"
echo "   https://github.com/YOUR_USERNAME/srt-api"
echo ""
echo "🚀 Then follow RENDER_DEPLOYMENT.md to deploy to Render!"