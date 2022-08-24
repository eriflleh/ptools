#!/bin/bash

# 安装依赖
pip install -r requirements.txt

CONTAINER_ALREADY_STARTED="CONTAINER_ALREADY_STARTED_PLACEHOLDER"
if [ ! -f ./db/db.sqlite3 ]; then
  echo "-- 初始化数据库 init database --"
  # 如果数据库存在，就不执行
  python manage.py makemigrations &&
    python manage.py migrate &&
    python manage.py loaddata pt.json
#  mv db.sqlite3 ./db/db.sqlite3
fi
if [ ! -e $CONTAINER_ALREADY_STARTED ]; then
  touch $CONTAINER_ALREADY_STARTED
  echo "-- First container startup --"
  # 此处插入你要执行的命令或者脚本文件
  # 安装依赖
  #  mv db.sqlite3 ./db/sqlite3 &&
  # 导入数据 person.json为自定义
  #  python manage.py loaddata person.json &&
  # 创建超级用户
  DJANGO_SUPERUSER_USERNAME=$DJANGO_SUPERUSER_USERNAME \
    DJANGO_SUPERUSER_EMAIL=$DJANGO_SUPERUSER_EMAIL \
    DJANGO_SUPERUSER_PASSWORD=$DJANGO_SUPERUSER_PASSWORD \
    python manage.py createsuperuser --noinput
else
  echo "-- Not first container startup --"
fi

python manage.py migrate &&
  python manage.py runserver 0.0.0.0 $DJANGO_WEB_PORT --noreload
