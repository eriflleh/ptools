from django.apps import AppConfig


class AutoPtConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auto_pt'
    verbose_name = '计划任务'

