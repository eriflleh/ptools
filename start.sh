#!/bin/bash

pip install -r requirements.txt

CONTAINER_ALREADY_STARTED="CONTAINER_ALREADY_STARTED_PLACEHOLDER"
if [ ! -e $CONTAINER_ALREADY_STARTED ]; then
  touch $CONTAINER_ALREADY_STARTED
  echo "-- First container startup --"
  # 拉取文件
  git clone https://gitee.com/ngfchl/ptools &&
    #  进入文件夹
    cd ptools &&
    # 设置拉取最新文件并覆盖
    git config pull.ff only &&
    python manage.py makemigrations &&
    python manage.py migrate &&
    python manage.py loaddata pt.json
  # 此处插入你要执行的命令或者脚本文件
  # 创建超级用户
  DJANGO_SUPERUSER_USERNAME=$DJANGO_SUPERUSER_USERNAME \
    DJANGO_SUPERUSER_EMAIL=$DJANGO_SUPERUSER_EMAIL \
    DJANGO_SUPERUSER_PASSWORD=$DJANGO_SUPERUSER_PASSWORD \
    python manage.py createsuperuser --noinput
else
  echo "-- Not first container startup --"
  if [ ! -f ./db/db.sqlite3 ]; then
    echo "-- 初始化数据库 init database --"
    # 如果数据库存在，就不执行
    python manage.py makemigrations &&
      python manage.py migrate &&
      python manage.py loaddata pt.json
  fi
  python manage.py makemigrations &&
    python manage.py migrate &&
    python manage.py runserver $DJANGO_WEB_PORT --noreload
fi
