# myproject/Dockerfile

# 建立 python3.9 环境
FROM python:3.9.13

# 镜像作者大江狗
MAINTAINER ngfchl ngfchl@126.com

# 设置 python 环境变量
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SUPERUSER_USERNAME=admin
ENV DJANGO_SUPERUSER_EMAIL=admin@eamil.com
ENV DJANGO_SUPERUSER_PASSWORD=adminadmin
ENV DJANGO_WEB_PORT=8000

COPY pip.conf /root/.pip/pip.conf

# 创建 myproject 文件夹
RUN mkdir -p /var/www/html/

# 将 myproject 文件夹为工作目录
WORKDIR /var/www/html/

# 将当前目录加入到工作目录中（. 表示当前目录）
#ADD . /var/www/html/ptools
ADD ./start.sh /var/www/html/
# 更新pip版本
#RUN /usr/local/bin/python -m pip install --upgrade pip

# 利用 pip 安装依赖
#RUN pip install -r requirements.txt

# 去除windows系统编辑文件中多余的\r回车空格
# RUN sed -i 's/\r//' ./start.sh

# 给start.sh可执行权限
RUN chmod +x ./start.sh

# 安装redis
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list

#RUN apt update
#RUN yes|apt install libgl1-mesa-glx
#RUN yes|apt install redis-server

VOLUME ["/var/www/html/ptools/db"]
VOLUME ["/var/www/html/ptools"]

EXPOSE  8000
#ENTRYPOINT ["redis-server","/etc/redis/redis.conf"]
#ENTRYPOINT ["/bin/bash", "first.sh"]
ENTRYPOINT ["/bin/bash", "start.sh"]