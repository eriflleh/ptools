import logging
import re
import threading
import time
from datetime import datetime

import aip
import cloudscraper
import opencc
from django.db import transaction
from django.db.models import QuerySet
from lxml import etree
from pypushdeer import PushDeer
from requests import Response
from urllib3.exceptions import NewConnectionError
from wechat_push import WechatPush
from wxpusher import WxPusher

from auto_pt.models import Notify, OCR
from pt_site.models import MySite, SignIn, TorrentInfo, SiteStatus
from ptools.base import TorrentBaseInfo, PushConfig, CommonResponse, StatusCodeEnum


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
                 user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko)',
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
        for notify in notifies:
            if notify.name == PushConfig.wechat_work_push:
                """企业微信通知"""
                notify_push = WechatPush(
                    corp_id=notify.corpid,
                    secret=notify.corpsecret,
                    agent_id=notify.agentid, )
                res = notify_push.send_markdown(text)

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
                res = pushdeer.send_markdown(text)
                print(res)

            if notify.name == PushConfig.bark_push:
                url = notify.custom_server + notify.corpsecret + '/' + text
                res = self.get_scraper().get(url=url)
                print(res)

    def send_request(self,
                     my_site: MySite,
                     url: str,
                     method: str = 'get',
                     data: dict = None,
                     timeout: int = 20,
                     delay: int = 15,
                     proxies: dict = None):
        site = my_site.site
        scraper = self.get_scraper(delay=delay)
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
                proxies=proxies
            )
        return scraper.get(
            url=url,
            headers=self.headers,
            cookies=self.cookies2dict(my_site.cookie),
            data=data,
            timeout=timeout,
            proxies=proxies,
        )

    def ocr_captcha(self, img_url):
        """百度OCR高精度识别，传入图片URL"""
        # 获取百度识别结果
        ocr = OCR.objects.filter(enable=True).first()
        if not ocr:
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
            print('天空验证码：', imagestring, len(imagestring))
            # 识别错误就重来
            times = 0
            while len(imagestring) != 6 and times <= 5:
                print('验证码长度：', len(imagestring), len(imagestring) == 6)
                time.sleep(1)
                self.ocr_captcha(img_url)
                times += 1
            return CommonResponse.success(
                status=StatusCodeEnum.OK,
                data=imagestring,
            )
        except Exception as e:
            print(str(e))
            # raise
            return CommonResponse.error(
                status=StatusCodeEnum.OCR_ACCESS_ERR,
                msg=StatusCodeEnum.OCR_ACCESS_ERR.errmsg + str(e)
            )

    """ paddleocr本地识别出问题，暂时放弃
        def paddle_ocr(self, img_src: str):
        # paddle_ocr调用识别验证码,本地识别没有合适的结果再向百度OCR请求
            paddle = PaddleOCR(use_angle_cls=True, lang='en')
            try:
                # result = paddle.ocr(img_src, cls=True)
                result = paddle.ocr(img_src)
                times = 0
                print(result)
                for line in result:
                    code = line[-1][0].strip()
                    print(code)
                    if len(code) != 6 and times <= 5:
                        times += 1
                        # print(times)
                        self.paddle_ocr(img_src)
                    # else:
                    if len(code) == 6:
                        return CommonResponse.success(
                            data=code
                        )
                        # 如果本地OCR失败就是用百度OCR
                return self.ocr_captcha(img_url=img_src)
            except Exception as e:
                print(str(e))
                return CommonResponse.error(msg='本地OCR识别失败！' + str(e))
    """

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
            ocr_result = self.ocr_captcha(img_get_url)
            if ocr_result.code == StatusCodeEnum.OK.code:
                imagestring = ocr_result.data
            else:
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

    def sign_in(self, my_site: MySite):
        """签到"""
        site = my_site.site
        print(site.name + '开始签到')
        signin_today = my_site.signin_set.filter(updated_at__date__gte=datetime.today()).first()
        # 如果已有签到记录
        if signin_today and signin_today.sign_in_today:
            # pass
            return CommonResponse.success(msg='已签到，请勿重复签到！')
        else:
            signin_today = SignIn(site=my_site)
        url = site.url + site.page_sign_in.lstrip('/')
        # print(url)
        try:
            # with lock:
            if 'hdsky.me' in site.url:
                result = self.sign_in_hdsky(my_site=my_site, captcha=site.sign_in_captcha)
                if result.code == StatusCodeEnum.OK.code:
                    res_json = result.data
                    if res_json.get('success'):
                        # 签到成功
                        bonus = res_json.get('message')
                        days = (int(bonus) - 10) / 2 + 1
                        signin_today.sign_in_today = True
                        signin_today.save()
                        message = '成功,已连续签到{}天,魔力值加{},明日继续签到可获取{}魔力值！'.format(days, bonus, bonus + 2)
                        return CommonResponse.success(
                            status=StatusCodeEnum.OK,
                            msg=message
                        )
                    elif res_json.get('message') == 'invalid_imagehash':
                        # 验证码错误
                        return CommonResponse.error(
                            status=StatusCodeEnum.IMAGE_CODE_ERR,
                        )
                    elif res_json.get('message') == 'date_unmatch':
                        # 重复签到
                        signin_today.sign_in_today = True
                        signin_today.save()
                        return CommonResponse.success(
                            msg='今天已签到了哦！'
                        )
                    else:
                        # 签到失败
                        return CommonResponse.error(
                            status=StatusCodeEnum.FAILED_SIGN_IN,
                        )
            if 'hdarea.co' in site.url:
                res = self.send_request(my_site=my_site,
                                        method=site.sign_in_method,
                                        url=url,
                                        data=eval(site.sign_in_params), )
                if res.status_code == 200:
                    signin_today.sign_in_today = True
                    signin_today.save()
                    return CommonResponse.success(msg=res.text)
                elif res.status_code == 503:
                    return CommonResponse.error(
                        status=StatusCodeEnum.WEB_CLOUD_FLARE,
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
                    signin_today.save()
                    return CommonResponse.success(msg=message)
                elif int(code) == 1:
                    signin_today.sign_in_today = True
                    signin_today.save()
                    return CommonResponse.success(
                        msg=res.json().get('msg')
                    )
                else:
                    return CommonResponse.error(
                        status=StatusCodeEnum.FAILED_SIGN_IN
                    )
            if 'btschool' in site.url:
                # print(res.content.decode('utf-8'))
                text = self.parse(res, '//script/text()')
                if len(text) > 0:
                    location = self.parse_school_location(text)
                    if 'addbouns.php' in location:
                        self.send_request(my_site=my_site, url=site.url + location.lstrip('/'))
                        signin_today.sign_in_today = True
                        signin_today.save()
                        return CommonResponse.success(msg='签到成功！')
                    else:
                        return CommonResponse.success(
                            msg='请勿重复签到！'
                        )
                signin_today.sign_in_today = True
                signin_today.save()
                return CommonResponse.success(msg='签到成功！')
                # print(res.text)
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
            signin_today.save()
            return CommonResponse.success(msg=message)
        except Exception as e:
            # raise
            return CommonResponse.error(msg='签到失败！' + str(e))

    @staticmethod
    def parse(response, rules):
        return etree.HTML(response.text).xpath(rules)

    def send_torrent_info_request(self, my_site: MySite):
        site = my_site.site
        url = site.url + site.page_default.lstrip('/')
        # print(url)
        try:
            response = self.send_request(my_site, url)
            if response.status_code == 200:
                return CommonResponse.success(data=response)
            elif response.status_code == 503:
                return CommonResponse.error(status=StatusCodeEnum.WEB_CLOUD_FLARE)
            else:
                return CommonResponse.error(msg="网站访问失败")
        except Exception as e:
            return CommonResponse.error(msg="网站访问失败" + str(e))

    @transaction.atomic
    def get_torrent_info_list(self, my_site: MySite, response: Response):
        count = 0
        new_count = 0
        site = my_site.site
        print(response)
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
                        # print('sale_status:', sale_status)
                        if not sale_status:
                            continue
                        sale_status = ''.join(re.split(r'[^\x00-\xff]', sale_status))
                        sale_status = sale_status.upper().replace('FREE', 'Free').replace(' ', '')
                        # # 下载链接，下载链接已存在则跳过
                        href = ''.join(tr.xpath(site.magnet_url_rule))
                        # print(href)
                        magnet_url = site.url + href.replace('&type=zip', '').replace(site.url, '')
                        if href.count('passkey') <= 0 and href.count('&sign=') <= 0:
                            download_url = magnet_url + '&passkey=' + my_site.passkey
                        else:
                            download_url = magnet_url
                        # print(download_url)
                        # print(magnet_url)
                        title_list = tr.xpath(site.title_rule)
                        print(title_list)
                        title = ''.join(title_list).strip().strip('剩余时间：').strip('剩餘時間：').strip('()')

                        # if sale_status == '2X':
                        #     sale_status = '2XFree'
                        # # H&R 如果设置为不下载HR种子，且种子HR为真,跳过
                        hr = True if ''.join(tr.xpath(site.hr_rule)) else False
                        # print(torrent.hr)
                        if hr and not site.hr:
                            continue
                        # # 促销到期时间
                        sale_expire = ''.join(tr.xpath(site.sale_expire_rule))
                        if site.url in [
                            'https://www.beitai.pt/',
                            'http://www.oshen.win/',
                            'https://www.hitpt.com/',
                            'https://hdsky.me/',
                        ]:
                            """
                            由于备胎等站优惠结束日期格式特殊，所以做特殊处理,使用正则表达式获取字符串中的时间
                            """
                            sale_expire = ''.join(
                                re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', ''.join(sale_expire)))
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
                        name = ''.join(tr.xpath(site.name_rule))
                        category = ''.join(tr.xpath(site.category_rule))
                        file_parse_size = ''.join(tr.xpath(site.size_rule))
                        # file_parse_size = ''.join(tr.xpath(''))
                        print(file_parse_size)
                        file_size = FileSizeConvert.parse_2_byte(file_parse_size)
                        # title = title if title else name
                        poster_url = ''.join(tr.xpath(site.poster_rule))  # 海报链接
                        detail_url = ''.join(tr.xpath(site.detail_url_rule))
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
                        result = TorrentInfo.objects.update_or_create(download_url=download_url, defaults={
                            'category': category,
                            'magnet_url': magnet_url,
                            'site': site,
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
        leeching_detail_url = site.url + site.page_leeching.lstrip('/').format(my_site.user_id)
        try:
            # 发送请求，做种信息与正在下载信息，个人主页
            seeding_detail_res = self.send_request(my_site=my_site, url=seeding_detail_url, timeout=25)
            # leeching_detail_res = self.send_request(my_site=my_site, url=leeching_detail_url, timeout=25)
            user_detail_res = self.send_request(my_site=my_site, url=user_detail_url, timeout=25)
            if seeding_detail_res.status_code != 200:
                return CommonResponse.error(
                    status=StatusCodeEnum.WEB_CONNECT_ERR,
                    msg=site.name + '做种信息访问错误，错误码：' + str(seeding_detail_res.status_code)
                )
            # if leeching_detail_res.status_code != 200:
            #     return site.name + '种子下载信息获取错误，错误码：' + str(leeching_detail_res.status_code), False
            if user_detail_res.status_code != 200:
                return CommonResponse.error(
                    status=StatusCodeEnum.WEB_CONNECT_ERR,
                    msg=site.name + '个人主页访问错误，错误码：' + str(user_detail_res.status_code)
                )
            # print(user_detail_res.status_code)
            # print('个人主页：', user_detail_res.content.decode('utf8'))
            # 解析HTML
            # print(user_detail_res.is_redirect)
            details_html = etree.HTML(user_detail_res.content)
            if 'school' in site.url:
                text = details_html.xpath('//script/text()')
                if len(text) > 0:
                    location = self.parse_school_location(text)
                    print('学校重定向链接：', location)
                    if '__SAKURA' in location:
                        res = self.send_request(my_site=my_site, url=site.url + location.lstrip('/'), timeout=25)
                        details_html = etree.HTML(res.text)
                        # print(res.content)
            seeding_html = etree.HTML(seeding_detail_res.text)
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
                msg='链接网站失败，请检查网站是否维护状态？？')
        except Exception as e:
            message = my_site.site.name + '访问个人主页信息：失败！原因：' + str(e)
            logging.error(message)
            # raise
            return CommonResponse.error(msg=message)

    @staticmethod
    def parse_school_location(text: list):
        print('解析学校访问链接', text)
        list1 = [x.strip().strip('"') for x in text[0].split('+')]
        list2 = ''.join(list1).split('=', 1)[1]
        return list2.strip(';').strip('"')

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
                    # print(vol)
                    if not len(vol) <= 0:
                        seed_vol_all += FileSizeConvert.parse_2_byte(vol)
            else:
                seed_vol_all = 0
            print('做种体积：', FileSizeConvert.parse_2_file_size(seed_vol_all))
            # print(''.join(seed_vol_list).strip().split('：'))
            # print(title)
            # print(etree.tostring(details_html))
            # leech = self.get_user_torrent(leeching_html, site.leech_rule)
            # seed = self.get_user_torrent(seeding_html, site.seed_rule)
            leech = ''.join(details_html.xpath(site.leech_rule)).strip()
            seed = ''.join(details_html.xpath(site.seed_rule)).strip()
            # seed = len(seed_vol_list)
            ratio = ''.join(details_html.xpath(site.ratio_rule)).replace(',', '').strip(']:').strip()
            if ratio == '无限' or ratio == '∞' or ratio == '---':
                # inf表示无限
                ratio = 'inf'
            downloaded = ''.join(
                details_html.xpath(site.downloaded_rule)
            ).replace(':', '').replace('\xa0\xa0', '').strip(' ')

            uploaded = ''.join(
                details_html.xpath(site.uploaded_rule)
            ).replace(':', '').strip(' ')

            invitation = ''.join(
                details_html.xpath(site.invitation_rule)
            ).strip(']:').replace('[', '').strip()
            invitation = re.sub("\D", "", invitation)
            # print('正则只保留数字', invitation)
            # invitation = ''.join(
            #     details_html.xpath(site.invitation_rule)
            # ).replace('[已签到]', '').replace('[签到]', '').strip(']:').replace('[', '').strip()
            time_join_1 = ''.join(
                details_html.xpath(site.time_join_rule)
            ).split('(')[0].strip('\xa0').strip()
            # print('注册时间：', time_join_1)
            time_join = time_join_1.replace('(', '').replace(')', '').strip('\xa0').strip()
            if not my_site.time_join and time_join:
                my_site.time_join = time_join

            # 去除字符串中的中文
            my_level_1 = ''.join(
                details_html.xpath(site.my_level_rule)
            ).replace('_Name', '').strip()
            if 'city' in site.url:
                my_level = my_level_1.strip()
            else:
                my_level = re.sub(u"([^\u0041-\u005a\u0061-\u007a])", "", my_level_1)
            # my_level = re.sub('[\u4e00-\u9fa5]', '', my_level_1)
            # print('正则去除中文：', my_level)
            latest_active_1 = ''.join(
                details_html.xpath(site.latest_active_rule)
            ).split('(')[0].strip('\xa0').strip()
            latest_active = latest_active_1.replace('(', '').replace(')', '').strip()

            # my_sp = ''.join(
            #     details_html.xpath(site.my_sp_rule)
            # ).replace(' ', '').replace('(', '').replace(')', '').replace(',', '').strip(']:').strip()
            # 获取字符串中的魔力值
            my_sp = ''.join(
                details_html.xpath(site.my_sp_rule)
            )
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

            if site.url == 'https://www.pttime.org/':
                my_sp = re.findall('-?\d+.?\d+', my_sp)[-1]

            hr = ''.join(details_html.xpath(site.my_hr_rule)).split(' ')[0]

            my_hr = hr if hr else '0'

            # print(my_bonus)
            # 更新我的站点数据
            invitation = converter.convert(invitation)
            invitation = re.sub('[\u4e00-\u9fa5]', '', invitation)
            if invitation == '没有邀请资格':
                invitation = 0
            my_site.invitation = int(invitation) if invitation else 0

            my_site.latest_active = latest_active if latest_active != '' else datetime.now()
            my_site.my_level = my_level if my_level != '' else ' '
            if my_hr:
                my_site.my_hr = my_hr
            my_site.seed = int(seed)
            print(leech)
            my_site.leech = int(leech)

            print('站点：', site)
            print('等级：', my_level, )
            print('魔力：', my_sp, )
            print('积分：', my_bonus if my_bonus else 0)
            print('分享率：', ratio, )
            print('下载量：', downloaded, )
            print('上传量：', uploaded, )
            print('邀请：', invitation, )
            print('注册时间：', time_join, )
            print('最后活动：', latest_active)
            print('H&R：', my_hr)
            print('上传数：', seed)
            print('下载数：', leech)
            try:
                res_sp_hour = self.get_hour_sp(my_site=my_site)
                if not res_sp_hour[1]:
                    logging.error(my_site.site.name + '时魔获取失败！')
                else:
                    my_site.sp_hour = res_sp_hour[0]
                # 保存上传下载等信息
                my_site.save()
                # 外键反向查询
                # status = my_site.sitestatus_set.filter(updated_at__date__gte=datetime.datetime.today())
                # print(status)
                result = SiteStatus.objects.update_or_create(site=my_site, updated_at__date__gte=datetime.today(),
                                                             defaults={
                                                                 'ratio': float(ratio) if ratio else 0,
                                                                 'downloaded': downloaded,
                                                                 'uploaded': uploaded,
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
                return CommonResponse.error(msg=message)

    def get_hour_sp(self, my_site: MySite):
        """获取时魔"""
        site = my_site.site
        response = self.send_request(
            my_site=my_site,
            url=site.url + site.page_mybonus,
        )
        res = converter.convert(response.content)
        print('时魔响应', response.status_code)
        # print('转为简体的时魔页面：', str(res))
        # res_list = self.parse(res, site.hour_sp_rule)
        res_list = etree.HTML(res).xpath(site.hour_sp_rule)
        print('时魔字符串', res_list)
        if len(res_list) <= 0:
            return '时魔获取失败！', False
        return get_decimals(res_list[0]), True
