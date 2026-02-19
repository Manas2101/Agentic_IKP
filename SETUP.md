# Quick Setup Guide

## Prerequisites Check

Before starting, ensure you have:
- ✅ Python 3.8 or higher
- ✅ Node.js 16 or higher
- ✅ Git CLI installed
- ✅ GitHub CLI (`gh`) installed and authenticated

## Quick Start (Recommended)

### Option 1: Using the Start Script

```bash
./start.sh
```

This will automatically:
1. Set up the Python virtual environment
2. Install backend dependencies
3. Start the Flask server (port 5000)
4. Install frontend dependencies
5. Start the React app (port 3000)

### Option 2: Manual Setup

#### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Start Flask server
python app.py
```

Backend will be available at: `http://localhost:5000`

#### Frontend Setup

Open a new terminal:

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start React app
npm start
```

Frontend will be available at: `http://localhost:3000`

## Verify Installation

1. Open browser to `http://localhost:3000`
2. You should see the HDPV2 Automation UI
3. Try switching between "Bulk Excel Upload" and "Form Builder" tabs

## GitHub CLI Setup

The application uses GitHub CLI to create PRs. Authenticate with:

```bash
gh auth login
```

Follow the prompts to authenticate with your GitHub account.

## Testing the Application

### Test Bulk Upload

1. Use the provided `info.csv` file
2. Go to "Bulk Excel Upload" tab
3. Drag and drop the CSV file
4. Click "Process & Create PRs"

### Test Form Builder

1. Go to "Form Builder" tab
2. Click on fields from the left panel
3. Fill in required fields (marked with *)
4. Click "Create PR"

## Troubleshooting

### Backend Issues

**Port 5000 already in use:**
```bash
# Find and kill the process
lsof -ti:5000 | xargs kill -9
```

**Module not found errors:**
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

### Frontend Issues

**Port 3000 already in use:**
```bash
# Kill the process
lsof -ti:3000 | xargs kill -9
```

**Dependency issues:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### CORS Issues

If you see CORS errors in the browser console:
1. Ensure backend is running on port 5000
2. Check that `flask-cors` is installed
3. Restart both servers

## File Structure

```
Agentic_IKP/
├── frontend/              # React application
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── App.js        # Main app component
│   │   └── index.css     # Styles
│   └── package.json
├── backend/              # Flask API
│   ├── app.py           # Main Flask app
│   └── requirements.txt
├── Agentic-ikp.py       # Core automation script
├── info.csv             # Sample data
└── start.sh             # Quick start script
```

## Next Steps

1. Customize the CSV fields in `info.csv` for your repositories
2. Update the automation script if needed
3. Configure GitHub authentication
4. Start processing your repositories!

## Support

For issues or questions:
- Check the main README.md
- Review the troubleshooting section
- Contact the development team
