import json
import socket
import subprocess
from datetime import datetime, timedelta

import docker
import git
from django.http import JsonResponse
from django.shortcuts import render

from pt_site import views as tasks
from pt_site.UtilityTool import FileSizeConvert
from pt_site.models import SiteStatus, MySite, Site
from pt_site.views import scheduler, pt_spider
from ptools.base import CommonResponse, StatusCodeEnum


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
    with open('./cookies.json', 'r') as f:
        # print(f.readlines())
        datas = json.load(f)
        cookies = []
        for data in datas:
            domain = data.get('url')
            cookie_list = data.get('cookies')
            cookie_str = ''
            for cookie in cookie_list:
                cookie_str += cookie.get('name') + '=' + cookie.get('value') + ';'
            print(domain, cookie_str)
            cookies.append({
                'domain': domain,
                'cookies': cookie_str.rstrip(';')
            })
        print(len(cookies))
    return JsonResponse('ok', safe=False)


def import_from_ptpp(request):
    if request.method == 'GET':
        return render(request, 'auto_pt/import_ptpp.html')
    else:

        # print(request.body)
        data_list = json.loads(request.body).get('ptpp')
        datas = json.loads(data_list)
        print('content', len(datas))

        res = pt_spider.parse_ptpp_cookies(datas)
        if res.code == StatusCodeEnum.OK.code:
            cookies = res.data
        else:
            return JsonResponse(res.to_dict(), safe=False)
        # success_messages = []
        # error_messages = []
        message_list = []
        # print(datas)

        for data in cookies:
            try:
                print(data)
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
            update_time = datetime.strptime(list1[1].strip(), '%a %b %d %X %Y +0800')
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
        cid = socket.gethostname()
        started_at = client.api.inspect_container(cid).get('State').get('StartedAt')[:-4] + 'Z'
        utc_format = "%Y-%m-%dT%H:%M:%S.%fZ"
        restart = 'true'
        utc_time = datetime.strptime(started_at, utc_format)
        local_time = utc_time + timedelta(hours=8)
        delta = str((datetime.now() - local_time).seconds) + '秒'
        print(delta)
        # delta = local_time.strftime('%Y-%m-%dT%H:%M:%S.%f')
        # delta = delta.astimezone(pytz.timezone('Asia/Shanghai'))
    except Exception as e:
        # raise
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
        p = subprocess.Popen('./update.sh', shell=True, stdout=subprocess.PIPE, bufsize=1)
        p.wait()
        out = p.stdout.readlines()
        for i in out:
            print(i.decode('utf8'))
        # 更新Xpath规则
        print('拉取更新完毕，开始更新Xpath规则')
        # 字符串型的数据量转化为int型
        status_list = SiteStatus.objects.all()
        for status in status_list:
            if not status.downloaded:
                status.downloaded = 0
            if not status.uploaded:
                status.uploaded = 0
            if type(status.downloaded) == str and 'B' in status.downloaded:
                status.downloaded = FileSizeConvert.parse_2_byte(status.downloaded)
            if type(status.uploaded) == str and 'B' in status.uploaded:
                status.uploaded = FileSizeConvert.parse_2_byte(status.uploaded)
            status.save()
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
        print(request.GET.get('restart'))
        flag = request.GET.get('restart') == 'true'
        if flag:
            cid = socket.gethostname()
            subprocess.Popen('docker restart {}'.format(cid), shell=True, stdout=subprocess.PIPE, )
        # out = reboot.stdout.readline().decode('utf8')
        # client.api.inspect_container(cid)
        # StartedAt = client.api.inspect_container(cid).get('State').get('StartedAt')
        return JsonResponse(data=CommonResponse.error(
            msg='更新成功，重启指令发送成功，容器重启中 ...' if flag else '更新成功，未映射docker路径请手动重启容器 ...'
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
            msg='重启指令发送成功，容器重启中 ...'
        ).to_dict(), safe=False)
    except Exception as e:
        return JsonResponse(data=CommonResponse.error(
            msg='重启指令发送失败!' + str(e),
        ).to_dict(), safe=False)
