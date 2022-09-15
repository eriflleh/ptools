# myproject/Dockerfile

# 建立 python3.9 环境
FROM python:3.9-slim

# 镜像作者大江狗
MAINTAINER ngfchl ngfchl@126.com

# 设置 python 环境变量
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SUPERUSER_USERNAME=admin
ENV DJANGO_SUPERUSER_EMAIL=admin@eamil.com
ENV DJANGO_SUPERUSER_PASSWORD=adminadmin
ENV MARIADB_ROOT_PASSWORD=adminadmin
ENV DJANGO_WEB_PORT=8000

COPY pip.conf /root/.pip/pip.conf

# 创建 myproject 文件夹
RUN mkdir -p /var/www/html/ptools

# 将 myproject 文件夹为工作目录
WORKDIR /var/www/html/ptools

# 将当前目录加入到工作目录中（. 表示当前目录）
ADD . /var/www/html/ptools
ADD ./start.sh /var/www/html

# 更新pip版本
#RUN /usr/local/bin/python -m pip install --upgrade pip

# 利用 pip 安装依赖
#RUN pip install -r requirements.txt

# 去除windows系统编辑文件中多余的\r回车空格
# RUN sed -i 's/\r//' ./start.sh

# 给start.sh可执行权限
RUN chmod +x /var/www/html/start.sh

# 更换USTC源，并安装gcc，git
RUN #sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list && apt update && yes|apt install gcc git && yes|apt autoremove gcc &&  apt-get autoclean
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list  \
    && apt update  \
#    && yes|apt upgrade  \
    && yes|apt install git gcc mariadb-server default-libmysqlclient-dev build-essential \
    && pip install -r requirements.txt -U \
    && yes|apt autoremove gcc  \
    && yes|apt autoremove  \
    &&  apt-get autoclean  \
    && service mariadb start \
    && rm -rf /var/lib/apt/lists/* \
    && mysqladmin -u root password $MARIADB_ROOT_PASSWORD

VOLUME ["/var/lib/mysql"]

EXPOSE  $DJANGO_WEB_PORT

EXPOSE 3306

ENTRYPOINT ["/bin/bash", "/var/www/html/start.sh"]