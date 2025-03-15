from django.urls import path
from .views import view_account, view_account_id  # Ensure views are imported correctly

urlpatterns = [
    path('', view_account, name='view_account'),  # Matches: /movies/
    path('<int:pk>/', view_account_id, name='view_account_id'),  # Matches: /movies/1/
    
    # path('', view_account, name='view_account'),  # Matches: /movies/
    # path('<int:pk>/', view_account_id, name='view_account_id'),  # Matches: /movies/1/
    
]
