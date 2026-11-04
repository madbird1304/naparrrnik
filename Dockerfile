# Frozen environment for the original voice: balcon.exe + "ELAN TTS Russian
# (Nicolai 16Khz)" under wine. ubuntu:22.04 is pinned on purpose: it ships the
# exact wine 6.0.3 the voice was verified with, a different wine is a risk of a
# different sound. The binaries in vendor/ are not in git, see vendor.sha256.
FROM --platform=linux/amd64 ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y \
        wine=6.0.3~repack-1 wine32:i386=6.0.3~repack-1 wine64=6.0.3~repack-1 \
        ffmpeg locales python3 python3-pip xvfb \
    && sed -i 's/^# *ru_RU.UTF-8/ru_RU.UTF-8/' /etc/locale.gen && locale-gen \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN printf 'pcm.!default { type null }\nctl.!default { type null }\n' > /etc/asound.conf

RUN useradd -u 1000 -m naparrnik

COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

ADD vendor/wineprefix.tar.gz /opt/
ADD vendor/balcon.tar.gz /opt/
COPY patch-msvcirt.py /tmp/patch-msvcirt.py
RUN python3 /tmp/patch-msvcirt.py /opt/wineprefix/drive_c/windows/system32/msvcirt.dll \
        "/opt/wineprefix/drive_c/Program Files/Elan/msvcirt.dll" \
    && rm /tmp/patch-msvcirt.py \
    && chown -R naparrnik:naparrnik /opt/wineprefix

COPY config.py /app/config.py
COPY pizdani /app/pizdani
COPY speech /app/speech
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Wine derives its ANSI codepage from the locale: without ru_RU the voice reads
# the cp1251 input as garbage.
ENV LC_ALL=ru_RU.UTF-8 LANG=ru_RU.UTF-8 PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 \
    WINEPREFIX=/opt/wineprefix WINEARCH=win32 WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml=;msvcirt=n,b" \
    CACHE_DIR=/tmp/naparrnik SS_BINARY=/opt/balcon/balcon.exe DISPLAY=:99

USER naparrnik
WORKDIR /app
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python3", "-O", "-m", "pizdani"]
