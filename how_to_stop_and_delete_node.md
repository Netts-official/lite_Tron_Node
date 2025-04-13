# Остановить сервис
sudo systemctl stop tron-node

# Отключить автозапуск
sudo systemctl disable tron-node

# Удалить файл сервиса
sudo rm /etc/systemd/system/tron-node.service

# Перезагрузить systemd для применения изменений
sudo systemctl daemon-reload

# Найти и завершить все процессы java связанные с FullNode
sudo pkill -f "FullNode.jar"

# Проверить, что процессы не работают
ps aux | grep [F]ullNode

# Удалить директорию java-tron
sudo rm -rf /home/java-tron

# Удалить временные файлы, если остались
sudo rm -rf /tmp/tron_*

# Удалить логи установки
sudo rm -f /var/log/tron-installation.log
sudo rm -f /var/log/tron-background-install.log

# Удалить файл настроек Java
sudo rm -f /etc/profile.d/java.sh

# Очистить кэш systemd
sudo systemctl reset-failed
