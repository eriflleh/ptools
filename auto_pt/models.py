# Create your models here.
from django.db import models

from ptools.base import BaseEntity, Trigger, PushConfig, OCRConfig


class Task(BaseEntity):
    name = models.CharField(verbose_name='任务名称', max_length=32)
    desc = models.CharField(verbose_name='任务描述', max_length=32)

    def __str__(self):
        return self.desc

    class Meta:
        verbose_name = '任务'
        verbose_name_plural = verbose_name
        ordering = ('name',)


class TaskJob(BaseEntity):
    """
    trigger: 　　 'date'、'interval'、'cron'。
    id: 　　任务的名字，不传的话会自动生成。不过为了之后对任务进行暂停、开启、删除等操作，建议给一个名字。并且是唯一的，如果多个任务取一个名字，之前的任务就会被覆盖。
    args: 　　list  执行代码所需要的参数。
    replace_existing: 　　默认不设置的话回导致重启项目后,  爆id已存在的错误, 设置此参数后会对已有的 id 进行覆盖从而避免报错
    next_run_time：　　datetime 开始执行时间
    misfire_grace_time: 　　强制执行结束的时间, 为避免撞车导致任务丢失, 没执行完就别执行了
    """
    task = models.ForeignKey(verbose_name='任务名称', to=Task, on_delete=models.CASCADE)
    job_id = models.CharField(verbose_name='任务ID', max_length=16, unique=True)
    trigger = models.CharField(verbose_name='任务类型', choices=Trigger.choices, default=Trigger.cron, max_length=64)
    task_exec = models.BooleanField(verbose_name='开启任务', default=False)
    replace_existing = models.BooleanField(verbose_name='覆盖任务', default=True,
                                           help_text='不设置此项重启项目后会报任务id已存在的错误, 设置此参数后会对已有的任务进行覆盖')
    expression_time = models.CharField(verbose_name='时间表达式',
                                       help_text='在间隔任务表示间隔时长使用数字，单位：秒，corn任务中为corn表达式：“0 15 8 ? * * 2022”',
                                       max_length=64)
    start_date = models.DateTimeField(verbose_name='任务开始时间', null=True, blank=True)
    end_date = models.DateTimeField(verbose_name='任务结束时间', null=True, blank=True)
    misfire_grace_time = models.IntegerField(verbose_name='任务运行时间', default=120,
                                             help_text='强制执行结束的时间, 为避免撞车导致任务丢失, 没执行完就别执行了')
    jitter = models.IntegerField(verbose_name='时间浮动参数', default=120,
                                 help_text='强制执行结束的时间, 为避免撞车导致任务丢失, 没执行完就别执行了')
    args = models.CharField(verbose_name='任务参数',
                            help_text='执行代码所需要的参数。',
                            max_length=128, null=True, blank=True)

    def __str__(self):
        return self.task.name

    class Meta:
        verbose_name = '计划任务'
        verbose_name_plural = verbose_name


class Notify(BaseEntity):
    """
    corpid=企业ID，在管理后台获取
    corpsecret: 自建应用的Secret，每个自建应用里都有单独的secret
    agentid: 应用ID，在后台应用中获取
    touser: 接收者用户名(微信账号), 多个用户用 | 分割, 与发送消息的touser至少存在一个
    """
    name = models.CharField(verbose_name='通知方式', choices=PushConfig.choices, default=PushConfig.wechat_work_push,
                            max_length=64)
    enable = models.BooleanField(verbose_name='开启通知', default=True, help_text='只有开启才能发送哦！')
    corpid = models.CharField(verbose_name='企业ID', max_length=64,
                              help_text='微信企业ID', null=True, blank=True)
    corpsecret = models.CharField(verbose_name='Secret', max_length=64,
                                  help_text='应用的Secret/Token', null=True, blank=True)
    agentid = models.CharField(verbose_name='应用ID', max_length=64,
                               help_text='APP ID', null=True, blank=True)

    touser = models.CharField(verbose_name='接收者', max_length=64,
                              help_text='接收者用户名/UID',
                              null=True, blank=True)
    custom_server = models.URLField(verbose_name='自定义服务器', null=True, blank=True, help_text='无自定义服务器的，请勿填写！')

    class Meta:
        verbose_name = '通知推送'
        verbose_name_plural = verbose_name


class OCR(BaseEntity):
    """
    corpid=企业ID，在管理后台获取
    corpsecret: 自建应用的Secret，每个自建应用里都有单独的secret
    agentid: 应用ID，在后台应用中获取
    app_id = '2695'
    api_key = 'TUoKvq3w1d'
    secret_key = 'XojLDC9s5qc'
    """
    name = models.CharField(verbose_name='OCR', choices=OCRConfig.choices, default=OCRConfig.baidu_aip, max_length=64)
    enable = models.BooleanField(verbose_name='启用', default=False)
    api_key = models.CharField(verbose_name='API-Key',
                               max_length=64,
                               null=True, blank=True)
    secret_key = models.CharField(verbose_name='Secret',
                                  max_length=64,
                                  help_text='应用的Secret',
                                  null=True, blank=True)
    app_id = models.CharField(verbose_name='应用ID',
                              max_length=64,
                              help_text='APP ID',
                              null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'OCR识别'
        verbose_name_plural = verbose_name
