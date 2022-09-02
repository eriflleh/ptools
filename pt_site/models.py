from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from ptools.base import BaseEntity, DownloaderCategory


# Create your models here.
# 支持的站点
class Site(BaseEntity):
    # 站点设置
    url = models.URLField(verbose_name='站点网址', default='', help_text='请保留网址结尾的"/"', unique=True)
    name = models.CharField(max_length=32, verbose_name='站点名称')
    logo = models.URLField(verbose_name='站点logo', default='', help_text='站点logo图标')
    # 功能支持
    sign_in_support = models.BooleanField(verbose_name="签到支持", default=True)
    get_torrent_support = models.BooleanField(verbose_name="拉取首页种子", default=True)
    get_userinfo_support = models.BooleanField(verbose_name="获取个人数据", default=True)
    search_support = models.BooleanField(verbose_name="搜索支持", default=False)
    # 主要页面
    page_default = models.CharField(verbose_name='默认搜索页面', default='torrents.php', max_length=64)
    page_sign_in = models.CharField(verbose_name='默认签到链接', default='attendance.php', max_length=64)
    page_detail = models.CharField(verbose_name='详情页面链接', default='details.php?id={}', max_length=64)
    page_download = models.CharField(verbose_name='默认下载链接', default='download.php?id={}', max_length=64)
    page_user = models.CharField(verbose_name='用户信息链接', default='userdetails.php?id={}', max_length=64)
    page_search = models.CharField(verbose_name='搜索链接', default='torrents.php?search={}', max_length=64)
    page_leeching = models.CharField(verbose_name='当前下载信息',
                                     default='getusertorrentlistajax.php?userid={}&type=leeching',
                                     max_length=64)
    page_uploaded = models.CharField(verbose_name='发布种子信息',
                                     default='getusertorrentlistajax.php?userid={}&type=uploaded',
                                     max_length=64)
    page_seeding = models.CharField(verbose_name='当前做种信息',
                                    default='getusertorrentlistajax.php?userid={}&type=seeding',
                                    max_length=64)
    page_completed = models.CharField(verbose_name='完成种子信息',
                                      default='getusertorrentlistajax.php?userid={}&type=completed',
                                      max_length=64)
    page_mybonus = models.CharField(verbose_name='魔力值页面',
                                    default='mybonus.php',
                                    max_length=64)
    page_viewfilelist = models.CharField(verbose_name='文件列表链接',
                                         default='viewfilelist.php?id={}',
                                         max_length=64)
    page_viewpeerlist = models.CharField(verbose_name='当前用户列表',
                                         default='viewpeerlist.php?id={}',
                                         max_length=64)
    sign_in_method = models.CharField(verbose_name='签到请求方法',
                                      default='get',
                                      help_text='get或post，请使用小写字母，默认get',
                                      max_length=5)
    sign_in_captcha = models.BooleanField(verbose_name='签到验证码',
                                          default=False,
                                          help_text='有签到验证码的站点请开启', )
    sign_in_params = models.CharField(verbose_name='签到请求参数',
                                      default='{}',
                                      help_text='默认无参数',
                                      max_length=128,
                                      blank=True,
                                      null=True)
    sign_in_headers = models.CharField(verbose_name='签到请求头',
                                       default='{}',
                                       help_text='字典格式：{"accept":"application/json","c":"d"},默认无参数',
                                       max_length=128)
    # HR及其他
    hr = models.BooleanField(verbose_name='H&R', default=False, help_text='站点是否开启HR')
    hr_rate = models.IntegerField(verbose_name='HR分享率', default=2, help_text='站点要求HR种子的分享率，最小：1')
    hr_time = models.IntegerField(verbose_name='HR时间', default=10, help_text='站点要求HR种子最短做种时间，单位：小时')
    sp_full = models.FloatField(verbose_name='满魔', default=0, help_text='时魔满魔')
    limit_speed = models.IntegerField(verbose_name='上传速度限制',
                                      default=100,
                                      help_text='站点盒子限速，家宽用户无需理会，单位：MB/S')
    # xpath规则
    torrents_rule = models.CharField(verbose_name='种子行信息',
                                     default='//table[@class="torrents"]/tr',
                                     max_length=128)
    name_rule = models.CharField(verbose_name='种子名称',
                                 default='.//td[@class="embedded"]/a/b/text()',
                                 max_length=128)
    title_rule = models.CharField(verbose_name='种子标题',
                                  default='.//tr/td[1]/text()',
                                  max_length=128)
    detail_url_rule = models.CharField(
        verbose_name='种子详情',
        default='.//td[@class="embedded"]/a[contains(@href,"detail")]/@href',
        max_length=128)
    category_rule = models.CharField(
        verbose_name='分类',
        default='.//td[@class="rowfollow nowrap"][1]/a[1]/img/@class',
        max_length=128)
    poster_rule = models.CharField(
        verbose_name='海报',
        default='.//table/tr/td[1]/img/@src',
        max_length=128)
    magnet_url_rule = models.CharField(
        verbose_name='下载链接',
        default='.//td/a[contains(@href,"download")]/@href',
        max_length=128)
    download_url_rule = models.CharField(
        verbose_name='种子链接',
        default='.//a[contains(@href,"download.php?id=") and contains(@href,"passkey")]/@href',
        max_length=128)
    size_rule = models.CharField(verbose_name='文件大小',
                                 default='.//td[5]/text()',
                                 max_length=128)
    hr_rule = models.CharField(
        verbose_name='H&R',
        default='.//table/tr/td/img[@class="hitandrun"]/@title',
        max_length=128)
    sale_rule = models.CharField(
        verbose_name='促销信息',
        default='.//table/tr/td/img[contains(@class,"pro_")]/@alt',
        max_length=128
    )
    sale_expire_rule = models.CharField(
        verbose_name='促销时间',
        default='.//table/tr/td/font/span/@title',
        max_length=128)
    release_rule = models.CharField(
        verbose_name='发布时间',
        default='.//td[4]/span/@title',
        max_length=128)
    seeders_rule = models.CharField(
        verbose_name='做种人数',
        default='.//td[6]/b/a/text()',
        max_length=128)
    leechers_rule = models.CharField(
        verbose_name='下载人数',
        default='.//td[7]/b/a/text()',
        max_length=128)
    completers_rule = models.CharField(
        verbose_name='完成人数',
        default='.//td[8]/a/b/text()',
        max_length=128)
    viewfilelist_rule = models.CharField(
        verbose_name='解析文件结构',
        default='.//td/text()',
        max_length=128)
    viewpeerlist_rule = models.CharField(
        verbose_name='平均下载进度',
        default='.//tr/td[9]/nobr/text()',
        max_length=128)
    peer_speed_rule = models.CharField(
        verbose_name='平均上传速度',
        default='.//tr/td[5]/nobr/text()',
        max_length=128)
    remark = models.TextField(verbose_name='备注', default='', null=True, blank=True)
    # 状态信息XPath
    invitation_rule = models.CharField(
        verbose_name='邀请资格',
        default='//a[contains(@href,"invite.php?id=")]/following-sibling::text()[1]',
        max_length=128)
    time_join_rule = models.CharField(
        verbose_name='注册时间',
        default='//td[contains(text(),"加入")]/following-sibling::td/span/@title',
        max_length=128)
    latest_active_rule = models.CharField(
        verbose_name='最后活动时间',
        default='//td[contains(text(),"最近动向")]/following-sibling::td/span/@title',
        max_length=128)
    uploaded_rule = models.CharField(
        verbose_name='上传量',
        default='//font[@class="color_uploaded"]/following-sibling::text()[1]',
        max_length=128)
    downloaded_rule = models.CharField(
        verbose_name='下载量',
        default='//font[@class="color_downloaded"]/following-sibling::text()[1]',
        max_length=128)
    ratio_rule = models.CharField(
        verbose_name='分享率',
        default='//font[@class="color_ratio"][1]/following-sibling::text()[1]',
        max_length=128)
    my_sp_rule = models.CharField(
        verbose_name='魔力值',
        default='//a[@href="mybonus.php"]/following-sibling::text()[1]',
        max_length=128)
    hour_sp_rule = models.CharField(
        verbose_name='时魔',
        default='//div[contains(text(),"每小时能获取")]/text()[1]',
        max_length=128)
    my_bonus_rule = models.CharField(
        verbose_name='保种积分',
        default='//font[@class="color_bonus" and contains(text(),"积分")]/following-sibling::text()[1]',
        max_length=128)
    my_level_rule = models.CharField(
        verbose_name='用户等级',
        default='//span[@class="medium"]/span[@class="nowrap"]/a[contains(@class,"_Name")]/@class',
        max_length=128
    )
    my_hr_rule = models.CharField(
        verbose_name='H&R',
        default='//tr[14]/td[2]/a/text()',
        max_length=128)
    leech_rule = models.CharField(
        verbose_name='下载数量',
        default='//img[@class="arrowdown"]/following-sibling::text()[1]',
        max_length=128)

    seed_rule = models.CharField(verbose_name='做种数量',
                                 default='//img[@class="arrowup"]/following-sibling::text()[1]',
                                 max_length=128)

    record_count_rule = models.CharField(verbose_name='种子记录数',
                                         default='/html/body/b/text()',
                                         max_length=128)

    seed_vol_rule = models.CharField(verbose_name='做种大小',
                                     default='//tr/td[3]',
                                     help_text='需对数据做处理',
                                     max_length=128)
    mailbox_rule = models.CharField(verbose_name='邮件规则',
                                    default='//a[@href="messages.php"]/following-sibling::text()[1]',
                                    help_text='获取新邮件',
                                    max_length=128)
    # HASH RULE
    hash_rule = models.CharField(verbose_name='种子HASH',
                                 default='//tr[11]//td[@class="no_border_wide"][2]/text()',
                                 max_length=128)

    class Meta:
        verbose_name = '站点信息'
        verbose_name_plural = verbose_name
        ordering = ['name', ]

    def __str__(self):
        return self.name


class MySite(BaseEntity):
    site = models.OneToOneField(verbose_name='站点', to=Site, on_delete=models.CASCADE)
    sort_id = models.IntegerField(verbose_name='排序', default=1)
    # 用户信息
    user_id = models.CharField(verbose_name='用户ID', max_length=16)
    passkey = models.CharField(max_length=128, verbose_name='PassKey')
    cookie = models.TextField(verbose_name='COOKIE')
    # 用户设置
    hr = models.BooleanField(verbose_name='开启HR下载', default=False, help_text='是否下载HR种子')
    sign_in = models.BooleanField(verbose_name='开启签到', default=True, help_text='是否开启签到')
    search = models.BooleanField(verbose_name='开启搜索', default=True, help_text='是否开启搜索')
    # 用户数据 自动拉取
    invitation = models.IntegerField(verbose_name='邀请资格', default=0)
    time_join = models.DateTimeField(verbose_name='注册时间', blank=True, null=True)
    latest_active = models.DateTimeField(verbose_name='最近活动时间', blank=True, null=True)
    sp_hour = models.CharField(verbose_name='时魔', max_length=8, default='')
    my_level = models.CharField(verbose_name='用户等级', max_length=16, default='')
    my_hr = models.CharField(verbose_name='H&R', max_length=16, default='')
    leech = models.IntegerField(verbose_name='当前下载', default=0)
    seed = models.IntegerField(verbose_name='当前做种', default=0)
    mail = models.IntegerField(verbose_name='新邮件', default=0)
    publish = models.IntegerField(verbose_name='发布种子', default=0)

    def __str__(self):
        return self.site.name

    class Meta:
        verbose_name = '我的站点'
        verbose_name_plural = verbose_name


# 站点信息
class SiteStatus(BaseEntity):
    # 获取日期，只保留当天最新数据
    site = models.ForeignKey(verbose_name='站点名称', to=MySite, on_delete=models.CASCADE)
    # 签到，有签到功能的访问签到页面，无签到的访问个人主页
    uploaded = models.CharField(verbose_name='上传量', default='0', max_length=16)
    downloaded = models.CharField(verbose_name='下载量', default='0', max_length=16)
    ratio = models.FloatField(verbose_name='分享率', default=0)
    my_sp = models.FloatField(verbose_name='魔力值', default=0)
    my_bonus = models.FloatField(verbose_name='做种积分', default=0)
    seed_vol = models.IntegerField(verbose_name='做种体积', default=0)

    class Meta:
        verbose_name = '我的数据'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.site.site.name


class SignIn(BaseEntity):
    site = models.ForeignKey(verbose_name='站点名称', to=MySite, on_delete=models.CASCADE)
    sign_in_today = models.BooleanField(verbose_name='签到', default=False)
    sign_in_info = models.CharField(verbose_name='信息', default='', max_length=256)

    class Meta:
        verbose_name = '签到'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.site.site.name


class Downloader(BaseEntity):
    # 下载器名称
    name = models.CharField(max_length=12, verbose_name='名称')
    # 下载器类别             tr  qb  de
    category = models.CharField(max_length=128, choices=DownloaderCategory.choices,
                                default=DownloaderCategory.qBittorrent,
                                verbose_name='下载器')
    # 用户名
    username = models.CharField(max_length=16, verbose_name='用户名')
    # 密码
    password = models.CharField(max_length=128, verbose_name='密码')
    # host
    host = models.CharField(max_length=32, verbose_name='HOST')
    # port
    port = models.IntegerField(default=8999, verbose_name='端口', validators=[
        MaxValueValidator(65535),
        MinValueValidator(1001)
    ])
    # 预留空间
    reserved_space = models.IntegerField(default=30, verbose_name='预留磁盘空间', validators=[
        MinValueValidator(1),
        MaxValueValidator(512)
    ], help_text='单位GB，最小为1G，最大512G')

    class Meta:
        verbose_name = '下载器'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


# 种子信息
class TorrentInfo(BaseEntity):
    site = models.ForeignKey(to=Site, on_delete=models.CASCADE, verbose_name='所属站点', null=True)
    name = models.CharField(max_length=256, verbose_name='种子名称', default='')
    title = models.CharField(max_length=256, verbose_name='标题', default='')
    category = models.CharField(max_length=128, verbose_name='分类', default='')
    poster_url = models.URLField(max_length=512, verbose_name='海报链接', default='')
    detail_url = models.URLField(max_length=512, verbose_name='种子详情', default='')
    magnet_url = models.URLField(verbose_name='下载链接')
    download_url = models.URLField(verbose_name='种子链接', unique=True, max_length=255)
    size = models.IntegerField(verbose_name='文件大小', default=0)
    state = models.BooleanField(max_length=16, verbose_name='推送状态', default=False)
    save_path = models.FilePathField(verbose_name='保存路径', default='/downloads/brush')
    hr = models.BooleanField(verbose_name='H&R', default=False)
    sale_status = models.CharField(verbose_name='优惠状态', default='无促销', max_length=16)
    sale_expire = models.CharField(verbose_name='到期时间', default='无限期', max_length=32)
    on_release = models.CharField(verbose_name='发布时间', default='', max_length=32)
    seeders = models.CharField(verbose_name='做种人数', default='0', max_length=8)
    leechers = models.CharField(verbose_name='下载人数', default='0', max_length=8)
    completers = models.CharField(verbose_name='完成人数', default='0', max_length=8)
    downloader = models.ForeignKey(to=Downloader,
                                   on_delete=models.CASCADE,
                                   verbose_name='下载器',
                                   blank=True, null=True)
    hash_string = models.CharField(max_length=128, verbose_name='Info_hash', default='')
    viewfilelist = models.CharField(max_length=128, verbose_name='文件列表', default='')
    viewpeerlist = models.FloatField(max_length=128, verbose_name='下载总进度', default=0)
    peer_list_speed = models.FloatField(max_length=128, verbose_name='平均上传速度', default=0)

    class Meta:
        verbose_name = '种子管理'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name
