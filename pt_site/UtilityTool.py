import contextlib
import json
import logging
import random
import re
import threading
import time
from datetime import datetime
from urllib.request import urlopen

import aip
import cloudscraper
import dateutil.parser
import opencc
import qbittorrentapi
import requests
import transmission_rpc
from django.db.models import QuerySet
from lxml import etree
from pypushdeer import PushDeer
from requests import Response, ReadTimeout
from urllib3.exceptions import NewConnectionError
from wechat_push import WechatPush
from wxpusher import WxPusher

from auto_pt.models import Notify, OCR
from pt_site.models import MySite, SignIn, TorrentInfo, SiteStatus, Site
from ptools.base import TorrentBaseInfo, PushConfig, CommonResponse, StatusCodeEnum, DownloaderCategory


def cookie2dict(source_str: str):
    """
    cookies字符串转为字典格式,传入参数必须为cookies字符串
    """
    dist_dict = {}
    list_mid = source_str.split(';')
    for i in list_mid:
        # 以第一个选中的字符分割1次，
        list2 = i.split('=', 1)
        dist_dict[list2[0]] = list2[1]
    return dist_dict


# 获取字符串中的小数
get_decimals = lambda x: re.search("\d+(\.\d+)?", x).group()

converter = opencc.OpenCC('t2s.json')

lock = threading.Lock()


class FileSizeConvert:
    """文件大小和字节数互转"""

    @staticmethod
    def parse_2_byte(file_size: str):
        """将文件大小字符串解析为字节"""
        regex = re.compile(r'(\d+(?:\.\d+)?)\s*([kmgtp]?b)', re.IGNORECASE)

        order = ['b', 'kb', 'mb', 'gb', 'tb', 'pb', 'eb']

        for value, unit in regex.findall(file_size):
            return int(float(value) * (1024 ** order.index(unit.lower())))

    @staticmethod
    def parse_2_file_size(byte: int):
        units = ["B", "KB", "MB", "GB", "TB", "PB", 'EB']
        size = 1024.0
        for i in range(len(units)):
            if (byte / size) < 1:
                return "%.3f%s" % (byte, units[i])
            byte = byte / size


class MessageTemplate:
    """消息模板"""

    status_message_template = "等级：{} 魔力：{} 时魔：{} 积分：{} 分享率：{} 下载量：{} 上传量：{} 上传数：{} 下载数：{} 邀请：{} H&R：{}\n"


class PtSpider:
    """爬虫"""

    def __init__(self, browser='chrome', platform='darwin',
                 user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36 Edg/105.0.1343.27',
                 *args, **kwargs):
        self.browser = browser
        self.platform = platform
        self.headers = {
            'User-Agent': user_agent,
            # 'Connection': 'close',
            # 'verify': 'false',
            # 'keep_alive': 'False'
        }

    @staticmethod
    def cookies2dict(source_str: str):
        """解析cookie"""
        dist_dict = {}
        list_mid = source_str.split(';')
        for i in list_mid:
            # 以第一个选中的字符分割1次，
            list2 = i.split('=', 1)
            # print(list2)
            if list2[0] == '':
                continue
            dist_dict[list2[0]] = list2[1]
        return dist_dict

    def get_scraper(self, delay=0):
        return cloudscraper.create_scraper(browser={
            'browser': self.browser,
            'platform': self.platform,
            'mobile': False
        }, delay=delay)

    def send_text(self, text: str, url: str = None):
        """通知分流"""
        notifies = Notify.objects.filter(enable=True).all()
        res = '你还没有配置通知参数哦！'
        if len(notifies) <= 0:
            return res
        try:
            for notify in notifies:
                if notify.name == PushConfig.wechat_work_push:
                    """企业微信通知"""
                    notify_push = WechatPush(
                        corp_id=notify.corpid,
                        secret=notify.corpsecret,
                        agent_id=notify.agentid, )
                    res = notify_push.send_text(
                        text=text,
                        to_uid=notify.touser if notify.touser else '@all'
                    )

                    print(res)

                if notify.name == PushConfig.wxpusher_push:
                    """WxPusher通知"""
                    res = WxPusher.send_message(
                        content=text,
                        url=url,
                        uids=notify.touser.split(','),
                        token=notify.corpsecret,
                        content_type=3,  # 1：文本，2：html，3：markdown
                    )
                    print(res)

                if notify.name == PushConfig.pushdeer_push:
                    pushdeer = PushDeer(
                        server=notify.custom_server,
                        pushkey=notify.corpsecret)
                    # res = pushdeer.send_text(text, desp="optional description")
                    res = pushdeer.send_markdown(text=text, desp="PushDeer消息提醒")
                    print(res)

                if notify.name == PushConfig.bark_push:
                    url = notify.custom_server + notify.corpsecret + '/' + text
                    res = self.get_scraper().get(url=url)
                    print(res)
        except Exception as e:
            print("通知发送失败，" + str(e))

    def send_request(self,
                     my_site: MySite,
                     url: str,
                     method: str = 'get',
                     data: dict = None,
                     params: dict = None,
                     json: dict = None,
                     timeout: int = 20,
                     delay: int = 15,
                     headers: dict = {},
                     proxies: dict = None):
        site = my_site.site
        scraper = self.get_scraper(delay=delay)
        self.headers = headers
        for k, v in eval(site.sign_in_headers).items():
            self.headers[k] = v
        # print(self.headers)

        if method.lower() == 'post':
            return scraper.post(
                url=url,
                headers=self.headers,
                cookies=self.cookies2dict(my_site.cookie),
                data=data,
                timeout=timeout,
                json=json,
                proxies=proxies,
                params=params,
            )
        return scraper.get(
            url=url,
            headers=self.headers,
            cookies=self.cookies2dict(my_site.cookie),
            data=data,
            timeout=timeout,
            proxies=proxies,
            params=params,
            json=json,
        )

    def ocr_captcha(self, img_url):
        """百度OCR高精度识别，传入图片URL"""
        # 获取百度识别结果
        ocr = OCR.objects.filter(enable=True).first()
        if not ocr:
            logging.error('未设置百度OCR文本识别API，无法使用本功能！')
            return CommonResponse.error(
                status=StatusCodeEnum.OCR_NO_CONFIG,
            )
        try:
            ocr_client = aip.AipOcr(appId=ocr.app_id, secretKey=ocr.secret_key, apiKey=ocr.api_key)
            res1 = ocr_client.basicGeneralUrl(img_url)
            print(res1)
            if res1.get('error_code'):
                res1 = ocr_client.basicAccurateUrl(img_url)
            print('res1', res1)
            if res1.get('error_code'):
                return CommonResponse.error(
                    status=StatusCodeEnum.OCR_ACCESS_ERR,
                    msg=StatusCodeEnum.OCR_ACCESS_ERR.errmsg + res1.get('error_msg')
                )
            res2 = res1.get('words_result')[0].get('words')
            # 去除杂乱字符
            imagestring = ''.join(re.findall('[A-Za-z0-9]+', res2)).strip()
            print('百度OCR天空验证码：', imagestring, len(imagestring))
            # 识别错误就重来

            return CommonResponse.success(
                status=StatusCodeEnum.OK,
                data=imagestring,
            )
        except Exception as e:
            print(str(e))
            # raise
            self.send_text('百度OCR识别失败：' + str(e))
            return CommonResponse.error(
                status=StatusCodeEnum.OCR_ACCESS_ERR,
                msg=StatusCodeEnum.OCR_ACCESS_ERR.errmsg + str(e)
            )

    def parse_ptpp_cookies(self, data_list):
        # 解析前端传来的数据
        datas = json.loads(data_list.get('cookies'))
        info_list = json.loads(data_list.get('info'))
        userdata_list = json.loads(data_list.get('userdata'))
        cookies = []
        try:
            for data, info in zip(datas, info_list):
                cookie_list = data.get('cookies')
                host = data.get('host')
                cookie_str = ''
                for cookie in cookie_list:
                    cookie_str += cookie.get('name') + '=' + cookie.get('value') + ';'
                # print(domain, cookie_str)
                cookies.append({
                    'url': data.get('url'),
                    'host': host,
                    'icon': info.get('icon'),
                    'info': info.get('user'),
                    'passkey': info.get('passkey'),
                    'cookies': cookie_str.rstrip(';'),
                    'userdatas': userdata_list.get(host)
                })
            print(len(cookies))
            # print(cookies)
            return CommonResponse.success(data=cookies)
        except Exception as e:
            # raise
            return CommonResponse.error(msg='Cookies解析失败，请确认导入了正确的cookies备份文件！')

    # @transaction.atomic
    def get_uid_and_passkey(self, cookie: dict):
        url = cookie.get('url')
        host = cookie.get('host')
        site = Site.objects.filter(url__contains=host).first()
        # print('查询站点信息：', site, site.url, url)
        if not site:
            return CommonResponse.error(msg='尚未支持此站点：' + url)
        icon = cookie.get('icon')
        if icon:
            site.logo = icon
        site.save()
        # my_site = MySite.objects.filter(site=site).first()
        # print('查询我的站点：',my_site)
        # 如果有更新cookie，如果没有继续创建
        my_level_str = cookie.get('info').get('levelName')
        if my_level_str:
            my_level = re.sub(u'([^a-zA-Z_ ])', "", my_level_str)
        else:
            my_level = ' '
        userdatas = cookie.get('userdatas')
        time_stamp = cookie.get('info').get('joinTime')
        if time_stamp:
            time_join = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time_stamp / 1000))
        else:
            time_join = None
        passkey = cookie.get('passkey')
        print('passkey:', passkey)

        result = MySite.objects.update_or_create(site=site, defaults={
            'cookie': cookie.get('cookies'),
            'passkey': passkey,
            'user_id': cookie.get('info').get('id'),
            'my_level': my_level if my_level else ' ',
            'time_join': time_join,
            'seed': cookie.get('info').get('seeding') if cookie.get('info').get('seeding') else 0,
            'mail': cookie.get('info').get('messageCount') if cookie.get('info').get('messageCount') else 0,
        })
        my_site = result[0]
        passkey_msg = ''
        if not passkey:
            try:
                response = self.send_request(my_site, site.url + site.page_control_panel)
                passkey = self.parse(response, site.my_passkey_rule)[0]
                my_site.passkey = passkey
                my_site.save()
            except Exception as e:
                passkey_msg = site.name + ' PassKey获取失败，请手动添加！'
                print(passkey_msg)
        for key, value in userdatas.items():
            print(key)
            try:
                downloaded = value.get('downloaded')
                uploaded = value.get('uploaded')
                seeding_size = value.get('seedingSize')
                my_sp = value.get('bonus')
                ratio = value.get('ratio')
                if ratio is None or ratio == 'null':
                    continue
                if type(ratio) == str:
                    ratio = ratio.strip('\n').strip()
                if float(ratio) < 0:
                    ratio = 'inf'
                if not value.get(
                        'id') or key == 'latest' or not downloaded or not uploaded or not seeding_size or not my_sp:
                    continue
                create_time = dateutil.parser.parse(key).date()
                count_status = SiteStatus.objects.filter(site=my_site,
                                                         created_at__date=create_time).count()
                if count_status >= 1:
                    continue
                status = SiteStatus.objects.create(
                    site=my_site,
                    uploaded=uploaded,
                    downloaded=downloaded,
                    ratio=float(ratio),
                    seed_vol=seeding_size,
                    my_sp=my_sp
                )
                # res_status = SiteStatus.objects.update_or_create(
                #     site=my_site,
                #     created_at__date=create_time,
                #     defaults={
                #         'uploaded': uploaded,
                #         'downloaded': downloaded,
                #         'my_sp': my_sp,
                #         'seed_vol': seeding_size,
                #         'ratio': float(ratio),
                #     })
                status.created_at = create_time
                status.save()
                print(status)
            except Exception as e:
                print(site.name, key, ' 数据导入出错')
                print('错误原因：', e)
                continue
        # if not passkey:
        #     return CommonResponse.success(
        #         status=StatusCodeEnum.NO_PASSKEY_WARNING,
        #         msg=site.name + (' 信息导入成功！' if result[1] else ' 信息更新成功！ ') + passkey_msg
        #     )
        return CommonResponse.success(
            status=StatusCodeEnum.NO_PASSKEY_WARNING,
            msg=site.name + (' 信息导入成功！' if result[1] else ' 信息更新成功！ ') + passkey_msg
        )

    @staticmethod
    def get_torrent_info_from_downloader(torrent_info: TorrentInfo):
        """
        通过种子信息，到下载器查询任务信息
        :param torrent_info:
        :return:
        """
        downloader = torrent_info.downloader
        if not downloader:
            return CommonResponse.error(
                msg='此种子未推送到下载器！'
            )
        if downloader.category == DownloaderCategory.Transmission:
            try:
                tr_client = transmission_rpc.Client(host=downloader.host,
                                                    port=downloader.port,
                                                    username=downloader.username,
                                                    password=downloader.password)
                torrent = tr_client.get_torrents(ids=torrent_info.hash_string)
            except Exception as e:
                return CommonResponse.error(
                    msg='下载无法连接，请检查下载器是否正常？！'
                )
        elif downloader.category == DownloaderCategory.qBittorrent:
            try:
                qb_client = qbittorrentapi.Client(
                    host=downloader.host,
                    port=downloader.port,
                    username=downloader.username,
                    password=downloader.password,
                    # 仅返回简单JSON
                    # SIMPLE_RESPONSES=True
                )
                qb_client.auth_log_in()
                torrent = qb_client.torrents_info(hashes=torrent_info.hash_string)
            except Exception as e:
                return CommonResponse.error(
                    msg='下载无法连接，请检查下载器是否正常？'
                )
            # if downloader.category == DownloaderCategory.qBittorrent:
            #     pass
        else:
            return CommonResponse.error(
                msg='下载不存在，请检查下载器是否正常？'
            )
        return CommonResponse.success(
            data=torrent
        )

    @staticmethod
    def download_img(image_url):
        """
        下载图片并转为二进制流
        :param image_url:
        :return:
        """
        if image_url.startswith('http'):
            r = requests.get(image_url, timeout=5)
            img_data = r.content
        elif image_url.startswith('ftp'):
            with contextlib.closing(urlopen(image_url, None, 10)) as r:
                img_data = r.read()
        else:
            return False
        return img_data

    def sign_in_u2(self, my_site: MySite):
        site = my_site.site
        try:
            url = site.url + site.page_sign_in.lstrip('/')
            result = self.send_request(
                my_site=my_site,
                url=url,
            )
            sign_str = ''.join(self.parse(result, '//a[@href="showup.php"]'))
            if '已签到' in converter.convert(sign_str):
                return CommonResponse.success(msg=site.name + '已签到，请勿重复操作！！')
            req = self.parse(result, '//form//td/input[@name="req"]/@value')
            hash_str = self.parse(result, '//form//td/input[@name="hash"]/@value')
            form = self.parse(result, '//form//td/input[@name="form"]/@value')
            submit_name = self.parse(result, '//form//td/input[@type="submit"]/@name')
            submit_value = self.parse(result, '//form//td/input[@type="submit"]/@value')
            message = site.sign_in_params if len(site.sign_in_params) >= 5 else '天空飘来五个字儿,幼儿园里没有事儿'
            print(submit_name)
            print(submit_value)
            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
            }
            param = []
            for name, value in zip(submit_name, submit_value):
                param.append({
                    name: value
                })
            data = {
                'req': req[0],
                'hash': hash_str[0],
                'form': form[0],
                'message': message,
            }
            data.update(param[random.randint(0, 3)])
            print(data)
            response = self.send_request(
                my_site,
                url=site.url + site.page_sign_in.lstrip('/') + '?action=show',
                method=site.sign_in_method,
                headers=headers,
                data=data,
            )
            print(response.content.decode('utf8'))
            if 'response.content.decode("utf8")' in response.content.decode('utf8'):
                return CommonResponse.success(msg='低保签到成功！')
            else:
                return CommonResponse.error(msg='签到失败！')
        except Exception as e:
            # raise
            return CommonResponse.error(
                status=StatusCodeEnum.WEB_CONNECT_ERR,
                msg=site.name + str(e)
            )

    def sign_in_hdsky(self, my_site: MySite, captcha=False):
        """HDSKY签到"""
        site = my_site.site
        url = site.url + site.page_sign_in.lstrip('/')
        # sky无需验证码时使用本方案
        if not captcha:
            result = self.send_request(
                my_site=my_site,
                method=site.sign_in_method,
                url=url,
                data=eval(site.sign_in_params))
        # sky无验证码方案结束
        else:
            # 获取img hash
            print('# 开启验证码！')
            res = self.send_request(
                my_site=my_site,
                method='post',
                url=site.url + 'image_code_ajax.php',
                data={
                    'action': 'new'
                }).json()
            # img url
            img_get_url = site.url + 'image.php?action=regimage&imagehash=' + res.get('code')
            print('验证码图片链接：', img_get_url)
            # 获取OCR识别结果
            # imagestring = self.ocr_captcha(img_url=img_get_url)
            times = 0
            # imagestring = ''
            ocr_result = None
            while times <= 5:
                # ocr_result = self.ocr_captcha(img_get_url)
                ocr_result = self.ocr_captcha(img_get_url)
                if ocr_result.code == StatusCodeEnum.OK.code:
                    imagestring = ocr_result.data
                    print('验证码长度：', len(imagestring), len(imagestring) == 6)
                    if len(imagestring) == 6:
                        break
                times += 1
                time.sleep(1)
            if ocr_result.code != StatusCodeEnum.OK.code:
                return ocr_result
            # 组装请求参数
            data = {
                'action': 'showup',
                'imagehash': res.get('code'),
                'imagestring': imagestring
            }
            # print('请求参数', data)
            result = self.send_request(
                my_site=my_site,
                method=site.sign_in_method,
                url=url, data=data)
        print('天空返回值：', result.content)
        return CommonResponse.success(
            status=StatusCodeEnum.OK,
            data=result.json()
        )

    def sign_in_ttg(self, my_site: MySite):
        """
        TTG签到
        :param my_site:
        :return:
        """
        site = my_site.site
        url = site.url + site.page_user.format(my_site.user_id)
        print('个人主页：', url)
        try:
            res = self.send_request(my_site=my_site, url=url)
            # print(res.text.encode('utf8'))
            # html = self.parse(res, '//script/text()')
            html = etree.HTML(res.content).xpath('//script/text()')
            # print(html)
            text = ''.join(html).replace('\n', '').replace(' ', '')
            print(text)
            signed_timestamp = get_decimals(re.search("signed_timestamp:\"\d{10}", text).group())

            signed_token = re.search('[a-zA-Z0-9]{32}', text).group()
            params = {
                'signed_timestamp': signed_timestamp,
                'signed_token': signed_token
            }
            print('signed_timestamp:', signed_timestamp)
            print('signed_token:', signed_token)

            resp = self.send_request(
                my_site,
                site.url + site.page_sign_in,
                method=site.sign_in_method,
                data=params)
            print(resp.content)
            return CommonResponse.success(
                status=StatusCodeEnum.OK,
                msg=resp.content.decode('utf8')
            )
        except Exception as e:
            return CommonResponse.success(
                status=StatusCodeEnum.WEB_CONNECT_ERR,
                msg=site.name + str(e)
            )

    @staticmethod
    def get_user_torrent(html, rule):
        res_list = html.xpath(rule)
        print('content', res_list)
        print('res_list:', len(res_list))
        return '0' if len(res_list) == 0 else res_list[0]

    def do_sign_in(self, pool, queryset: QuerySet[MySite]):
        message_list = '### <font color="orange">未显示的站点已经签到过了哟！</font>  \n'
        queryset = [my_site for my_site in queryset if
                    my_site.cookie and my_site.passkey and my_site.site.sign_in_support and my_site.signin_set.filter(
                        created_at__date__gte=datetime.today()).count() <= 0]
        print(len(queryset))
        if len(queryset) <= 0:
            message_list += '> <font color="orange">已全部签到或无需签到！</font>  \n'
        # results = pool.map(pt_spider.sign_in, site_list)
        with lock:
            results = pool.map(self.sign_in, queryset)
            for my_site, result in zip(queryset, results):
                print('自动签到：', my_site, result)
                if result.code == StatusCodeEnum.OK.code:
                    message_list += ('> ' + my_site.site.name + ' 签到成功！' + converter.convert(result.msg) + '  \n')
                    logging.info(my_site.site.name + '签到成功！' + result.msg)
                else:
                    message = '> <font color="red">' + my_site.site.name + ' 签到失败！' + result.msg + '</font>  \n'
                    message_list = message + message_list
                logging.error(my_site.site.name + '签到失败！原因：' + result.msg)
            return message_list

    # @transaction.atomic
    def sign_in(self, my_site: MySite):
        """签到"""
        site = my_site.site
        print(site.name + '开始签到')
        signin_today = my_site.signin_set.filter(created_at__date__gte=datetime.today()).first()
        # 如果已有签到记录
        if signin_today and (signin_today.sign_in_today is True):
            # pass
            return CommonResponse.success(msg='已签到，请勿重复签到！')
        else:
            signin_today = SignIn(site=my_site, sign_in_today=False, sign_in_info='')
        url = site.url + site.page_sign_in.lstrip('/')
        print('签到链接：', url)
        try:
            # with lock:
            if 'totheglory' in site.url:
                result = self.sign_in_ttg(my_site)
                if result.code == StatusCodeEnum.OK.code:
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = result.msg
                    signin_today.save()
                return result
            if 'u2.dmhy.org' in site.url:
                result = self.sign_in_u2(my_site)
                if result.code == StatusCodeEnum.OK.code:
                    print(result.data)
                    return CommonResponse.success(
                        status=StatusCodeEnum.OK,
                        msg='签到成功！'
                    )
                else:
                    return result
            if 'hdsky.me' in site.url:
                result = self.sign_in_hdsky(my_site=my_site, captcha=site.sign_in_captcha)
                if result.code == StatusCodeEnum.OK.code:
                    res_json = result.data
                    if res_json.get('success'):
                        # 签到成功
                        bonus = res_json.get('message')
                        days = (int(bonus) - 10) / 2 + 1
                        signin_today.sign_in_today = True
                        message = '成功,已连续签到{}天,魔力值加{},明日继续签到可获取{}魔力值！'.format(
                            days,
                            bonus,
                            bonus + 2
                        )
                        signin_today.sign_in_info = message
                        signin_today.save()
                        return CommonResponse.success(
                            status=StatusCodeEnum.OK,
                            msg=message
                        )
                    elif res_json.get('message') == 'date_unmatch':
                        # 重复签到
                        message = '您今天已经在其他地方签到了哦！'
                        signin_today.sign_in_today = True
                        signin_today.sign_in_info = message
                        signin_today.save()
                        return CommonResponse.success(
                            msg=message
                        )
                    elif res_json.get('message') == 'invalid_imagehash':
                        # 验证码错误
                        return CommonResponse.error(
                            status=StatusCodeEnum.IMAGE_CODE_ERR,
                        )
                    else:
                        # 签到失败
                        return CommonResponse.error(
                            status=StatusCodeEnum.FAILED_SIGN_IN,
                        )
                else:
                    # 签到失败
                    return result
            if 'hdarea.co' in site.url:
                res = self.send_request(my_site=my_site,
                                        method=site.sign_in_method,
                                        url=url,
                                        data=eval(site.sign_in_params), )
                if res.status_code == 200:
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = res.content.decode('utf8')
                    signin_today.save()
                    return CommonResponse.success(msg=res.text)
                elif res.status_code == 503:
                    return CommonResponse.error(
                        status=StatusCodeEnum.COOKIE_EXPIRE,
                    )
                else:
                    return CommonResponse.error(
                        status=StatusCodeEnum.WEB_CONNECT_ERR,
                        msg=StatusCodeEnum.WEB_CONNECT_ERR.errmsg + '签到失败！'
                    )
            res = self.send_request(my_site=my_site, method=site.sign_in_method, url=url,
                                    data=eval(site.sign_in_params))

            if 'hares.top' in site.url:
                print(res.text)
                code = res.json().get('code')
                print('白兔返回码：', type(code))
                message = ''
                if int(code) == 0:
                    """
                    "datas": {
                      "id": 2273,
                      "uid": 2577,
                      "added": "2022-08-03 12:52:36",
                      "points": "200",
                      "total_points": 5435,
                      "days": 42,
                      "total_days": 123,
                      "added_time": "12:52:36",
                      "is_updated": 1
                    }
                    """
                    message_template = '签到成功！奖励奶糖{},奶糖总奖励是{},您已连续签到{}天，签到总天数{}天！'
                    data = res.json().get('datas')
                    message = message_template.format(data.get('points'),
                                                      data.get('total_points'),
                                                      data.get('days'),
                                                      data.get('total_days'))
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = message
                    signin_today.save()
                    return CommonResponse.success(msg=message)
                elif int(code) == 1:
                    message = res.json().get('msg')
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = message
                    signin_today.save()
                    return CommonResponse.success(
                        msg=message
                    )
                else:
                    return CommonResponse.error(
                        status=StatusCodeEnum.FAILED_SIGN_IN
                    )
            if 'btschool' in site.url:
                print(res.content.decode('utf-8'))
                text = self.parse(res, '//script/text()')
                if len(text) > 0:
                    location = self.parse_school_location(text)
                    print('学校签到链接：', location)
                    if 'addbouns.php' in location:
                        self.send_request(my_site=my_site, url=site.url + location.lstrip('/'))
                        signin_today.sign_in_today = True
                        signin_today.sign_in_info = '签到成功！'
                        signin_today.save()
                        return CommonResponse.success(msg='签到成功！')
                    else:
                        signin_today.sign_in_today = True
                        signin_today.sign_in_info = '签到成功！'
                        signin_today.save()
                        return CommonResponse.success(
                            msg='请勿重复签到！'
                        )
                elif res.status_code == 200:
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = '签到成功！'
                    signin_today.save()
                    return CommonResponse.success(msg='签到成功！')
                else:
                    return CommonResponse.error(msg='签到失败！')
                # print(res.text)
            if res.status_code == 200:
                title_parse = self.parse(res, '//td[@id="outer"]//td[@class="embedded"]/h2/text()')
                content_parse = self.parse(res, '//td[@id="outer"]//td[@class="embedded"]/table/tr/td//text()')
                if len(content_parse) <= 0:
                    title_parse = self.parse(res, '//td[@id="outer"]//td[@class="embedded"]/b[1]/text()')
                    content_parse = self.parse(res, '//td[@id="outer"]//td[@class="embedded"]/text()[1]')
                title = ''.join(title_parse).strip()
                # print(content_parse)
                content = ''.join(content_parse).strip().replace('\n', '')
                # print(content)
                message = title + ',' + content
                # message = ''.join(title).strip()
                signin_today.sign_in_today = True
                signin_today.sign_in_info = message
                signin_today.save()
                return CommonResponse.success(msg=message)
            else:
                return CommonResponse.error(msg='请确认签到是否成功？？网页返回码：' + str(res.status_code))
        except Exception as e:
            # raise
            self.send_text(site.name + '签到失败！原因：' + str(e))
            return CommonResponse.error(msg='签到失败！' + str(e))

    @staticmethod
    def parse(response, rules):
        return etree.HTML(response.content.decode('utf8')).xpath(rules)

    def send_torrent_info_request(self, my_site: MySite):
        site = my_site.site
        url = site.url + site.page_default.lstrip('/')
        # print(url)
        try:
            response = self.send_request(my_site, url)
            print(site.name, response.status_code)
            if response.status_code == 200:
                return CommonResponse.success(data=response)
            elif response.status_code == 503:
                return CommonResponse.error(status=StatusCodeEnum.WEB_CLOUD_FLARE)
            else:
                return CommonResponse.error(msg="网站访问失败")
        except Exception as e:
            # raise
            self.send_text(site.name + '网站访问失败！原因：' + str(e))
            return CommonResponse.error(msg="网站访问失败" + str(e))

    # @transaction.atomic
    def get_torrent_info_list(self, my_site: MySite, response: Response):
        count = 0
        new_count = 0
        site = my_site.site
        # print(response.text.encode('utf8'))
        try:
            with lock:
                if site.url == 'https://www.hd.ai/':
                    # print(response.text)
                    torrent_info_list = response.json().get('data').get('items')
                    print('海带首页种子数目', len(torrent_info_list))
                    for torrent_json_info in torrent_info_list:
                        # print(torrent_json_info.get('download'))
                        magnet_url = site.url + torrent_json_info.get('download')
                        sale_num = torrent_json_info.get('promotion_time_type')
                        # print(type(sale_status))
                        if sale_num == 1:
                            continue
                        # print(type(sale_num))
                        name = torrent_json_info.get('name')
                        title = torrent_json_info.get('small_descr')
                        download_url = site.url + torrent_json_info.get('download').lstrip('/')
                        result = TorrentInfo.objects.update_or_create(download_url=download_url, defaults={
                            'category': torrent_json_info.get('category'),
                            'site': site,
                            'name': name,
                            'title': title if title != '' else name,
                            'magnet_url': magnet_url,
                            'poster_url': torrent_json_info.get('poster'),
                            'detail_url': torrent_json_info.get('details'),
                            'sale_status': TorrentBaseInfo.sale_list.get(sale_num),
                            'sale_expire': torrent_json_info.get('promotion_until'),
                            'hr': True,
                            'on_release': torrent_json_info.get('added'),
                            'size': int(torrent_json_info.get('size')),
                            'seeders': torrent_json_info.get('seeders'),
                            'leechers': torrent_json_info.get('leechers'),
                            'completers': torrent_json_info.get('times_completed'),
                            'save_path': '/downloads/brush'
                        })
                        # print(result[0].site.url)
                        if not result[1]:
                            count += 1
                        else:
                            new_count += 1
                            # print(torrent_info)
                else:
                    # response = self.send_request()
                    trs = self.parse(response, site.torrents_rule)
                    # print(response.text)
                    # print(trs)
                    # print(len(trs))
                    for tr in trs:
                        # print(tr)
                        # print(etree.tostring(tr))
                        sale_status = ''.join(tr.xpath(site.sale_rule))
                        print('sale_status:', sale_status)
                        # 非免费种子跳过
                        if not sale_status:
                            print('非免费种子跳过')
                            continue
                        title_list = tr.xpath(site.title_rule)
                        print(title_list)
                        title = ''.join(title_list).strip().strip('剩余时间：').strip('剩餘時間：').strip('()')
                        name = ''.join(tr.xpath(site.name_rule))
                        if not name and not title:
                            print('无名无姓？跳过')
                            continue
                        # sale_status = ''.join(re.split(r'[^\x00-\xff]', sale_status))
                        sale_status = sale_status.upper().replace(
                            'FREE', 'Free'
                        ).replace('免费', 'Free').replace(' ', '')
                        # # 下载链接，下载链接已存在则跳过
                        href = ''.join(tr.xpath(site.magnet_url_rule))
                        print('href', href)
                        magnet_url = site.url + href.replace('&type=zip', '').replace(site.url, '').lstrip('/')
                        if href.count('passkey') <= 0 and href.count('&sign=') <= 0:
                            download_url = magnet_url + '&passkey=' + my_site.passkey
                        else:
                            download_url = magnet_url
                        print('download_url', download_url)
                        print('magnet_url', magnet_url)

                        # if sale_status == '2X':
                        #     sale_status = '2XFree'

                        # 如果种子有HR，则为否 HR绿色表示无需，红色表示未通过HR考核
                        hr = False if tr.xpath(site.hr_rule) else True
                        # H&R 种子有HR且站点设置不下载HR种子,跳过，
                        if not hr and not site.hr:
                            print('hr种子，未开启HR跳过')
                            continue
                        # # 促销到期时间
                        sale_expire = ''.join(tr.xpath(site.sale_expire_rule))
                        if site.url in [
                            'https://www.beitai.pt/',
                            'http://www.oshen.win/',
                            'https://www.hitpt.com/',
                            'https://hdsky.me/',
                            'https://pt.keepfrds.com/',
                            # 'https://totheglory.im/',
                        ]:
                            """
                            由于备胎等站优惠结束日期格式特殊，所以做特殊处理,使用正则表达式获取字符串中的时间
                            """
                            sale_expire = ''.join(
                                re.findall(r'\d{4}\D\d{2}\D\d{2}\D\d{2}\D\d{2}\D', ''.join(sale_expire)))

                        if site.url in [
                            'https://totheglory.im/',
                        ]:
                            # javascript: alert('Freeleech将持续到2022年09月20日13点46分,加油呀~')
                            # 获取时间数据
                            time_array = re.findall(r'\d+', ''.join(sale_expire))
                            # 不组9位
                            time_array.extend([0, 0, 0, 0])
                            # 转化为标准时间字符串
                            sale_expire = time.strftime(
                                "%Y-%m-%d %H:%M:%S",
                                time.struct_time(tuple([int(x) for x in time_array]))
                            )
                        #     pass
                        # print(sale_expire)
                        # 如果促销结束时间为空，则为无限期
                        sale_expire = '无限期' if not sale_expire else sale_expire
                        # print(torrent_info.sale_expire)
                        # # 发布时间
                        on_release = ''.join(tr.xpath(site.release_rule))
                        # # 做种人数
                        seeders = ''.join(tr.xpath(site.seeders_rule))
                        # # # 下载人数
                        leechers = ''.join(tr.xpath(site.leechers_rule))
                        # # # 完成人数
                        completers = ''.join(tr.xpath(site.completers_rule))
                        # 存在则更新，不存在就创建
                        # print(type(seeders), type(leechers), type(completers), )
                        # print(seeders, leechers, completers)
                        # print(''.join(tr.xpath(site.name_rule)))
                        category = ''.join(tr.xpath(site.category_rule))
                        file_parse_size = ''.join(tr.xpath(site.size_rule))
                        # file_parse_size = ''.join(tr.xpath(''))
                        print(file_parse_size)
                        file_size = FileSizeConvert.parse_2_byte(file_parse_size)
                        # title = title if title else name
                        poster_url = ''.join(tr.xpath(site.poster_rule))  # 海报链接
                        detail_url = site.url + ''.join(
                            tr.xpath(site.detail_url_rule)
                        ).replace(site.url, '').lstrip('/')
                        print('name：', site)
                        print('size', file_size, )
                        print('category：', category, )
                        print('download_url：', download_url, )
                        print('magnet_url：', magnet_url, )
                        print('title：', title, )
                        print('poster_url：', poster_url, )
                        print('detail_url：', detail_url, )
                        print('sale_status：', sale_status, )
                        print('sale_expire：', sale_expire, )
                        print('seeders：', seeders, )
                        print('leechers：', leechers)
                        print('H&R：', hr)
                        print('completers：', completers)
                        result = TorrentInfo.objects.update_or_create(site=site, detail_url=detail_url, defaults={
                            'category': category,
                            'download_url': download_url,
                            'magnet_url': magnet_url,
                            'name': name,
                            'title': title,
                            'poster_url': poster_url,  # 海报链接
                            'detail_url': detail_url,
                            'sale_status': sale_status,
                            'sale_expire': sale_expire,
                            'hr': hr,
                            'on_release': on_release,
                            'size': file_size,
                            'seeders': seeders if seeders else '0',
                            'leechers': leechers if leechers else '0',
                            'completers': completers if completers else '0',
                            'save_path': '/downloads/brush'
                        })
                        print('拉取种子：', site.name, result[0])
                        # time.sleep(0.5)
                        if not result[1]:
                            count += 1
                        else:
                            new_count += 1
                            # print(torrent_info)
                if count + new_count <= 0:
                    return CommonResponse.error(msg='抓取失败或无促销种子！')
                return CommonResponse.success(data=(new_count, count))
        except Exception as e:
            # raise
            self.send_text(site.name + '解析种子信息：失败！原因：' + str(e))
            return CommonResponse.error(msg='解析种子页面失败！' + str(e))

    # 从种子详情页面爬取种子HASH值
    def get_hash(self, torrent_info: TorrentInfo):
        site = torrent_info.site
        url = site.url + torrent_info.detail_url

        response = self.send_request(site.mysite, url)
        # print(site, url, response.text)
        # html = self.parse(response, site.hash_rule)
        # has_string = self.parse(response, site.hash_rule)
        # magnet_url = self.parse(response, site.magnet_url_rule)
        hash_string = self.parse(response, '//tr[10]//td[@class="no_border_wide"][2]/text()')
        magnet_url = self.parse(response, '//a[contains(@href,"downhash")]/@href')
        torrent_info.hash_string = hash_string[0].replace('\xa0', '')
        torrent_info.magnet_url = magnet_url[0]
        print('种子HASH及下载链接：', hash_string, magnet_url)
        torrent_info.save()
        # print(''.join(html))
        # torrent_hash = html[0].strip('\xa0')
        # TorrentInfo.objects.get(id=torrent_info.id).update(torrent_hash=torrent_hash)

    # 生产者消费者模式测试
    def send_status_request(self, my_site: MySite):
        site = my_site.site
        user_detail_url = site.url + site.page_user.lstrip('/').format(my_site.user_id)
        print(user_detail_url)
        # uploaded_detail_url = site.url + site.page_uploaded.lstrip('/').format(my_site.user_id)
        seeding_detail_url = site.url + site.page_seeding.lstrip('/').format(my_site.user_id)
        # completed_detail_url = site.url + site.page_completed.lstrip('/').format(my_site.user_id)
        # leeching_detail_url = site.url + site.page_leeching.lstrip('/').format(my_site.user_id)
        try:
            # 发送请求，做种信息与正在下载信息，个人主页
            user_detail_res = self.send_request(my_site=my_site, url=user_detail_url, timeout=25)
            # if leeching_detail_res.status_code != 200:
            #     return site.name + '种子下载信息获取错误，错误码：' + str(leeching_detail_res.status_code), False
            if user_detail_res.status_code != 200:
                return CommonResponse.error(
                    status=StatusCodeEnum.WEB_CONNECT_ERR,
                    msg=site.name + '个人主页访问错误，错误码：' + str(user_detail_res.status_code)
                )
            # print(user_detail_res.status_code)
            # print('个人主页：', user_detail_res.content)
            # 解析HTML
            # print(user_detail_res.is_redirect)

            if 'totheglory' in site.url:
                # ttg的信息都是直接加载的，不需要再访问其他网页，直接解析就好
                details_html = etree.HTML(user_detail_res.content)
                seeding_html = details_html.xpath('//div[@id="ka2"]/table')[0]
            else:
                details_html = etree.HTML(converter.convert(user_detail_res.content))
                if 'btschool' in site.url:
                    text = details_html.xpath('//script/text()')
                    if len(text) > 0:
                        location = self.parse_school_location(text)
                        print('学校重定向链接：', location)
                        if '__SAKURA' in location:
                            res = self.send_request(my_site=my_site, url=site.url + location.lstrip('/'), timeout=25)
                            details_html = etree.HTML(res.text)
                            # print(res.content)
                seeding_detail_res = self.send_request(my_site=my_site, url=seeding_detail_url, timeout=25)
                # leeching_detail_res = self.send_request(my_site=my_site, url=leeching_detail_url, timeout=25)
                if seeding_detail_res.status_code != 200:
                    return CommonResponse.error(
                        status=StatusCodeEnum.WEB_CONNECT_ERR,
                        msg=site.name + '做种信息访问错误，错误码：' + str(seeding_detail_res.status_code)
                    )
                seeding_html = etree.HTML(converter.convert(seeding_detail_res.text))
            # leeching_html = etree.HTML(leeching_detail_res.text)
            # print(seeding_detail_res.content.decode('utf8'))
            return CommonResponse.success(data={
                'details_html': details_html,
                'seeding_html': seeding_html,
                # 'leeching_html': leeching_html
            })
        except NewConnectionError as nce:
            return CommonResponse.error(
                status=StatusCodeEnum.WEB_CONNECT_ERR,
                msg='打开网站失败，请检查网站是否维护？？')
        except ReadTimeout as e:
            return CommonResponse.error(
                status=StatusCodeEnum.WEB_CONNECT_ERR,
                msg='网站访问超时，请检查网站是否维护？？')
        except Exception as e:
            message = my_site.site.name + '访问个人主页信息：失败！原因：' + str(e)
            logging.error(message)
            self.send_text(message)
            # raise
            return CommonResponse.error(msg=message)

    @staticmethod
    def parse_school_location(text: list):
        print('解析学校访问链接', text)
        list1 = [x.strip().strip('"') for x in text[0].split('+')]
        list2 = ''.join(list1).split('=', 1)[1]
        return list2.strip(';').strip('"')

    @staticmethod
    def parse_message_num(messages: str):
        """
        解析网站消息条数
        :param messages:
        :return:
        """
        list1 = messages.split('(')
        if len(list1) > 1:
            count = re.sub(u"([^(\u0030-\u0039])", "", list1[1])
        elif len(list1) == 1:
            count = messages
        else:
            count = 0
        return int(count)

    # @transaction.atomic
    def parse_status_html(self, my_site: MySite, result: dict):
        """解析个人状态"""
        with lock:
            site = my_site.site
            details_html = result.get('details_html')
            seeding_html = result.get('seeding_html')
            # leeching_html = result.get('leeching_html')
            # 获取指定元素
            # title = details_html.xpath('//title/text()')
            # seed_vol_list = seeding_html.xpath(site.record_bulk_rule)
            seed_vol_list = seeding_html.xpath(site.seed_vol_rule)
            if len(seed_vol_list) > 0:
                seed_vol_list.pop(0)
            print('seeding_vol', len(seed_vol_list))
            # 做种体积
            seed_vol_all = 0
            for seed_vol in seed_vol_list:
                # print(etree.tostring(seed_vol))
                vol = ''.join(seed_vol.xpath('.//text()'))
                print(vol)
                if not len(vol) <= 0:
                    seed_vol_all += FileSizeConvert.parse_2_byte(
                        vol.replace('i', '')  # U2返回字符串为mib，gib
                    )
                else:
                    # seed_vol_all = 0
                    pass
            print('做种体积：', FileSizeConvert.parse_2_file_size(seed_vol_all))
            # print(''.join(seed_vol_list).strip().split('：'))
            # print(title)
            # print(etree.tostring(details_html))
            # leech = self.get_user_torrent(leeching_html, site.leech_rule)
            # seed = self.get_user_torrent(seeding_html, site.seed_rule)
            leech = re.sub(r'\D', '', ''.join(details_html.xpath(site.leech_rule)).strip())
            seed = ''.join(details_html.xpath(site.seed_rule)).strip()
            if not leech and not seed:
                return CommonResponse.error(
                    status=StatusCodeEnum.WEB_CONNECT_ERR,
                    msg=StatusCodeEnum.WEB_CONNECT_ERR.errmsg + '请检查网站访问是否正常？'
                )
            # seed = len(seed_vol_list)

            downloaded = ''.join(
                details_html.xpath(site.downloaded_rule)
            ).replace(':', '').replace('\xa0\xa0', '').replace('i', '').strip(' ')
            downloaded = FileSizeConvert.parse_2_byte(downloaded)
            uploaded = ''.join(
                details_html.xpath(site.uploaded_rule)
            ).replace(':', '').replace('i', '').strip(' ')
            uploaded = FileSizeConvert.parse_2_byte(uploaded)

            invitation = ''.join(
                details_html.xpath(site.invitation_rule)
            ).strip(']:').replace('[', '').strip()
            invitation = re.sub("\D", "", invitation)
            # time_join_1 = ''.join(
            #     details_html.xpath(site.time_join_rule)
            # ).split('(')[0].strip('\xa0').strip()
            # print('注册时间：', time_join_1)
            # time_join = time_join_1.replace('(', '').replace(')', '').strip('\xa0').strip()
            # if not my_site.time_join and time_join:
            #     my_site.time_join = time_join

            # 去除字符串中的中文
            my_level_1 = ''.join(
                details_html.xpath(site.my_level_rule)
            ).replace('_Name', '').strip()
            if 'city' in site.url:
                my_level = my_level_1.strip()
            elif 'u2' in site.url:
                my_level = ''.join(re.findall(r'/(.*).{4}', my_level_1)).title()
            else:
                my_level = re.sub(u"([^\u0041-\u005a\u0061-\u007a])", "", my_level_1)
            # my_level = re.sub('[\u4e00-\u9fa5]', '', my_level_1)
            # print('正则去除中文：', my_level)
            # latest_active = ''.join(
            #     details_html.xpath(site.latest_active_rule)
            # ).strip('\xa0').strip()
            # if '(' in latest_active:
            #     latest_active = latest_active.split('(')[0].strip()

            # 获取字符串中的魔力值
            my_sp = ''.join(
                details_html.xpath(site.my_sp_rule)
            ).replace(',', '').strip()
            print('魔力：', details_html.xpath(site.my_sp_rule))

            if my_sp:
                my_sp = get_decimals(my_sp)

            my_bonus_1 = ''.join(
                details_html.xpath(site.my_bonus_rule)
            ).strip('N/A').replace(',', '').strip()
            if my_bonus_1 != '':
                my_bonus = get_decimals(my_bonus_1)
            else:
                my_bonus = 0
            # if '（' in my_bonus:
            #     my_bonus = my_bonus.split('（')[0]

            hr = ''.join(details_html.xpath(site.my_hr_rule)).split(' ')[0]

            my_hr = hr if hr else '0'

            # print(my_bonus)
            # 更新我的站点数据
            invitation = converter.convert(invitation)
            invitation = re.sub('[\u4e00-\u9fa5]', '', invitation)
            if invitation == '没有邀请资格':
                invitation = 0
            my_site.invitation = int(invitation) if invitation else 0

            my_site.latest_active = datetime.now()
            my_site.my_level = my_level if my_level != '' else ' '
            if my_hr:
                my_site.my_hr = my_hr
            my_site.seed = int(seed) if seed else 0
            print(leech)
            my_site.leech = int(leech) if leech else 0

            print('站点：', site)
            print('等级：', my_level, )
            print('魔力：', my_sp, )
            print('积分：', my_bonus if my_bonus else 0)
            # print('分享率：', ratio, )
            print('下载量：', downloaded, )
            print('上传量：', uploaded, )
            print('邀请：', invitation, )
            # print('注册时间：', time_join, )
            # print('最后活动：', latest_active)
            print('H&R：', my_hr)
            print('上传数：', seed)
            print('下载数：', leech)
            try:
                ratio = ''.join(
                    details_html.xpath(site.ratio_rule)
                ).replace(',', '').replace('无限', 'inf').replace('∞', 'inf').replace('---', 'inf').strip(']:').strip()
                # 分享率告警通知
                print('ratio', ratio)
                if ratio and ratio != 'inf' and float(ratio) <= 1:
                    message = '# <font color="red">' + site.name + ' 站点分享率告警：' + str(ratio) + '</font>  \n'
                    self.send_text(message)
                # 检查邮件
                mail_str = ''.join(details_html.xpath(site.mailbox_rule))
                notice_str = ''.join(details_html.xpath(site.notice_rule))
                if mail_str or notice_str:
                    mail_count = re.sub(u"([^\u0030-\u0039])", "", mail_str)
                    notice_count = re.sub(u"([^\u0030-\u0039])", "", notice_str)
                    mail_count = int(mail_count) if mail_count else 0
                    notice_count = int(notice_count) if notice_count else 0
                    my_site.mail = mail_count + notice_count
                    if mail_count + notice_count > 0:
                        template = '### <font color="red">{} 有{}条新短消息，请注意及时查收！</font>'
                        # 测试发送网站消息原内容
                        self.send_text(template.format(site.name, mail_count + notice_count) + mail_str + notice_str)
                if mail_str or notice_str:
                    my_site.mail = 0
                res_sp_hour = self.get_hour_sp(my_site=my_site)
                if res_sp_hour.code != StatusCodeEnum.OK.code:
                    logging.error(my_site.site.name + res_sp_hour.msg)
                else:
                    my_site.sp_hour = res_sp_hour.data
                # 保存上传下载等信息
                my_site.save()
                # 外键反向查询
                # status = my_site.sitestatus_set.filter(updated_at__date__gte=datetime.datetime.today())
                # print(status)
                result = SiteStatus.objects.update_or_create(site=my_site, created_at__date__gte=datetime.today(),
                                                             defaults={
                                                                 'ratio': float(ratio) if ratio else 0,
                                                                 'downloaded': int(downloaded),
                                                                 'uploaded': int(uploaded),
                                                                 'my_sp': float(my_sp),
                                                                 'my_bonus': float(my_bonus) if my_bonus != '' else 0,
                                                                 # 做种体积
                                                                 'seed_vol': seed_vol_all,
                                                             })
                # print(result) # result 本身就是元祖
                return CommonResponse.success(data=result)
            except Exception as e:
                message = my_site.site.name + '解析个人主页信息：失败！原因：' + str(e)
                logging.error(message)
                # raise
                self.send_text('# <font color="red">' + message + '</font>  \n')
                return CommonResponse.error(msg=message)

    def get_hour_sp(self, my_site: MySite):
        """获取时魔"""
        site = my_site.site
        try:
            response = self.send_request(
                my_site=my_site,
                url=site.url + site.page_mybonus,
            )
            """
            if 'btschool' in site.url:
            # print(response.content.decode('utf8'))
            url = self.parse(response, '//form[@id="challenge-form"]/@action[1]')
            data = {
                'md': ''.join(self.parse(response, '//form[@id="challenge-form"]/input[@name="md"]/@value')),
                'r': ''.join(self.parse(response, '//form[@id="challenge-form"]/input[@name="r"]/@value'))
            }
            print(data)
            print('学校时魔页面url：', url)
            response = self.send_request(
                my_site=my_site,
                url=site.url + ''.join(url).lstrip('/'),
                method='post',
                # headers=headers,
                data=data
            )
            """
            res = converter.convert(response.content)
            # print('时魔响应', response.content)
            # print('转为简体的时魔页面：', str(res))
            # res_list = self.parse(res, site.hour_sp_rule)
            res_list = etree.HTML(res).xpath(site.hour_sp_rule)
            if 'u2.dmhy.org' in site.url:
                res_list = ''.join(res_list).split('，')
                res_list.reverse()
            print('时魔字符串', res_list)
            if len(res_list) <= 0:
                CommonResponse.error(msg='时魔获取失败！')
            return CommonResponse.success(
                data=get_decimals(res_list[0])
            )
        except Exception as e:
            message = '时魔获取失败！'
            logging.error(site.name + message)
            return CommonResponse.success(
                msg=message,
                data=0
            )
