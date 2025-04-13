# Скрипт развертывания облегченной полной ноды TRON

## Описание

Этот скрипт предназначен для автоматического развертывания облегченной полной ноды TRON на серверах Ubuntu/Debian. Скрипт выполняет следующие операции:

1. Установка необходимых зависимостей
2. Настройка Java 8 в качестве основной версии
3. Клонирование и сборка репозитория java-tron
4. Автоматический поиск и загрузка последнего доступного архива базы данных для быстрого старта
5. Создание всех конфигурационных файлов
6. Настройка автозапуска через systemd
7. Запуск ноды

## Требования

- Ubuntu 20.04/22.04 или Debian 10/11
- Минимум 16 ГБ ОЗУ (рекомендуется 24 ГБ)
- Минимум 500 ГБ дискового пространства (рекомендуется SSD)
- Права root для установки

## Установка

### Вариант 1: Прямая установка из GitHub

```bash
# Клонирование репозитория
git clone https://github.com/Netts-official/lite_Tron_Node.git
cd lite_Tron_Node

# Делаем скрипт исполняемым
chmod +x install_tron_node.py

# Запускаем скрипт с правами root
sudo nohup python3 install_tron_node.py > /home/lite_Tron_Node/tron-install.log 2>&1 &
или
sudo python3 install_tron_node.py
```

### Проверка логов
```bash
tail -f /home/lite_Tron_Node/tron-install.log
```

### Проверка скрипта
```bash
ps aux | grep python
```

### Вариант 2: Загрузка и запуск скрипта напрямую

```bash
# Загрузка скрипта
wget https://raw.githubusercontent.com/Netts-official/lite_Tron_Node/main/install_tron_node.py

# Делаем скрипт исполняемым
chmod +x install_tron_node.py

# Запускаем скрипт с правами root
sudo python3 install_tron_node.py
```

## Команды управления нодой

### Проверка статуса ноды
```bash
systemctl status tron-node
```

### Запуск ноды
```bash
systemctl start tron-node
```

### Остановка ноды
```bash
systemctl stop tron-node
```

### Перезапуск ноды
```bash
systemctl restart tron-node
```

### Включение автозапуска
```bash
systemctl enable tron-node
```

### Проверка запущенных процессов
```bash
ps aux | grep [F]ullNode
```

### Проверка информации о ноде
```bash
curl http://127.0.0.1:8090/wallet/getnodeinfo
```

### Проверка текущего блока
```bash
curl http://127.0.0.1:8090/wallet/getnowblock

curl -s http://127.0.0.1:8090/wallet/getnodeinfo | grep -o '"block":"[^"]*"' | grep -o 'Num:[0-9]*'
```

## Мониторинг и логи

### Просмотр логов ноды
```bash
journalctl -u tron-node -f
```

### Просмотр последних 100 строк логов
```bash
journalctl -u tron-node -n 100
```

### Просмотр логов за последний час
```bash
journalctl -u tron-node --since "1 hour ago"
```

## Устранение неполадок

### Проблемы с версией Java

Если у вас возникли проблемы с версией Java, вы можете вручную настроить Java 8:

```bash
sudo update-alternatives --config java
# Выберите опцию с java-8-openjdk

sudo update-alternatives --config javac
# Выберите опцию с java-8-openjdk
```

### Проблемы с компиляцией Java-tron

Если вы столкнулись с ошибками во время компиляции, связанными с отсутствием класса `javax.annotation.Generated`, добавьте следующую зависимость в файл `build.gradle`:

```
dependencies {
    implementation 'javax.annotation:javax.annotation-api:1.3.2'
}
```

### Проблемы с загрузкой архива базы данных

Если скрипт не может автоматически найти или загрузить последний архив базы данных, вы можете:

1. Вручную проверить доступные резервные копии:
```bash
curl -s http://34.86.86.229/ | grep -o 'backup[0-9]\{8\}'
```

2. Загрузить архив вручную, используя последнюю доступную резервную копию (замените XXXXXXXX фактической датой):
```bash
wget http://34.86.86.229/backupXXXXXXXX/LiteFullNode_output-directory.tgz -O /tmp/LiteFullNode_output-directory.tgz
mkdir -p /home/java-tron/output-directory
tar -xzf /tmp/LiteFullNode_output-directory.tgz -C /home/java-tron/output-directory
```

## Обновление ноды

Для обновления ноды до последней версии:

```bash
cd /home/java-tron
git pull
./gradlew clean build -x test
systemctl restart tron-node
```

## Дополнительная информация

- Конфигурационный файл: `/home/java-tron/last-conf.conf`
- Скрипт запуска: `/home/java-tron/last-node-start.sh`
- Директория данных: `/home/java-tron/output-directory`
- Systemd сервис: `/etc/systemd/system/tron-node.service`

## Полезные ссылки

- [Официальная документация TRON](https://developers.tron.network/)
- [GitHub репозиторий Java-tron](https://github.com/tronprotocol/java-tron)
- [TRON Explorer](https://tronscan.org/)# lite_Tron_Node
Установка LiteFullNode
