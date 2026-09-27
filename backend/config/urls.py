from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Yeticode Innovations Admin"
admin.site.site_title = "Yeticode Admin"
admin.site.index_title = "Users, units and roles"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("payroll.urls")),
    path("api/", include("team.urls")),
    path("api/", include("notifications.urls")),
]

# Uploaded photos and logos in development. static() does nothing unless DEBUG is on.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
