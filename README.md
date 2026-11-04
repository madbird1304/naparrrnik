# Напарррник

Telegram-бот, который озвучивает текст голосом ELAN TTS Russian (Nicolai 16Khz)
через `balcon.exe` под Wine. Весь смысл в этом голосе, поэтому движок и версия
Wine зафиксированы в образе. Это x86-образ, на ARM он работает через QEMU.

- В личке бот озвучивает любое сообщение.
- В группе нужна команда `/pizdani текст`.
- В любом чате работает inline: `@naparrrnik_bot текст`, затем выбрать «Озвучить».
  Сначала появится заглушка, потом она сменится на аудио. Уже озвученная фраза
  сразу придёт настоящим голосовым.

## Настройка

1. Скопировать `.envrc.template` в `.envrc` и заполнить `TG_BOT_TOKEN`.
   Для inline нужен `INLINE_STORAGE_CHAT`: чат, куда бот на секунду загружает
   файлы. `INLINE_USERS` пустой значит, что inline открыт для всех.
2. В `@BotFather` включить inline (`/setinline`) и `/setinlinefeedback` в
   значение **Enabled**. Вероятности вроде `1/100` не подходят: сообщения
   застрянут на заглушке.
3. Положить в `vendor/` файлы `wineprefix.tar.gz` и `balcon.tar.gz`. Их нет в git,
   потому что репозиторий публичный. Проверка: `cd vendor && sha256sum -c ../vendor.sha256`.
4. На ARM поставить Docker и эмуляцию x86:

   ```sh
   sudo apt-get install -y docker.io docker-buildx qemu-user-binfmt
   sudo usermod -aG docker "$USER"
   ```

## Запуск и перезапуск контейнера

```sh
set -a; . ./.envrc; set +a
docker rm -f naparrnik
docker run -d --name naparrnik --restart unless-stopped --platform linux/amd64 \
  -e TG_BOT_TOKEN -e INLINE_STORAGE_CHAT -e INLINE_USERS naparrnik:latest
```

Логи: `docker logs -f naparrnik`.

Один токен может опрашивать только один бот. Перед запуском на другой машине
остановите контейнер на старой.

## Обновление кода

Если менялся только код (`pizdani`, `speech`), образ собирается за секунды, в том
числе на ARM: всё остальное берётся из уже имеющегося образа.

```sh
git pull
DOCKER_BUILDKIT=0 docker build --cache-from naparrnik:latest -t naparrnik:latest .
```

Затем пересоздайте контейнер командой из раздела выше.

## Полная сборка

Нужна, если менялись `vendor/` или шаги Dockerfile выше кода. Собирать надо на x86:
на ARM шаг `apt` падает на `ldconfig` под QEMU. Потом образ переносится, это
примерно 8 минут:

```sh
docker build -t naparrnik:latest .                            # на x86
ssh x86-host docker save naparrnik:latest | docker load       # на ARM
```

Шаг с `apt` кэшируется, пока команды до него не менялись.

## Что важно для звука

- `vendor/` собирается из рабочего префикса командой
  `make-vendor.py PREFIX_DIR BALCON_DIR OLD_PREFIX_PATH`: она чинит абсолютные
  симлинки, в том числе на `sapi.dll`.
- `LC_ALL=ru_RU.UTF-8` обязателен: Wine берёт из локали кодировку ANSI, а текст
  идёт в cp1251. Иначе голос читает мусор.
- Движку нужны окно и звуковое устройство, даже при записи в файл. Без X он
  виснет, без аудио звучит иначе. Поэтому в образе Xvfb и нулевое устройство ALSA.
- `patch-msvcirt.py` чинит лишние слова. Движок завершает строку через `<< ends`,
  а `msvcirt` из Wine не записывает этот ноль, и остатки буфера читаются вслух.
- Символы вне cp1251, например эмодзи, бот не озвучивает. В личке он промолчит,
  в inline напишет «Не смог озвучить».
