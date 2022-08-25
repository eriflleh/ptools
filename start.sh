#!/bin/bash

CONTAINER_ALREADY_STARTED="CONTAINER_ALREADY_STARTED_PLACEHOLDER"
if [ ! -e $CONTAINER_ALREADY_STARTED ]; then
  echo "-- First container startup --"
  # 拉取文件
  if [ ! -f ptools ]; then

    git clone https://gitee.com/ngfchl/ptools
  fi
  #  进入文件夹
  cd ptools &&
    git init &&
    git remote add origin https://gitee.com/ngfchl/ptools &&
    # 设置拉取最新文件并覆盖
    git config pull.ff only &&
    git pull
  git checkout master &&
    git branch --set-upstream-to=origin/master master
  python -m pip install --upgrade pip &&
    pip install -r requirements.txt &&
    python manage.py makemigrations &&
    python manage.py migrate &&
    python manage.py loaddata pt.json
  # 此处插入你要执行的命令或者脚本文件
  # 创建超级用户
  DJANGO_SUPERUSER_USERNAME=$DJANGO_SUPERUSER_USERNAME \
    DJANGO_SUPERUSER_EMAIL=$DJANGO_SUPERUSER_EMAIL \
    DJANGO_SUPERUSER_PASSWORD=$DJANGO_SUPERUSER_PASSWORD \
    python manage.py createsuperuser --noinput &&
    touch $CONTAINER_ALREADY_STARTED
else
  echo "-- Not first container startup --"
  cd ptools &&
    pip install -r requirements.txt
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
