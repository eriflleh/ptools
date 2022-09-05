# 先备份数据库文件再拉取更新 $(date "+%Y%m%d%H%M%S")当前时间年月日时分秒
cp /var/www/html/ptools/db/db.sqlite3 /var/www/html/ptools/db/db.sqlite3-$(date "+%Y%m%d%H%M%S") &&
  git pull &&
  mv -f /var/www/html/ptools/start.sh /var/www/html/start.sh &&
  python manage.py makemigrations &&
  python manage.py migrate
