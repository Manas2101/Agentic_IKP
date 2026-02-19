#!/bin/bash

echo "🚀 Starting HDPV2 Automation UI..."

# Start backend
echo "📦 Starting Flask backend..."
cd backend
source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt > /dev/null 2>&1
python app.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend
echo "⚛️  Starting React frontend..."
cd ../frontend
npm install > /dev/null 2>&1
npm start &
FRONTEND_PID=$!

echo ""
echo "✅ Application started successfully!"
echo "📱 Frontend: http://localhost:3000"
echo "🔧 Backend: http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
