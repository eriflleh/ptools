import json
import os
import subprocess
from datetime import datetime

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from pt_site import views as tasks
from pt_site.models import SiteStatus, MySite
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
    tasks.auto_sign_in.delay()
    return JsonResponse('ok!', safe=False)


def test_field(request):
    my_site = MySite.objects.get(pk=1)
    list1 = SiteStatus.objects.filter(site=my_site, created_at__date__gte=datetime.today())
    print(list1)
    return JsonResponse('ok!', safe=False)


def test_notify(request):
    """
    app_id：28987
    uid:	UID_jkMs0DaVVwOcBuFPQGzymjCwYVgH
    应用名称：pt_helper
    appToken：AT_ShUnRu2CJRcsqbbW540voVkjMZ1PKjGy
    """
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


def restart_container(request):
    # scraper = pt_spider.get_scraper()
    # res = scraper.get('https://gitee.com/ngfchl/ptools/raw/master/update.md')
    # update_md = markdown.markdown(res.text, extensions=['tables'])

    # 拉取更新元数据
    update_log = subprocess.Popen('git remote update', shell=True)
    update_log.wait()
    # 获取本地更新日志第一条
    p_local = subprocess.Popen('git log --oneline -1', shell=True, stdout=subprocess.PIPE, )
    commit_local = p_local.stdout.readline().decode('utf8').strip()
    # 获取远端仓库更新日志第一条
    p_remote = subprocess.Popen('git log origin/master --oneline -1', shell=True, stdout=subprocess.PIPE, )
    commit_remote = p_remote.stdout.readline().decode('utf8').strip()
    print(commit_local, commit_remote)
    # if 'HEAD' in commit and 'origin' in commit:
    print(commit_remote == commit_local)
    # 如果日志相同则更新到最新，否则显示远端更新日志
    if commit_remote == commit_local:
        update = 'false'
        update_tips = '目前您使用的是最新版本！'
    else:
        update = 'true'
        update_tips = '已有新版本，请根据需要升级！'
    restart = 'false'
    if os.environ.get('CONTAINER_NAME'):
        restart = 'true'
    return render(request, 'auto_pt/restart.html',
                  context={
                      # 'update_md': update_md,
                      'local_logs': get_git_logs(),
                      'update_notes': get_git_logs(master='origin/master'),
                      'restart': restart,
                      'update': update,
                      'update_tips': update_tips,
                  })

#
# def do_get_update(request):
#     update = 'false'
#     # 拉取更新元数据
#     update_log = subprocess.Popen('git remote update', shell=True)
#     update_log.wait()
#     # 获取本地更新日志第一条
#     p_local = subprocess.Popen('git log --oneline -1', shell=True, stdout=subprocess.PIPE, )
#     commit_local = p_local.stdout.readline().decode('utf8').strip()
#     # 获取远端仓库更新日志第一条
#     p_remote = subprocess.Popen('git log origin/master --oneline -1', shell=True, stdout=subprocess.PIPE, )
#     commit_remote = p_remote.stdout.readline().decode('utf8').strip()
#     print(commit_local, commit_remote)
#     # if 'HEAD' in commit and 'origin' in commit:
#     print(commit_remote == commit_local)
#     # 如果日志相同则更新到最新，否则显示远端更新日志
#     if commit_remote == commit_local:
#         return JsonResponse(data=CommonResponse.success(
#             msg='已经更新到最新！',
#             data={
#                 'update_notes': get_git_logs(master='origin/master'),
#             }
#         ).to_dict(), safe=False)
#     else:
#         update = 'true'
#         return JsonResponse(data=CommonResponse.success(
#             msg='拉取更新日志成功！!',
#             data={
#                 'update': update,
#                 'update_notes': get_git_logs(master='origin/master'),
#             }
#         ).to_dict(), safe=False)


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
        with open('main_pt_site_site.sql', encoding='utf-8') as sql_file:
            contents = sql_file.readlines()
            print(contents[0])
            with connection.cursor() as cursor:
                for statement in contents:
                    cursor.execute(statement)
        # Site.objects.raw()
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
        print('重启')
        # print(os.system('pwd'))
        if os.environ.get('CONTAINER_NAME'):
            subprocess.Popen('chmod +x ./restart.sh', shell=True)
            subprocess.Popen('./restart.sh', shell=True)
            return JsonResponse(data=CommonResponse.success(
                msg='容器重启中！!'
            ).to_dict(), safe=False)
        return JsonResponse(data=CommonResponse.error(
            msg='未配置CONTAINER_NAME（容器名称）环境变量，请自行重启容器！!'
        ).to_dict(), safe=False)
    except Exception as e:
        return JsonResponse(data=CommonResponse.error(
            msg='重启指令发送失败!' + str(e)
        ).to_dict(), safe=False)
