# Create your views here.
import datetime
import logging
import time
from concurrent.futures.thread import ThreadPoolExecutor

from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore

from pt_site.UtilityTool import PtSpider, MessageTemplate, FileSizeConvert
from pt_site.models import MySite, TorrentInfo
from ptools.base import StatusCodeEnum

job_defaults = {
    'coalesce': True,
    'misfire_grace_time': None
}
executors = {
    'default': ThreadPoolExecutor(2)
}
scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
scheduler.add_jobstore(DjangoJobStore(), 'default')

pool = ThreadPoolExecutor(2)
pt_spider = PtSpider()
# Create your views here.
try:

    def auto_sign_in():
        """自动签到"""
        start = time.time()
        # 获取本人所有站点
        queryset = MySite.objects.all()
        message_list = pt_spider.do_sign_in(pool, queryset)
        end = time.time()
        consuming = '> <font  color="blue">{} 任务运行成功！耗时：{}完成时间：{}  </font>\n'.format(
            '自动签到', end - start,
            time.strftime("%Y-%m-%d %H:%M:%S")
        )
        pt_spider.send_text(message_list + consuming)
        print('{} 任务运行成功！完成时间：{}'.format('自动签到', time.strftime("%Y-%m-%d %H:%M:%S")))


    def auto_get_status():
        """
        更新个人数据
        """
        start = time.time()
        message_list = ''
        queryset = MySite.objects.all()
        site_list = [my_site for my_site in queryset if my_site.site.get_userinfo_support]
        results = pool.map(pt_spider.send_status_request, site_list)
        message_template = MessageTemplate.status_message_template
        for my_site, result in zip(site_list, results):
            if result.code == StatusCodeEnum.OK.code:
                res = pt_spider.parse_status_html(my_site, result.data)
                print('自动更新个人数据', my_site.site, res)
                if res.code == StatusCodeEnum.OK.code:
                    status = res.data[0]
                    message = message_template.format(
                        my_site.my_level,
                        status.my_sp,
                        my_site.sp_hour,
                        status.my_bonus,
                        status.ratio,
                        FileSizeConvert.parse_2_file_size(status.downloaded),
                        FileSizeConvert.parse_2_file_size(status.uploaded),
                        my_site.seed,
                        my_site.leech,
                        my_site.invitation,
                        my_site.my_hr
                    )
                    print('组装Message：', message)
                    message_list += ('> ' + my_site.site.name + ' 信息更新成功！' + message + '  \n')
                    # pt_spider.send_text(my_site.site.name + ' 信息更新成功！' + message)
                    logging.info(my_site.site.name + '信息更新成功！' + message)
                else:
                    print(res)
                    message = '> <font color="red">' + my_site.site.name + ' 信息更新失败！原因：' + res.msg + '</font>  \n'
                    message_list = message + message_list
                    # pt_spider.send_text(my_site.site.name + ' 信息更新失败！原因：' + str(res[0]))
                    logging.error(my_site.site.name + '信息更新失败！原因：' + res.msg)
            else:
                # pt_spider.send_text(my_site.site.name + ' 信息更新失败！原因：' + str(result[1]))
                message = '> <font color="red">' + my_site.site.name + ' 信息更新失败！原因：' + result.msg + '</font>  \n'
                message_list = message + message_list
                logging.error(my_site.site.name + '信息更新失败！原因：' + result.msg)
        end = time.time()
        consuming = '> <font color="blue">{} 任务运行成功！耗时：{} 完成时间：{}  </font>  \n'.format(
            '自动更新个人数据', end - start,
            time.strftime("%Y-%m-%d %H:%M:%S")
        )
        pt_spider.send_text(text=message_list + consuming)


    def auto_update_torrents():
        """
        拉取最新种子
        """
        start = time.time()
        message_list = ''
        queryset = MySite.objects.all()
        site_list = [my_site for my_site in queryset if my_site.site.get_torrent_support]
        results = pool.map(pt_spider.send_torrent_info_request, site_list)
        for my_site, result in zip(site_list, results):
            print('获取种子：', my_site.site, result)
            # print(result is tuple[int])
            if result.code == StatusCodeEnum.OK.code:
                res = pt_spider.get_torrent_info_list(my_site, result.data)
                # 通知推送
                if res.code == StatusCodeEnum.OK.code:
                    message = '> {} 种子抓取成功！新增种子{}条，更新种子{}条!  \n'.format(my_site.site.name, res.data[0], res.data[1])
                    message_list += message
                else:
                    message = '> <font color="red">' + my_site.site.name + '抓取种子信息失败！原因：' + res.msg + '</font>  \n'
                    message_list = message + message_list
                # 日志
                logging.info(
                    '{} 种子抓取成功！新增种子{}条，更新种子{}条! '.format(my_site.site.name, res.data[0], res.data[
                        1]) if res.code == StatusCodeEnum.OK.code else my_site.site.name + '抓取种子信息失败！原因：' + res.msg)
            else:
                # pt_spider.send_text(my_site.site.name + ' 抓取种子信息失败！原因：' + result[0])
                message = '> <font color="red">' + my_site.site.name + ' 抓取种子信息失败！原因：' + result.msg + '</font>  \n'
                message_list = message + message_list
                logging.error(my_site.site.name + '抓取种子信息失败！原因：' + result.msg)
        end = time.time()
        consuming = '> {} 任务运行成功！耗时：{} 当前时间：{}  \n'.format(
            '拉取最新种子',
            end - start,
            time.strftime("%Y-%m-%d %H:%M:%S"))
        pt_spider.send_text(message_list + consuming)


    def auto_remove_expire_torrents():
        """
        删除过期种子
        """
        start = time.time()
        torrent_info_list = TorrentInfo.objects.all().filter(downloader__isnull=False)
        for torrent_info in torrent_info_list:
            expire_time = torrent_info.sale_expire
            if '无限期' in expire_time:
                # ToDo 先更新种子信息，然后再判断
                continue
            if expire_time.endswith(':'):
                expire_time += '00'
            time_now = datetime.datetime.now()
            expire_time_parse = datetime.datetime.strptime(expire_time, '%Y-%m-%d %H:%M:%S')

            if time_now >= expire_time_parse:
                if not torrent_info.downloader:
                    # 未推送到下载器，跳过或删除？
                    continue
                if pt_spider.get_torrent_info_from_downloader(torrent_info).code == StatusCodeEnum.OK.code:
                    # todo 设定任务规则：
                    #  免费到期后，下载完毕的种子是删除还是保留？
                    #  未下载完成的，是暂停还是删除？
                    torrent_info.delete()
        end = time.time()
        pt_spider.send_text(
            '> {} 任务运行成功！耗时：{}{}  \n'.format('签到', end - start, time.strftime("%Y-%m-%d %H:%M:%S")))


    def auto_push_to_downloader():
        """推送到下载器"""
        start = time.time()
        print('推送到下载器')
        end = time.time()
        pt_spider.send_text(
            '> {} 任务运行成功！耗时：{}{}  \n'.format('签到', end - start, time.strftime("%Y-%m-%d %H:%M:%S")))


    def auto_get_torrent_hash():
        """自动获取种子HASH"""
        start = time.time()
        print('自动获取种子HASH')
        time.sleep(5)
        end = time.time()
        pt_spider.send_text(
            '> {} 任务运行成功！耗时：{}{}  \n'.format('获取种子HASH', end - start, time.strftime("%Y-%m-%d %H:%M:%S")))


    scheduler.start()
except Exception as e:
    print(e)
    # 有错误就停止定时器
    scheduler.shutdown()
