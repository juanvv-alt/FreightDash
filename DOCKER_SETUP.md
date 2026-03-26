# Docker & Render Deployment Setup Guide

This project includes optimized Docker configuration for development and Render deployment in the Singapore region.

## 📋 Prerequisites

- Docker & Docker Compose installed
- Python 3.11+
- Render account (https://render.com)
- PostgreSQL knowledge (basic)

## 🚀 Quick Start - Local Development

### 1. Environment Setup

```bash
# Copy environment variables
cp .env.example .env

# Edit .env with your local settings
nano .env
```

### 2. Build and Start Services

```bash
# Build Docker images
docker-compose build

# Start all services (PostgreSQL, Django, Redis)
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Access your app
# Django: http://localhost:8000
# PostgreSQL: localhost:5432
# Redis: localhost:6379
```

### 3. Useful Commands

```bash
# View logs
docker-compose logs -f web
docker-compose logs -f db

# Access Django shell
docker-compose exec web python manage.py shell

# Run tests
docker-compose exec web pytest

# Stop services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

## 🏗️ Project Structure for Production

```
FreightDash/
├── config/
│   ├── settings.py
│   ├── wsgi.py
│   └── urls.py
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── render.yaml
├── .dockerignore
├── .env.example
└── README.md
```

### Expected Django App Structure

```bash
# Create a Django project if you don't have one
django-admin startproject config .

# Create Django apps
python manage.py startapp app_name
```

## 🚀 Deployment to Render (Singapore Region)

### Step 1: Prepare Your Repository

```bash
# Ensure files are in root directory
git add Dockerfile docker-compose.yml requirements.txt render.yaml .env.example
git commit -m "Add Docker and Render configuration"
git push
```

### Step 2: Deploy via Render Dashboard

1. Go to https://dashboard.render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Fill in deployment details:
   - **Name**: freightdash-web
   - **Region**: Singapore (ap-southeast-1)
   - **Branch**: main
   - **Runtime**: Python 3
   - **Build Command**: 
     ```
     pip install -r requirements.txt && python manage.py collectstatic --noinput --clear
     ```
   - **Start Command**: 
     ```
     python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4
     ```

### Step 3: Add Environment Variables

In Render Dashboard → Your Service → Environment:

```
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=yourdomain.onrender.com
DATABASE_URL=postgresql://...  (auto-linked if using Render PostgreSQL)
PYTHON_VERSION=3.11.0
TZ=Asia/Singapore
```

### Step 4: Add PostgreSQL Service

1. In Render Dashboard → New → PostgreSQL
2. **Region**: Singapore
3. **Name**: freightdash-db
4. **Database Name**: freightdash

The `DATABASE_URL` will be automatically available in your web service.

### Step 5: Deploy Configuration Files Usage

**Use `render.yaml`** for Infrastructure as Code (recommended):
```bash
# Deploy entire stack from render.yaml
# Commit render.yaml and push to trigger deployment
```

## 🔐 Security Best Practices

### For Production (Render)

1. **Generate Strong Secret Key**
   ```python
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

2. **Set Proper Environment Variables**
   - Never commit `.env` file
   - Use Render's environment variable management
   - Set `DEBUG=False` in production

3. **Database Security**
   - Use strong passwords for PostgreSQL
   - Manage in Render's private database
   - Enable SSL connections in `settings.py`

4. **CORS & CSRF**
   - Update `CSRF_TRUSTED_ORIGINS` for your domain
   - Configure CORS appropriately in `django-cors-headers`

5. **Static/Media Files**
   - Use AWS S3 or Render's file storage
   - Configure `USE_S3=True` in .env if using S3

## 📊 Performance Optimization (Singapore Region)

### Gunicorn Workers Configuration

The Dockerfile uses optimized settings for Render:
- **Workers**: 4 (adjust based on Render plan)
- **Worker Class**: sync (best for Django)
- **Max Requests**: 1000 (prevent memory leaks)
- **Timeout**: 60 seconds

For different Render plans:
- **Starter**: 2-3 workers
- **Standard**: 4 workers
- **Pro/Premium**: 6-8 workers

Edit Dockerfile ENTRYPOINT to adjust.

### Caching Strategy

Redis is included for:
- Session management
- Cache backend
- Celery task queue (optional)

### Database Optimization

```python
# In settings.py
DATABASES = {
    'default': {
        'CONN_MAX_AGE': 600,  # Connection pooling
        'CONN_HEALTH_CHECKS': True,
        'ATOMIC_REQUESTS': True,  # Atomicity
    }
}
```

## 🐛 Troubleshooting

### Build Fails on Render

**Issue**: psycopg2 compilation error
**Solution**: Use `psycopg2-binary` in requirements.txt (included)

### Database Connection Issues

```bash
# Test connection locally
docker-compose exec web python manage.py dbshell

# Check DATABASE_URL format
# postgresql://username:password@hostname:port/database
```

### Migration Issues

```bash
# Reset database (development only)
docker-compose down -v
docker-compose up -d
docker-compose exec web python manage.py migrate

# On Render, migrations run automatically
```

### Static Files Not Loading

```bash
# Manually collect static files
docker-compose exec web python manage.py collectstatic --noinput --clear

# Verify whitenoise in settings.py
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

## 📝 Configuration Files Reference

- **Dockerfile**: Multi-stage build, optimized for production
- **docker-compose.yml**: Local development stack with PostgreSQL & Redis
- **render.yaml**: Infrastructure as Code for Render deployment
- **requirements.txt**: Python dependencies
- **.env.example**: Environment variable template
- **DJANGO_SETTINGS.md**: Settings.py configuration template

## 🌐 Region-Specific Notes (Singapore)

- PostgreSQL region: `ap-southeast-1` (Singapore)
- Timezone: `Asia/Singapore`
- DNS resolution optimized for Asia-Pacific
- Latency: ~1-5ms from Singapore servers

## 📚 Additional Resources

- [Render Documentation](https://render.com/docs)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Gunicorn Configuration](https://docs.gunicorn.org/en/stable/settings.html)

## ❓ Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Review Django error messages
3. Verify environment variables match configuration
4. Check Render's support documentation

---

**Happy Deploying! 🚀**
