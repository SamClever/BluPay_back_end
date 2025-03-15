from django.urls import path
from .views import view_allUsers, user_id  # Ensure views are imported correctly

urlpatterns = [
    path('', view_allUsers, name='view_allUsers'),  # Matches: /movies/
    path('<int:pk>/', user_id, name='user_id'),  # Matches: /movies/1/
]
