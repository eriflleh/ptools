from django.urls import path

from . import views
from .views import scheduler

status = scheduler.state

urlpatterns = [
    path(r'auto_sign_in', views.auto_sign_in, name='auto_sign_in'),
    path(r'auto_get_status', views.auto_get_status, name='auto_get_status'),
    path(r'auto_update_torrents', views.auto_update_torrents, name='auto_update_torrents'),
    path(r'auto_remove_expire_torrents', views.auto_remove_expire_torrents, name='auto_remove_expire_torrents'),
    path(r'auto_push_to_downloader', views.auto_push_to_downloader, name='auto_push_to_downloader'),
    path(r'auto_get_torrent_hash', views.auto_get_torrent_hash, name='auto_get_torrent_hash'),
]
