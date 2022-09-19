from enum import Enum

from django.db import models


# 基类
class BaseEntity(models.Model):
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)

    class Meta:
        abstract = True


class StatusCodeEnum(Enum):
    """状态码枚举类"""

    OK = (0, '成功')
    ERROR = (-1, '错误')
    SERVER_ERR = (500, '服务器异常')
    # import
    NO_PASSKEY_WARNING = (7001, 'PassKey获取失败！')
    # OCR 1
    OCR_NO_CONFIG = (1001, 'OCR未配置')
    OCR_ACCESS_ERR = (1002, '在线OCR接口访问错误')
    # 签到
    SUCCESS_SIGN_IN = (2000, '签到成功！')
    FAILED_SIGN_IN = (2001, '签到失败！')
    IS_SIGN_IN = (2002, '请勿重复签到！')
    ALL_SIGN_IN = (2003, '已全部签到哦！')
    # 验证码 4
    IMAGE_CODE_ERR = (4001, '验证码错误(Wrong CAPTCHA)！')
    THROTTLING_ERR = (4002, '访问过于频繁')
    # 网络
    WEB_CONNECT_ERR = (4404, '网站访问错误！')
    WEB_CLOUD_FLARE = (4505, '我遇到CF盾咯！')
    COOKIE_EXPIRE = (4503, '疑似COOKIE过期咯！')
    NECESSARY_PARAM_ERR = (4003, '缺少必传参数')
    USER_ERR = (4004, '用户名错误')
    PWD_ERR = (4005, '密码错误')
    CPWD_ERR = (4006, '密码不一致')
    MOBILE_ERR = (4007, '手机号错误')
    SMS_CODE_ERR = (4008, '短信验证码有误')
    ALLOW_ERR = (4009, '未勾选协议')
    SESSION_ERR = (4010, '用户未登录')

    DB_ERR = (5000, '数据错误')
    EMAIL_ERR = (5001, '邮箱错误')
    TEL_ERR = (5002, '固定电话错误')
    NODATA_ERR = (5003, '无数据')
    NEW_PWD_ERR = (5004, '新密码错误')
    OPENID_ERR = (5005, '无效的openid')
    PARAM_ERR = (5006, '参数错误')
    STOCK_ERR = (5007, '库存不足')

    @property
    def code(self):
        """获取状态码"""
        return self.value[0]

    @property
    def errmsg(self):
        """获取状态码信息"""
        return self.value[1]


class CommonResponse:
    """
    统一的json返回格式
    """

    def __init__(self, data, status: StatusCodeEnum, msg):
        self.data = data
        self.code = status.code
        if msg is None:
            self.msg = status.errmsg
        else:
            self.msg = msg

    @classmethod
    def success(cls, data=None, status=StatusCodeEnum.OK, msg=None):
        return cls(data, status, msg)

    @classmethod
    def error(cls, data=None, status=StatusCodeEnum.ERROR, msg=None):
        return cls(data, status, msg)

    def to_dict(self):
        return {
            "code": self.code,
            "msg": self.msg,
            "data": self.data
        }


# 支持的下载器种类
class DownloaderCategory(models.TextChoices):
    # 下载器名称
    # Deluge = 'De', 'Deluge'
    Transmission = 'Tr', 'Transmission'
    qBittorrent = 'Qb', 'qBittorrent'


class TorrentBaseInfo:
    category_list = {
        0: "空类型",
        1: "电影Movies",
        2: "电视剧TV Series",
        3: "综艺TV Shows",
        4: "纪录片Documentaries",
        5: "动漫Animations",
        6: "音乐视频Music Videos",
        7: "体育Sports",
        8: "音乐Music",
        9: "电子书Ebook",
        10: "软件Software",
        11: "游戏Game",
        12: "资料Education",
        13: "旅游Travel",
        14: "美食Food",
        15: "其他Misc",
    }
    sale_list = {
        1: '无优惠',
        2: 'Free',
        3: '2X',
        4: '2XFree',
        5: '50%',
        6: '2X50%',
        7: '30%',
        8: '6xFree'
    }

    download_state = {
        'allocating': '分配',
        'checkingDL': '校验中',
        'checkingResumeData': '校验恢复数据',
        'checkingUP': '',
        'downloading': '下载中',
        'error': '错误',
        'forcedDL': '强制下载',
        'forcedMetaDL': '强制下载元数据',
        'forcedUP': '强制上传',
        'metaDL': '下载元数据',
        'missingFiles': '文件丢失',
        'moving': '移动中',
        'pausedDL': '暂停下载',
        'pausedUP': '完成',
        'queuedDL': '下载队列中',
        'queuedUP': '下载队列中',
        'stalledDL': '等待下载',
        'stalledUP': '做种',
        'unknown': '未知',
        'uploading': '上传中',
    }


class Trigger(models.TextChoices):
    # date = 'date', '单次任务'
    interval = 'interval', '间隔任务'
    cron = 'cron', 'cron任务'


class PushConfig(models.TextChoices):
    # date = 'date', '单次任务'
    wechat_work_push = 'wechat_work_push', '企业微信通知'
    wxpusher_push = 'wxpusher_push', 'WxPusher通知'
    pushdeer_push = 'pushdeer_push', 'PushDeer通知'
    bark_push = 'bark_push', 'Bark通知'


class OCRConfig(models.TextChoices):
    # date = 'date', '单次任务'
    baidu_aip = 'baidu_aip', '百度OCR'
