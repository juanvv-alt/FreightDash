# AdminLTE Dashboard Setup Guide

## Overview

Your FreightDash application now includes **Jazzmin**, a modern admin interface based on AdminLTE, with a preconfigured login page.

## Admin Credentials

- **Username**: `admin`
- **Password**: `admin`

⚠️ **IMPORTANT**: Change these credentials in production!

## Access Admin Panel

Once the Docker containers are running:

```
http://localhost:8000/admin/
```

## Features

✅ **Modern AdminLTE-based Interface**  
✅ **Responsive Design** - Works on desktop, tablet, and mobile  
✅ **User Management** - Built-in Django auth  
✅ **Search Functionality**  
✅ **Dark Mode Support**  
✅ **Custom Branding** - "FreightDash" branding throughout  
✅ **Dashboard Overview**  

## Admin Panel Screenshots

The admin panel includes:
- **Dashboard** - Overview of your application
- **Users** - Manage user accounts and permissions
- **Groups** - Manage user groups and roles
- **Admin Documentation** - Automatic docs for your models

## Security Notes

### For Local Development
The admin/admin credentials are fine for testing locally.

### For Production (Render)
Before deploying to Render:

1. **Change Admin Password**:
   ```bash
   # In your local environment
   docker-compose exec web python manage.py changepassword admin

   # Or create a new superuser
   docker-compose exec web python manage.py createsuperuser
   ```

2. **Enable HTTPS Enforcement**:
   - Already configured in `settings.py` when `DEBUG=False`

3. **Set Strong Secret Key**:
   - Configure in Render environment variables
   ```
   SECRET_KEY=your-very-secure-random-key
   ```

4. **Use Environment Variables**:
   - Don't hardcode credentials
   - Use Render's secure environment variable management

## Configuration

Jazzmin settings are in [config/settings.py](../config/settings.py):

```python
JAZZMIN_SETTINGS = {
    "site_title": "FreightDash Admin",
    "site_header": "FreightDash Administration",
    "site_brand": "FreightDash",
    # ... more settings
}
```

### Customize Branding

Edit `JAZZMIN_SETTINGS` in settings.py:
- Change `site_title`
- Change `site_header`
- Change `site_brand`
- Add custom `login_logo`

## Management Commands

### Create Admin User
```bash
# Automatic (runs at startup)
python manage.py create_admin

# Manual
python manage.py createsuperuser
```

### Change Password
```bash
docker-compose exec web python manage.py changepassword admin
```

### Create Additional Superusers
```bash
docker-compose exec web python manage.py createsuperuser
```

## Extending Admin Interface

### Add Custom Models to Admin

1. Create a model in your app:
```python
# In core/models.py or your app's models.py
from django.db import models

class YourModel(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
```

2. Register in admin:
```python
# In core/admin.py
from django.contrib import admin
from .models import YourModel

@admin.register(YourModel)
class YourModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at']
```

3. Run migrations:
```bash
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
```

## Default Models Available in Admin

- **Users** - User account management
- **Groups** - Role-based access control
- **Permissions** - Model-level permissions
- **Log Entries** - Admin action history

## Troubleshooting

### Admin page looks broken/no styling
- Static files might not be collected
```bash
docker-compose exec web python manage.py collectstatic --noinput
```

### Can't login
- Check username is `admin` and password is `admin`
- Check DATABASE is running and accessible
- Check logs: `docker-compose logs -f web`

### Forgot admin password
```bash
docker-compose exec web python manage.py changepassword admin
```

### Need to recreate admin user
```bash
docker-compose exec web python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.filter(username='admin').delete()
>>> exit()
docker-compose exec web python manage.py create_admin
```

## Next Steps

1. ✅ Access admin at `http://localhost:8000/admin/`
2. ✅ Login with `admin` / `admin`
3. ✅ Create additional users for your team
4. ✅ Build your custom models and admin interfaces
5. ✅ Set up permissions and groups

## Resources

- [Jazzmin Documentation](https://django-jazzmin.readthedocs.io/)
- [Django Admin Documentation](https://docs.djangoproject.com/en/4.2/ref/contrib/admin/)
- [AdminLTE Documentation](https://adminlte.io/)

---

**Happy administering! 🚀**
