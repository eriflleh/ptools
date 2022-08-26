from django.urls import path

from auto_pt import views

urlpatterns = [
    path(r'get_tasks', views.get_tasks, name='get_tasks'),
    path(r'add_task', views.get_tasks, name='add_task'),
    path(r'exec_task', views.exec_task, name='exec_task'),
    path(r'test_field', views.test_field, name='test_field'),
    path(r'test_notify', views.test_notify, name='test_notify'),
    path(r'restart', views.restart_container, name='restart_container'),
    path(r'do_restart', views.do_restart, name='do_restart'),
    path(r'do_restart', views.do_restart, name='do_restart'),
    path(r'do_update', views.do_update, name='do_update'),
    path(r'get_update', views.do_get_update, name='do_get_update'),
    path(r'do_sql', views.do_sql, name='do_sql'),
]
