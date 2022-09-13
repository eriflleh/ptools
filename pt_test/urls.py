from django.urls import path

from . import views

urlpatterns = [
    path(r'test_import', views.test_import, name='test_import'),
]
