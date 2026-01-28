# AoE2 Replay Visualizer

A web-based visualizer for Age of Empires II: Definitive Edition replay files.

**Live URL:** https://aoe2-replay-visualizer-production.up.railway.app

## Features

- Upload and parse `.aoe2record` replay files
- Isometric map view with unit and building sprites
- Playback controls with variable speed (1x, 2x, 4x, 8x, 12x, 16x)
- Player visibility toggles
- Action log with timestamped events
- Wall rendering
- Speed-based unit movement interpolation

## Project Structure

```
visualizer/
├── server.py          # Flask server (Railway & local)
├── requirements.txt   # Python dependencies
├── Procfile           # Railway process file
├── railway.json       # Railway configuration
├── public/            # Static assets
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── renderer.js
│   └── playback.js
└── generate_data.py   # Standalone replay parser
```

## Local Development

```bash
cd visualizer
pip install flask flask-cors mgz
python server.py
```

Open http://localhost:8000

## Deployment

The app is deployed on Railway at https://aoe2-replay-visualizer-production.up.railway.app

### Current Setup

The Railway project is already configured and linked to this repository. The deployment uses:
- **Nixpacks** for building (auto-detects Python)
- **Gunicorn** as the production WSGI server
- **Flask** serving the API and static files from `public/`

### Making Changes (Git Workflow)

1. **Create a new branch for your changes:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes and commit:**
   ```bash
   git add .
   git commit -m "Description of changes"
   ```

3. **Push the branch to GitHub:**
   ```bash
   git push -u origin feature/your-feature-name
   ```

4. **Create a Pull Request on GitHub:**
   - Go to the repository on GitHub
   - Click "Compare & pull request"
   - Review changes and merge to `main`

5. **Deploy to Railway:**
   ```bash
   git checkout main
   git pull
   cd visualizer
   railway up --service aoe2-replay-visualizer
   ```

### First-Time Setup (Already Done)

If setting up from scratch on a new machine:

1. **Install Railway CLI:**
   ```bash
   npm install -g @railway/cli
   ```

2. **Login to Railway:**
   ```bash
   railway login --browserless
   ```

3. **Link to existing project:**
   ```bash
   cd visualizer
   railway link
   # Select: aoe2-replay-visualizer project
   # Select: aoe2-replay-visualizer service
   ```

4. **Deploy:**
   ```bash
   railway up --service aoe2-replay-visualizer
   ```

### Environment Variables

Railway automatically sets the `PORT` environment variable. No additional configuration needed.

## Troubleshooting

### CORS errors
The server includes CORS headers. If you're still having issues, check browser console for specific errors.

### Large replay files
Very large replays may take longer to process. The server has no file size limit.

### Deployment issues
Check Railway logs:
```bash
railway logs --service aoe2-replay-visualizer
```
