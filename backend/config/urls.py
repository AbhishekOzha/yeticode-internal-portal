from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Yeticode Innovations Admin"
admin.site.site_title = "Yeticode Admin"
admin.site.index_title = "Users, units and roles"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
]
