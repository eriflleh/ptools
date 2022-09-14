from django import template

from pt_site.UtilityTool import FileSizeConvert

register = template.Library()


@register.filter(name='file_2_size')
def file_2_size(value):
    return FileSizeConvert.parse_2_file_size(int(value))
