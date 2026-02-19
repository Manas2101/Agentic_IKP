# Deployment Guide

## Production Deployment

### Backend Deployment (Flask)

#### Option 1: Using Gunicorn

1. Install Gunicorn:
```bash
pip install gunicorn
```

2. Run with Gunicorn:
```bash
cd backend
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

#### Option 2: Using Docker

Create `backend/Dockerfile`:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

Build and run:
```bash
docker build -t hdpv2-backend ./backend
docker run -p 5000:5000 hdpv2-backend
```

### Frontend Deployment (React)

#### Build for Production

```bash
cd frontend
npm run build
```

#### Option 1: Serve with Nginx

1. Install Nginx
2. Copy build files to web root:
```bash
sudo cp -r build/* /var/www/html/
```

3. Configure Nginx to proxy API requests to backend

#### Option 2: Deploy to Netlify/Vercel

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Deploy
cd frontend
netlify deploy --prod
```

### Environment Variables

#### Backend (.env)
```
FLASK_ENV=production
SECRET_KEY=<generate-secure-key>
MAX_CONTENT_LENGTH=16777216
GITHUB_TOKEN=<your-github-token>
```

#### Frontend (.env.production)
```
REACT_APP_API_URL=https://your-backend-url.com
```

## Docker Compose Setup

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

Run:
```bash
docker-compose up -d
```

## Security Considerations

1. **API Authentication**: Add authentication middleware
2. **Rate Limiting**: Implement rate limiting for API endpoints
3. **File Upload Validation**: Strict file type and size validation
4. **HTTPS**: Always use HTTPS in production
5. **Environment Variables**: Never commit sensitive data
6. **CORS**: Configure CORS for specific domains only

## Monitoring

### Health Checks

Backend health endpoint: `GET /api/health`

### Logging

Configure logging in production:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Scaling

### Horizontal Scaling
- Use load balancer (Nginx, HAProxy)
- Run multiple backend instances
- Use Redis for session management

### Vertical Scaling
- Increase Gunicorn workers
- Optimize database queries
- Implement caching

## Backup Strategy

1. Regular backups of uploaded files
2. Database backups (if using one)
3. Configuration backups
4. Automated backup scripts

## Rollback Plan

1. Keep previous Docker images
2. Version control for all code
3. Database migration rollback scripts
4. Quick rollback procedure documented
