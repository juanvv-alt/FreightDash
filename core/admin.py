import json
import os
import tempfile
from io import StringIO

from django import forms
from django.apps import apps
from django.contrib import admin, messages
from django.core.management import call_command
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from .models import MenuItem


BACKUP_APP_LABELS = ("core", "voyage")


class MenuItemAdmin(admin.ModelAdmin):
    """Admin configuration for Menu Items."""
    list_display = ('title', 'url', 'icon', 'order', 'is_active', 'created_at', 'updated_at')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'url')
    ordering = ('order', 'title')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'url', 'icon', 'order', 'is_active')
        }),
        ('Help Text', {
            'classes': ('collapse',),
            'fields': (),
            'description': (
                '<p><strong>Icon examples:</strong></p>'
                '<ul>'
                '<li><i class="fas fa-ship"></i> fas fa-ship</li>'
                '<li><i class="fas fa-home"></i> fas fa-home</li>'
                '<li><i class="fas fa-calculator"></i> fas fa-calculator</li>'
                '<li><i class="fas fa-cog"></i> fas fa-cog</li>'
                '<li><i class="fas fa-database"></i> fas fa-database</li>'
                '<li><i class="fas fa-chart-line"></i> fas fa-chart-line</li>'
                '</ul>'
                '<p><strong>URL examples:</strong></p>'
                '<ul>'
                '<li>/ - Home</li>'
                '<li>/admin/ - Admin Panel</li>'
                '<li>/admin/database-tools/ - Database Tools</li>'
                '</ul>'
            )
        }),
    )


class RestoreBackupForm(forms.Form):
	backup_file = forms.FileField(
		help_text="Upload a JSON backup exported from this page."
	)
	replace_existing = forms.BooleanField(
		required=False,
		initial=True,
		help_text="Delete existing core/voyage data before restore.",
	)


def _delete_backup_app_data():
	models = []
	for app_label in BACKUP_APP_LABELS:
		app_config = apps.get_app_config(app_label)
		models.extend(app_config.get_models())

	# Delete in reverse order to respect FK dependencies.
	for model in reversed(models):
		model.objects.all().delete()


def database_tools_view(request):
	if request.method == "POST":
		action = request.POST.get("action")

		if action == "download":
			output = StringIO()
			call_command(
				"dumpdata",
				*BACKUP_APP_LABELS,
				format="json",
				indent=2,
				stdout=output,
			)
			backup_json = output.getvalue()
			timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
			response = HttpResponse(backup_json, content_type="application/json")
			response["Content-Disposition"] = (
				f'attachment; filename="freightdash_backup_{timestamp}.json"'
			)
			return response

		if action == "restore":
			restore_form = RestoreBackupForm(request.POST, request.FILES)
			if restore_form.is_valid():
				uploaded_file = restore_form.cleaned_data["backup_file"]
				replace_existing = restore_form.cleaned_data["replace_existing"]

				try:
					file_bytes = uploaded_file.read()
					json.loads(file_bytes.decode("utf-8"))
				except (UnicodeDecodeError, json.JSONDecodeError):
					messages.error(request, "Invalid backup file. Please upload valid JSON.")
					return redirect(reverse("admin:database-tools"))

				temp_path = None
				try:
					with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_file:
						tmp_file.write(file_bytes)
						temp_path = tmp_file.name

					with transaction.atomic():
						if replace_existing:
							_delete_backup_app_data()
						call_command("loaddata", temp_path, verbosity=0)

					messages.success(request, "Backup restored successfully.")
				except Exception as exc:
					messages.error(request, f"Restore failed: {exc}")
				finally:
					if temp_path and os.path.exists(temp_path):
						os.unlink(temp_path)

				return redirect(reverse("admin:database-tools"))

			messages.error(request, "Please select a backup file.")
			return redirect(reverse("admin:database-tools"))

	restore_form = RestoreBackupForm()
	context = {
		**admin.site.each_context(request),
		"title": "Database Backup & Restore",
		"backup_app_labels": ", ".join(BACKUP_APP_LABELS),
		"restore_form": restore_form,
	}
	return TemplateResponse(request, "admin/database_tools.html", context)


# Register the MenuItem model
admin.site.register(MenuItem, MenuItemAdmin)


_original_get_urls = admin.site.get_urls


def _custom_admin_urls():
	custom_urls = [
		path(
			"database-tools/",
			admin.site.admin_view(database_tools_view),
			name="database-tools",
		),
	]
	return custom_urls + _original_get_urls()


admin.site.get_urls = _custom_admin_urls