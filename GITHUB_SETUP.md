# GitHub Setup Guide for SRT API

This guide explains how to push the Audio Transcription API to GitHub as the "srt-api" repository.

## Method 1: Using GitHub Web Interface (Recommended)

### Step 1: Create Repository on GitHub

1. Go to [GitHub.com](https://github.com) and sign in
2. Click the "+" icon in the top right corner
3. Select "New repository"
4. Fill in the details:
   - **Repository name**: `srt-api`
   - **Description**: `Audio Transcription API that converts audio files to SRT subtitles using FastAPI and OpenAI Whisper`
   - **Visibility**: Public (or Private if preferred)
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)
5. Click "Create repository"

### Step 2: Push Local Code to GitHub

After creating the repository, GitHub will show you commands. Use these:

```bash
cd /Users/arjanpapot/Desktop/n8n-dashboard/audio-transcription-api
git remote add origin https://github.com/YOUR_USERNAME/srt-api.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

## Method 2: Using GitHub CLI (If Available)

If you have GitHub CLI installed:

```bash
cd /Users/arjanpapot/Desktop/n8n-dashboard/audio-transcription-api
gh repo create srt-api --public --description "Audio Transcription API that converts audio files to SRT subtitles using FastAPI and OpenAI Whisper" --push
```

## Method 3: Install GitHub CLI First

If you want to install GitHub CLI:

```bash
# On macOS with Homebrew
brew install gh

# Then authenticate
gh auth login

# Then create and push repository
gh repo create srt-api --public --description "Audio Transcription API that converts audio files to SRT subtitles using FastAPI and OpenAI Whisper" --push
```

## Verification

After pushing, verify your repository:

1. Go to `https://github.com/YOUR_USERNAME/srt-api`
2. Check that all files are present:
   - `main.py` - FastAPI application
   - `requirements.txt` - Dependencies
   - `README.md` - Documentation
   - `render.yaml` - Render deployment config
   - `RENDER_DEPLOYMENT.md` - Deployment guide
   - `frontend.html` - Web interface
   - `Dockerfile` - Docker configuration
   - And other supporting files

## Next Steps: Deploy to Render

Once your code is on GitHub, follow the `RENDER_DEPLOYMENT.md` guide to deploy to Render.com:

1. Go to [Render.com](https://render.com)
2. Connect your GitHub account
3. Select the `srt-api` repository
4. Configure environment variables
5. Deploy!

## Repository Structure

Your GitHub repository should contain:

```
srt-api/
├── .env.example          # Environment template
├── .gitignore           # Git ignore rules
├── Dockerfile           # Docker configuration
├── GITHUB_SETUP.md      # This file
├── README.md            # Main documentation
├── RENDER_DEPLOYMENT.md # Render deployment guide
├── docker-compose.yml   # Docker Compose config
├── frontend.html        # Web interface
├── main.py             # FastAPI application
├── render.yaml         # Render configuration
├── requirements.txt    # Python dependencies
├── start.py           # Startup script
└── test_client.py     # Test client
```

## Troubleshooting

**Authentication Issues:**
- Make sure you're logged into GitHub
- Check your GitHub username and repository name
- Verify repository permissions

**Push Rejected:**
- Make sure the repository is empty (no initial files)
- Try force push: `git push -f origin main` (use carefully)

**Large Files:**
- If you get warnings about large files, they're likely from the .env file
- Make sure .env is in .gitignore (it should be)

## Security Notes

- The `.env` file is excluded from Git (check `.gitignore`)
- Never commit API keys or sensitive information
- Use environment variables for configuration in production