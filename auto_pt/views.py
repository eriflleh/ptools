import json
import socket
import subprocess
from datetime import datetime

import docker
import git
from django.http import JsonResponse
from django.shortcuts import render

from pt_site import views as tasks
from pt_site.models import SiteStatus, MySite, Site
from pt_site.views import scheduler, pt_spider
from ptools.base import CommonResponse


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
    # with open('main_pt_site_site.sql', encoding='utf-8') as file_obj:
    #     contents = file_obj.readlines()
    #     with connection.cursor() as cursor:
    #         for statement in contents:
    #             res1 = cursor.execute(statement)
    # print(threading.main_thread().getName())
    try:
        print(0)
    except Exception as e:

        print(e)
    # autoreload.start_django(au)
    # django_main_thread

    return JsonResponse('ok', safe=False)


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
    """
        # commits = [str(commit) for commit in commits]
        # remote_commits = [str(commit) for commit in remote_commits]
        # # for commit in commits:
        # #     print(commit.hexsha)
        # #     print(commit.committed_datetime)
        # #     print(commit.message)
        # return render(request, 'auto_pt/restart.html',
        #               context={
        #                   # 'update_md': update_md,
        #                   'local_logs': commits,
        #                   'update_notes': remote_commits,
        #                   'update': update,
        #                   'update_tips': update_tips,
        #               })
    """
    return commits[0].hexsha == remote_commits[0].hexsha


def restart_container(request):
    # scraper = pt_spider.get_scraper()
    # res = scraper.get('https://gitee.com/ngfchl/ptools/raw/master/update.md')
    # update_md = markdown.markdown(res.text, extensions=['tables'])
    # 获取docker对象
    client = docker.from_env()
    # 从内部获取容器id
    cid = socket.gethostname()
    started_at = client.api.inspect_container(cid).get('State').get('StartedAt')[:19]
    UTC_FORMAT = "%Y-%m-%dT%H:%M:%S"
    utc_time = datetime.strptime(started_at, UTC_FORMAT)
    delta = datetime.now() - utc_time

    if get_update_logs():
        update = 'false'
        update_tips = '目前您使用的是最新版本！'
    else:
        update = 'true'
        update_tips = '已有新版本，请根据需要升级！'
    return render(request, 'auto_pt/restart.html',
                  context={
                      'delta': delta.total_seconds(),
                      'local_logs': get_git_logs(),
                      'update_notes': get_git_logs(master='origin/master'),
                      'update': update,
                      'update_tips': update_tips
                  })


def do_update(request):
    try:
        print('更新')
        # print(os.system('cat ./update.sh'))
        subprocess.Popen('chmod +x ./update.sh', shell=True)
        p = subprocess.Popen('./update.sh', shell=True, stdout=subprocess.PIPE, bufsize=1)
        p.wait()
        out = p.stdout.readlines()
        result = []
        for i in out:
            result.append(i.decode('utf8'))
            print(result)
        # 更新数据库
        with open('./pt_site_site.json', 'r') as f:
            # print(f.readlines())
            data = json.load(f)
            print(data[2])
        print(data[0].get('url'))
        for site in data:
            Site.objects.update_or_create(defaults=site, url=site.get('url'))
        return JsonResponse(data=CommonResponse.success(
            msg='更新成功！!',
            data=result
            # data={
            #     # 'p': str(p.stdout.readlines()).strip("'").strip('[').strip(']').strip()
            # }
        ).to_dict(), safe=False)
    except Exception as e:
        return JsonResponse(data=CommonResponse.error(
            msg='更新指令发送失败!' + str(e)
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
        subprocess.Popen('docker restart {}'.format(cid), shell=True)
        # client.api.inspect_container(cid)
        # StartedAt = client.api.inspect_container(cid).get('State').get('StartedAt')
        return JsonResponse(data=CommonResponse.error(
            msg='重启指令发送成功，容器重启中 ...'
        ).to_dict(), safe=False)
    except Exception as e:
        return JsonResponse(data=CommonResponse.error(
            msg='重启指令发送失败!' + str(e),
        ).to_dict(), safe=False)
