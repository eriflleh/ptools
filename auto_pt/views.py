import json
import socket
import subprocess
import time
from datetime import datetime, timedelta

import docker
import git
import qbittorrentapi
from django.http import JsonResponse
from django.shortcuts import render

from pt_site import views as tasks
from pt_site.UtilityTool import FileSizeConvert
from pt_site.models import SiteStatus, MySite, Site, Downloader
from pt_site.views import scheduler, pt_spider
from ptools.base import CommonResponse, StatusCodeEnum, DownloaderCategory, TorrentBaseInfo


def add_task(request):
    if request.method == 'POST':
        content = json.loads(request.body.decode())  # 接收参数
        try:
            start_time = content['start_time']  # 用户输入的任务开始时间, '10:00:00'
            start_time = start_time.split(':')
            hour = int(start_time[0])
            minute = int(start_time[1])
            second = int(start_time[2])
            s = content['s']  # 接收执行任务的各种参数
            # 创建任务
            scheduler.add_job(tasks.scheduler, 'cron', hour=hour, minute=minute, second=second, args=[s])
            code = '200'
            message = 'success'
        except Exception as e:
            code = '400'
            message = e

        data = {
            'code': code,
            'message': message
        }
        return JsonResponse(json.dumps(data, ensure_ascii=False), safe=False)


def get_tasks(request):
    # print(dir(tasks))
    data = [key for key in dir(tasks) if key.startswith('auto')]
    print(data)
    # print(tasks.__getattr__)
    # print(tasks.auto_get_status.__doc__)
    # inspect.getmembers(tasks, inspect.isfunction)
    # inspect.getmodule(tasks)
    # print(sys.modules[__name__])
    # print(sys.modules.values())
    # print(sys.modules.keys())
    # print(sys.modules.items())
    return JsonResponse('ok', safe=False)


def exec_task(request):
    # res = AutoPt.auto_sign_in()
    # print(res)
    # tasks.auto_sign_in
    return JsonResponse('ok!', safe=False)


def test_field(request):
    my_site = MySite.objects.get(pk=1)
    list1 = SiteStatus.objects.filter(site=my_site, created_at__date__gte=datetime.today())
    print(list1)
    return JsonResponse('ok!', safe=False)


def test_notify(request):
    # res = NotifyDispatch().send_text(text='66666')

    res = pt_spider.send_text('666')
    print(res)
    return JsonResponse(res, safe=False)


def do_sql(request):
    print('exit')
    return JsonResponse('ok', safe=False)


def page_downloading(request):
    return render(request, 'auto_pt/downloading.html')


def get_downloader(request):
    downloader_list = Downloader.objects.filter(category=DownloaderCategory.qBittorrent).values('id', 'name', 'host')
    if len(downloader_list) <= 0:
        return JsonResponse(CommonResponse.error(msg='请先添加下载器！目前仅支持qBittorrent！').to_dict(), safe=False)
    return JsonResponse(CommonResponse.success(data=list(downloader_list)).to_dict(), safe=False)


def get_downloading(request):
    id = request.GET.get('id')
    print(id)
    downloader = Downloader.objects.filter(id=id).first()

    qb_client = qbittorrentapi.Client(
        host=downloader.host,
        port=downloader.port,
        username=downloader.username,
        password=downloader.password,
        SIMPLE_RESPONSES=True
    )
    try:
        qb_client.auth_log_in()
        torrents = qb_client.torrents_info()
        for torrent in torrents:
            # 时间处理
            # 添加于
            torrent['added_on'] = datetime.fromtimestamp(torrent.get('added_on')).strftime(
                '%Y年%m月%d日%H:%M:%S'
            )
            # 完成于
            if torrent.get('downloaded') == 0:
                torrent['completion_on'] = ''
                torrent['last_activity'] = ''
                torrent['downloaded'] = ''
            else:
                torrent['completion_on'] = datetime.fromtimestamp(torrent.get('completion_on')).strftime(
                    '%Y年%m月%d日%H:%M:%S'
                )
                # 最后活动于
                last_activity = str(timedelta(seconds=time.time() - torrent.get('last_activity')))

                torrent['last_activity'] = last_activity.replace(
                    'days,', '天'
                ).replace(
                    'day,', '天'
                ).replace(':', '小时', 1).replace(':', '分', 1).split('.')[0] + '秒'
                # torrent['last_activity'] = datetime.fromtimestamp(torrent.get('last_activity')).strftime(
                #     '%Y年%m月%d日%H:%M:%S')
            # 做种时间
            seeding_time = str(timedelta(seconds=torrent.get('seeding_time')))
            torrent['seeding_time'] = seeding_time.replace('days,', '天').replace(
                'day,', '天'
            ).replace(':', '小时', 1).replace(':', '分', 1).split('.')[0] + '秒'
            # 大小与速度处理
            torrent['state'] = TorrentBaseInfo.download_state.get(torrent.get('state'))
            torrent['ratio'] = '%.4f' % torrent.get('ratio') if torrent['ratio'] >= 0.0001 else 0
            torrent['progress'] = '%.4f' % torrent.get('progress') if float(torrent['progress']) < 1 else 1
            torrent['uploaded'] = '' if torrent['uploaded'] == 0 else torrent['uploaded']
            torrent['upspeed'] = '' if torrent['upspeed'] == 0 else torrent['upspeed']
            torrent['dlspeed'] = '' if torrent['dlspeed'] == 0 else torrent['dlspeed']
        print(torrents)
        return JsonResponse(CommonResponse.success(data=torrents).to_dict(), safe=False)
    except Exception as e:
        print(e)
        return JsonResponse(CommonResponse.error(
            msg='连接下载器出错咯！'
        ).to_dict(), safe=False)


def import_from_ptpp(request):
    if request.method == 'GET':
        return render(request, 'auto_pt/import_ptpp.html')
    else:
        data_list = json.loads(request.body).get('user')
        res = pt_spider.parse_ptpp_cookies(data_list)
        if res.code == StatusCodeEnum.OK.code:
            cookies = res.data
            # print(cookies)
        else:
            return JsonResponse(res.to_dict(), safe=False)
        message_list = []
        for data in cookies:
            try:
                # print(data)
                res = pt_spider.get_uid_and_passkey(data)
                msg = res.msg
                print(msg)
                if res.code == StatusCodeEnum.OK.code:
                    message_list.append({
                        'msg': msg,
                        'tag': 'success'
                    })
                else:
                    # error_messages.append(msg)
                    message_list.append({
                        'msg': msg,
                        'tag': 'error'
                    })
            except Exception as e:
                message = '{} 站点导入失败！{}  \n'.format(data.get('domain'), str(e))
                message_list.append({
                    'msg': message,
                    'tag': 'warning'
                })
                # raise
        return JsonResponse(CommonResponse.success(data={
            'messages': message_list
        }).to_dict(), safe=False)


def get_git_logs(master='', n=10):
    # 获取最新的10条更新记录
    # master='' 本地 master='origin/master'  远程
    p = subprocess.Popen('git log {} -{}'.format(master, n), shell=True, stdout=subprocess.PIPE, )
    contents = p.stdout.readlines()
    update_notes = []
    info = {
        'date': '',
        'data': []
    }
    for i in contents:
        string = i.decode('utf8')
        if string == '\n' or 'commit' in string or 'Author' in string:
            continue
        if 'Date' in string:
            update_notes.append(info)
            info = {}
            list1 = string.split(':', 1)
            # 格式化时间
            update_time = datetime.strptime(list1[1].strip(), '%a %b %d %H:%M:%S %Y %z')
            info['date'] = update_time.strftime('%Y-%m-%d %H:%M:%S')
            info['data'] = []
            continue
        info['data'].append(string.strip())
    # print(update_notes)
    update_notes.pop(0)
    return update_notes


def get_git_log(master='master', n=10):
    repo = git.Repo(path='.')
    # 拉取仓库更新记录元数据
    repo.remote().update()
    # 获取本地仓库commits更新记录
    commits = list(repo.iter_commits(master, max_count=n))
    # 获取远程仓库commits记录
    # remote_commits = list(repo.iter_commits("origin/master", max_count=10))


def get_update_logs():
    repo = git.Repo(path='.')
    # 拉取仓库更新记录元数据
    repo.remote().update()
    # 获取本地仓库commits更新记录
    commits = list(repo.iter_commits('master', max_count=10))
    # 获取远程仓库commits记录
    remote_commits = list(repo.iter_commits("origin/master", max_count=10))
    return commits[0].hexsha == remote_commits[0].hexsha


def update_page(request):
    try:
        # 获取docker对象
        client = docker.from_env()
        # 从内部获取容器id
        for c in client.api.containers():
            if 'ngfchl/ptools' in c.get('Image'):
                cid = c.get('Id')
                delta = c.get('Status')
                restart = 'true'
    except Exception as e:
        cid = ''
        restart = 'false'
        delta = '程序未在容器中启动？'
    if get_update_logs():
        update = 'false'
        update_tips = '目前您使用的是最新版本！'
    else:
        update = 'true'
        update_tips = '已有新版本，请根据需要升级！'
    return render(request, 'auto_pt/update.html',
                  context={
                      'cid': cid,
                      'delta': delta,
                      'restart': restart,
                      'local_logs': get_git_logs(),
                      'update_notes': get_git_logs(master='origin/master'),
                      'update': update,
                      'update_tips': update_tips
                  })


def do_update(request):
    try:
        print('开始拉取更新')
        # print(os.system('cat ./update.sh'))
        subprocess.Popen('chmod +x ./update.sh', shell=True)
        p = subprocess.Popen('./update.sh', shell=True, stdout=subprocess.PIPE)
        p.wait()
        out = p.stdout.readlines()
        for i in out:
            print(i.decode('utf8'))
        # 更新Xpath规则
        print('拉取更新完毕，开始更新Xpath规则')
        # 字符串型的数据量转化为int型
        # status_list = SiteStatus.objects.all()
        # for status in status_list:
        #     if not status.downloaded:
        #         status.downloaded = 0
        #     if not status.uploaded:
        #         status.uploaded = 0
        #     if type(status.downloaded) == str and 'B' in status.downloaded:
        #         status.downloaded = FileSizeConvert.parse_2_byte(status.downloaded)
        #     if type(status.uploaded) == str and 'B' in status.uploaded:
        #         status.uploaded = FileSizeConvert.parse_2_byte(status.uploaded)
        #     status.save()
        with open('./main_pt_site_site.json', 'r') as f:
            # print(f.readlines())
            data = json.load(f)
            # print(data[2])
            # print(data[0].get('url'))
            # xpath_update = []
            print('更新规则中，返回结果为True为新建，为False为更新，其他是错误了')
            for site_rules in data:
                if site_rules.get('pk'):
                    del site_rules['pk']
                if site_rules.get('id'):
                    del site_rules['id']
                site_obj = Site.objects.update_or_create(defaults=site_rules, url=site_rules.get('url'))
                print(site_obj[0].name + (' 规则新增成功！' if site_obj[1] else '规则更新成功！'))
        print('更新完毕，开始重启')
        cid = request.GET.get('cid')
        flag = (cid == '')
        if not flag:
            subprocess.Popen('docker restart {}'.format(cid), shell=True, stdout=subprocess.PIPE, )
        # out = reboot.stdout.readline().decode('utf8')
        # client.api.inspect_container(cid)
        # StartedAt = client.api.inspect_container(cid).get('State').get('StartedAt')
        return JsonResponse(data=CommonResponse.error(
            msg='更新成功，重启指令发送成功，容器重启中 ...' if not flag else '更新成功，未映射docker路径请手动重启容器 ...'
        ).to_dict(), safe=False)
    except Exception as e:
        # raise
        return JsonResponse(data=CommonResponse.error(
            msg='更新失败!' + str(e)
        ).to_dict(), safe=False)


def do_restart(request):
    try:
        # 获取docker对象
        # client = docker.from_env()
        # 从内部获取容器id
        cid = socket.gethostname()
        # 获取容器对象
        # container = client.containers.get(cid)
        # 重启容器
        # client.api.restart(cid)
        print('重启中')
        reboot = subprocess.Popen('docker restart {}'.format(cid), shell=True, stdout=subprocess.PIPE, )
        # out = reboot.stdout.readline().decode('utf8')
        # print(out)
        # client.api.inspect_container(cid)
        # StartedAt = client.api.inspect_container(cid).get('State').get('StartedAt')
        return JsonResponse(data=CommonResponse.error(
            msg='重启指令发送成功，容器重启中 ... 15秒后自动刷新页面 ...'
        ).to_dict(), safe=False)
    except Exception as e:
        return JsonResponse(data=CommonResponse.error(
            msg='重启指令发送失败!' + str(e),
        ).to_dict(), safe=False)
