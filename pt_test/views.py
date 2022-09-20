# Create your views here.
import json

from django.http import JsonResponse
from django.shortcuts import render

from pt_site.views import pt_spider
from ptools.base import CommonResponse, StatusCodeEnum


def test_import(request):
    if request.method == 'GET':
        return render(request, 'pt_test/test_import.html')
    else:
        data_list = json.loads(request.body).get('user')
        res = pt_spider.parse_ptpp_cookies(data_list)
        if res.code == StatusCodeEnum.OK.code:
            cookies = res.data
            print(cookies)
        else:
            return JsonResponse(res.to_dict(), safe=False)
        message_list = []
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
        return JsonResponse(CommonResponse.success(data={
            'messages': message_list
        }).to_dict(), safe=False)


def handle_json(request):
    if request.method == 'GET':
        return render(request, 'pt_test/test_json.html')


def test_post(request):
    if request.method == 'GET':
        return render(request, 'pt_test/test_post.html')
    else:
        r = request.POST
        for i, j in r.items():
            print(i, type(i))
            print(j, type(j))
        print(r)
        return JsonResponse(CommonResponse.success(data=r).to_dict(), safe=False)
