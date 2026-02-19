# GitHub API Setup Guide

The application now uses **GitHub REST API** to create pull requests instead of relying on the `gh` CLI.

## Prerequisites

You need a GitHub Personal Access Token (PAT) with the following permissions:
- `repo` (Full control of private repositories)
- `workflow` (Update GitHub Action workflows - optional)

## Creating a GitHub Personal Access Token

### For GitHub Enterprise (HSBC)

1. Go to your GitHub Enterprise instance: `https://alm-github.systems.uk.hsbc`
2. Click your profile picture → **Settings**
3. Scroll down to **Developer settings** (left sidebar)
4. Click **Personal access tokens** → **Tokens (classic)**
5. Click **Generate new token** → **Generate new token (classic)**
6. Give it a descriptive name: `HDPV2 Automation Tool`
7. Set expiration (recommend 90 days for security)
8. Select scopes:
   - ✅ **repo** (all sub-scopes)
   - ✅ **workflow** (optional)
9. Click **Generate token**
10. **IMPORTANT**: Copy the token immediately (you won't see it again!)

### For GitHub.com

1. Go to https://github.com/settings/tokens
2. Click **Generate new token** → **Generate new token (classic)**
3. Follow steps 6-10 above

## Configuring the Backend

### Option 1: Environment Variable (Recommended)

```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

Add to your `~/.bashrc` or `~/.zshrc` for persistence:
```bash
echo 'export GITHUB_TOKEN="ghp_your_token_here"' >> ~/.zshrc
source ~/.zshrc
```

### Option 2: .env File

Create `/Users/kritikapandey/Desktop/Agentic_IKP/backend/.env`:
```
GITHUB_TOKEN=ghp_your_token_here
```

Then update `app.py` to load from .env:
```python
from dotenv import load_dotenv
load_dotenv()
```

And install python-dotenv:
```bash
pip install python-dotenv
```

## Testing the Setup

1. Start the backend:
```bash
cd /Users/kritikapandey/Desktop/Agentic_IKP/backend
source venv/bin/activate
export GITHUB_TOKEN="your_token_here"
python app.py
```

2. The application will now:
   - Run the automation script to generate files
   - Push changes to a new branch
   - Create a PR using GitHub API
   - Return the PR URL in the response

## Security Best Practices

1. **Never commit tokens to git**
   - `.env` files are already in `.gitignore`
   - Always use environment variables

2. **Use token expiration**
   - Set tokens to expire after 90 days
   - Rotate tokens regularly

3. **Limit token scope**
   - Only grant necessary permissions
   - Use fine-grained tokens when available

4. **Revoke unused tokens**
   - Go to Settings → Developer settings → Personal access tokens
   - Revoke tokens you no longer need

## Troubleshooting

### Error: "GitHub token not configured"
- Ensure `GITHUB_TOKEN` environment variable is set
- Restart the Flask server after setting the variable

### Error: "Invalid GitHub URL"
- Check that the repository URL is in the correct format
- Example: `https://alm-github.systems.uk.hsbc/ORG/REPO.git`

### Error: "GitHub API error: 401"
- Token is invalid or expired
- Generate a new token and update the environment variable

### Error: "GitHub API error: 403"
- Token doesn't have required permissions
- Regenerate token with `repo` scope

### Error: "GitHub API error: 422"
- Branch already exists or PR already created
- Check if a PR already exists for this branch
- Delete the branch and try again

## API Response Format

Successful PR creation returns:
```json
{
  "message": "Successfully created PR #123 for app-name",
  "pr_url": "https://github.com/org/repo/pull/123"
}
```

Failed PR creation returns:
```json
{
  "error": "GitHub API error: 401 - Bad credentials"
}
```
