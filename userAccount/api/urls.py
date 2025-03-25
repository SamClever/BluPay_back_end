from django.urls import path
from .views import view_allUsers, user_id, register_user
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('', view_allUsers, name='view_allUsers'),  # Matches: /movies/
    path('<int:pk>/', user_id, name='user_id'),  # Matches: /movies/1/
    path('register/', register_user, name='register_user'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)