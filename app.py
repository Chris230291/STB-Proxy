# region import
import flask
import threading
import os
import json
import subprocess
import uuid
import logging
import xml.etree.cElementTree as ET
from flask import (
    Flask,
    render_template,
    redirect,
    request,
    Response,
    make_response,
    flash,
    stream_with_context,
)
import math
import time
import requests
from datetime import datetime, timezone
from dateutil.parser import parse
from functools import wraps
import secrets
import waitress
import copy
import ast

# endregion

# region init
app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(32)

logger = logging.getLogger("STB-Proxy")
logFormat = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
fileHandler = logging.FileHandler("STB-Proxy.log")
fileHandler.setFormatter(logFormat)
logger.addHandler(fileHandler)
consoleFormat = logging.Formatter("[%(levelname)s] %(message)s")
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(consoleFormat)
logger.addHandler(consoleHandler)

basePath = os.path.abspath(os.getcwd())

if os.getenv("HOST"):
    host = os.getenv("HOST")
else:
    host = "localhost:8001"

if os.getenv("CONFIG"):
    config_dir = os.getenv("CONFIG")
else:
    config_dir = basePath

if os.getenv("DEBUG"):
    debugString = os.getenv("DEBUG")
    debug = debugString.lower() == "true" or debugString == "1"
    logger.setLevel(logging.DEBUG)
else:
    debug = False
    logger.setLevel(logging.INFO)

settings_file = os.path.join(config_dir, "settings.json")
sources_file = os.path.join(config_dir, "sources.json")

settings = {}
sources = {}
occupied = {}

d_ffmpegcmd = "ffmpeg -re -http_proxy <proxy> -timeout <timeout> -i <url> -map 0 -codec copy -f mpegts pipe:"

default_settings = {
    "stream method": "direct buffer",
    "stream timeout": 5,
    "stream chunk size": 1024,
    "ffmpeg command": "ffmpeg -http_proxy <proxy> -timeout <timeout> -i <url> -codec copy -f mpegts pipe:",
    "test streams": False,
    "use channel groups": True,
    "use channel numbers": True,
    "sort playlists by channel group": False,
    "sort playlists by channel number": False,
    "sort playlists by channel name": False,
    "enable security": False,
    "username": "admin",
    "password": "12345",
    "enable hdhr": False,
    "hdhr name": "STB-Proxy",
    "hdhr id": str(uuid.uuid4().hex),
    "hdhr tuners": 1,
}

default_mac = {
    "type": "mac",
    "enabled": True,
    "name": "",
    "url": "",
    "macs": {},
    "epg time offset": 0,
    "try all macs": False,
    "enabled channels": [],
    "custom channel names": {},
    "custom channel numbers": {},
    "custom groups": {},
    "custom epg ids": {},
    "fallback channels": {},
}

default_macs_dict = {
    "mac": None,
    "proxy": "",
    "max streams": 1,
    "expiry": None,
    "playtime": 0,
    "errors": 0,
    "requests": 0,
}

# endregion


# region core functions
def convert_configs():
    config_file = os.path.join(config_dir, "config.json")
    if os.path.exists(config_file):
        with open(config_file) as config:
            data = json.load(config)
            with open(settings_file, "w") as settings:
                json.dump(data["settings"], settings, indent=4)
            with open(sources_file, "w") as sources:
                for i in data["portals"]:
                    data["portals"][i]["type"] = "mac"
                json.dump(data["portals"], sources, indent=4)
        os.remove(os.path.join(config_dir, "config.json"))


def load_settings():
    try:
        with open(settings_file) as f:
            data = json.load(f)
    except:
        logger.warning("No settings file found... Creating a new one")
        data = {}

    data_out = {}

    for setting, default in default_settings.items():
        value = data.get(setting)
        if not value or type(default) != type(value):
            value = default
        data_out[setting] = value

    with open(settings_file, "w") as f:
        json.dump(data_out, f, indent=4)

    return data_out


def load_sources():
    try:
        with open(sources_file) as f:
            data = json.load(f)
    except:
        logger.warning("No sources file found... Creating a new one")
        data = {}

    data_out = {}

    for s in data:
        data_out[s] = {}

        if data[s]["type"] == "mac":
            defaults = default_mac
        elif data[s]["type"] == "xtream":
            pass
        elif data[s]["type"] == "m3u":
            pass
        else:
            continue

        for setting, default in defaults.items():
            value = data[s].get(setting)
            if not value or type(default) != type(value):
                value = default
            data_out[s][setting] = value

    with open(sources_file, "w") as f:
        json.dump(data_out, f, indent=4)

    return data_out


def parse_expiery_string(date_string):
    try:
        date_obj = parse(date_string)
        timestamp = date_obj.timestamp()
        return int(timestamp)
    except:
        logger.info("Unable to parse expiration date ({})".format(date_string))


def save_settings():
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=4)


def save_sources():
    with open(sources_file, "w") as f:
        json.dump(sources, f, indent=4)


def authorise(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if (
            settings["enable security"] == False
            or auth
            and auth.username == settings["username"]
            and auth.password == settings["password"]
        ):
            return f(*args, **kwargs)

        return make_response(
            "Could not verify your login!",
            401,
            {"WWW-Authenticate": 'Basic realm="Login Required"'},
        )

    return decorated


def test_stream(link, proxy):
    ffprobecmd = [
        "ffprobe",
        "-timeout",
        str(settings["stream timeout"] * int(1000000)),
        "-i",
        link,
    ]

    if proxy:
        ffprobecmd.insert(1, "-http_proxy")
        ffprobecmd.insert(2, proxy)

    with subprocess.Popen(
        ffprobecmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as ffprobe_sb:
        ffprobe_sb.communicate()
        if ffprobe_sb.returncode == 0:
            return True
        else:
            return False


def stream_data(stream):
    def build_ffmpeg_command(stream):
        if stream["web"]:
            ffmpegcmd = [
                "ffmpeg",
                "-loglevel",
                "panic",
                "-hide_banner",
                "-i",
                stream["link"],
                "-vcodec",
                "copy",
                "-f",
                "mp4",
                "-movflags",
                "frag_keyframe+empty_moov",
                "pipe:",
            ]
            if stream["proxy"]:
                ffmpegcmd.insert(1, "-http_proxy")
                ffmpegcmd.insert(2, stream["proxy"])
        else:
            ffmpegcmd = settings["ffmpeg command"]
            ffmpegcmd = ffmpegcmd.replace("<url>", stream["link"])
            ffmpegcmd = ffmpegcmd.replace(
                "<timeout>",
                str(settings["stream timeout"] * int(1000000)),
            )
            if stream["proxy"]:
                ffmpegcmd = ffmpegcmd.replace("<proxy>", stream["proxy"])
            else:
                ffmpegcmd = ffmpegcmd.replace("-http_proxy <proxy>", "")
            " ".join(ffmpegcmd.split())  # cleans up multiple whitespaces
            ffmpegcmd = ffmpegcmd.split()
        return ffmpegcmd

    def occupy():
        occupied.setdefault(stream["source id"], [])
        occupied.get(stream["source id"], []).append(stream)
        logger.info(
            "Occupied Source({}):Account({})".format(
                stream["source id"], stream["account"]
            )
        )

    def unoccupy():
        occupied.get(stream["source id"], []).remove(stream)
        logger.info(
            "Unoccupied Source({}):Account({})".format(
                stream["source id"], stream["account"]
            )
        )

    def calculate_stream_duration():
        streamDuration = datetime.now(timezone.utc).timestamp() - startTime
        return streamDuration

    def stream_ffmpeg():
        nonlocal stream_canceled

        def read_stderr(ffmpeg_sp, last_stderr):
            while ffmpeg_sp.poll() is None:
                try:
                    line = ffmpeg_sp.stderr.readline()
                except Exception as e:
                    break
                if not line:
                    break
                # Decode new line and keep latest 10 lines
                stderr_text = line.decode("utf-8").strip()
                logger.debug("FFMPEG stderr: " + stderr_text)
                last_stderr.append(stderr_text)
                if len(last_stderr) > 10:
                    last_stderr.pop(0)

        last_stderr = []  # list to save the last stderr output
        try:
            with subprocess.Popen(
                ffmpegcmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as ffmpeg_sp:
                # Start reading stderr of ffmpeg in seperate thread
                stderr_thread = threading.Thread(
                    target=read_stderr, args=(ffmpeg_sp, last_stderr)
                )
                stderr_thread.start()

                while True:
                    # read ffmpeg stdout buffer
                    chunk = ffmpeg_sp.stdout.read(1024)

                    if len(chunk) == 0:
                        logger.debug("No stream data from ffmpeg detected.")
                        if ffmpeg_sp.poll() is not None:
                            logger.debug(
                                "Ffmpeg process closed unexpectedly with return / error code ({}).".format(
                                    str(ffmpeg_sp.poll())
                                )
                            )
                            # Check errors
                            error_text = "\n".join(last_stderr)
                            if "I/O error" in error_text:
                                # stream ended / closed by server
                                stream_canceled = True
                                logger.info(
                                    "Stream to client ({}) from Portal ({}) was closed.".format(
                                        stream["client"], stream["source name"]
                                    )
                                )
                            elif "Operation timed out" in error_text:
                                logger.info(
                                    "Stream to client ({}) from Portal ({}) timed out.".format(
                                        stream["client"], stream["source name"]
                                    )
                                )
                            else:
                                logger.debug(
                                    "Stream with ffmpeg process stopped with unknown error:\n{}".format(
                                        error_text
                                    )
                                )
                            # stop stream
                            break
                    yield chunk
        except Exception as e:
            pass
        finally:
            if stderr_thread.is_alive():
                stderr_thread.join(timeout=0.2)  # Wait for the end of the stderr thread
            ffmpeg_sp.kill()

    def stream_direct():
        nonlocal stream_canceled
        try:
            # Send a request to the source video stream URL
            reqTimeout = int(settings["stream timeout"])  # Request timeout in seconds
            response = requests.get(stream["link"], stream=True, timeout=reqTimeout)

            # Check if the request was successful
            if response.status_code == 200:
                # Start stream
                for chunk in response.iter_content(chunk_size=1024):
                    if len(chunk) == 0:
                        logger.info("No stream data.")
                        return
                    yield chunk
            else:
                logger.error(
                    "Couldn't connect to stream URL ({}).\n Request stopped with status code ({}).".format(
                        stream["link"], response.status_code
                    )
                )
        except requests.exceptions.Timeout:
            logger.error("Stream request to URL ({}) timed out.".format(stream["link"]))
            return
        except requests.exceptions.RequestException as e:
            logger.error(
                "Stream request to URL ({}) ended with error:\n{}".format(
                    stream["link"], e
                )
            )
            return
        except Exception as e:
            logger.error(
                "Stream from direct buffer raised an unknown error:\n{}".format(e)
            )
            return

        # stream ended / closed by server
        stream_canceled = True
        logger.info(
            "Stream to client ({}) from Portal ({}) was closed.".format(
                stream["client"], stream["source name"]
            )
        )

    # Start new stream
    startTime = datetime.now(timezone.utc).timestamp()
    stream_canceled = False
    try:
        occupy()
        if stream["web"] or settings["stream method"] == "ffmpeg":
            ffmpegcmd = build_ffmpeg_command(stream)
            logger.debug("Start Stream by ffmpeg.")
            for chunk in stream_ffmpeg():
                yield chunk
        else:
            logger.debug("Start Stream by direct buffer.")
            for chunk in stream_direct():
                yield chunk
    except GeneratorExit:
        logger.info("Stream closed by client.")
        pass
    except Exception as e:
        pass
    finally:
        unoccupy()
        stream_duration = round(calculate_stream_duration(), 1)
        type = stream["type"]
        if type == "mac":
            sources[stream["source id"]]["macs"][stream["account"]][
                "playtime"
            ] += stream_duration
            sources[stream["source id"]]["macs"][stream["account"]][
                "errors"
            ] += stream_canceled
        elif type == "xtream":
            pass
        elif type == "m3u":
            pass

        if stream_canceled and stream_duration <= 60:
            logger.info(
                "A forced disconnection by the server after a short stream time indicates that mac address might be over-used."
            )
        save_sources()


def float_to_timestamp(decimal_hours):
    hours = int(decimal_hours)
    minutes = int((decimal_hours - hours) * 60)

    sign = "+" if hours >= 0 else "-"
    hours = abs(hours)

    return f"{sign}{hours:02d}{minutes:02d}"


# endregion


# region mac functions
def mac_get_url(url_in, proxy=None):
    def parse_response(endpoint, data):
        java = data.text.replace(" ", "").replace("'", "").replace("+", "")
        pattern = re.search(r"varpattern.*\/(\(http.*)\/;", java).group(1)
        result = re.search(pattern, endpoint)
        protocolIndex = re.search(r"this\.portal_protocol.*(\d).*;", java).group(1)
        ipIndex = re.search(r"this\.portal_ip.*(\d).*;", java).group(1)
        pathIndex = re.search(r"this\.portal_path.*(\d).*;", java).group(1)
        protocol = result.group(int(protocolIndex))
        ip = result.group(int(ipIndex))
        path = result.group(int(pathIndex))
        portalPatern = re.search(r"this\.ajax_loader=(.*\.php);", java).group(1)
        portal = (
            portalPatern.replace("this.portal_protocol", protocol)
            .replace("this.portal_ip", ip)
            .replace("this.portal_path", path)
        )
        return portal

    url_root = urlparse(url_in).scheme + "://" + urlparse(url_in).netloc

    endpoints = [
        "/c/xpcom.common.js",
        "/client/xpcom.common.js",
        "/c_/xpcom.common.js",
        "/stalker_portal/c/xpcom.common.js",
        "/stalker_portal/c_/xpcom.common.js",
    ]

    proxies = {"http": proxy, "https": proxy}
    headers = {"User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)"}

    try:
        for e in endpoints:
            try:
                response = requests.get(url_root + e, headers=headers, proxies=proxies)
            except:
                response = None
            if response:
                return parse_response(url_root + e, response)
    except:
        pass

    return url_in


def mac_get_token(url, mac, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {"User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)"}
    try:
        response = requests.get(
            url + "?type=stb&action=handshake&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies,
        )
        token = response.json()["js"]["token"]
        if token:
            return token
    except:
        pass


def mac_get_profile(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?type=stb&action=get_profile&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies,
        )
        profile = response.json()["js"]
        if profile:
            return profile
    except:
        pass


def mac_get_expires(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?type=account_info&action=get_main_info&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies,
        )
        expires = response.json()["js"]["phone"]
        if expires:
            return expires
    except:
        pass


def mac_get_all_channels(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url
            + "?type=itv&action=get_all_channels&force_ch_link_check=&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies,
        )
        channels = response.json()["js"]["data"]
        if channels:
            return channels
    except:
        pass


def mac_get_groups(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?action=get_genres&type=itv&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies,
        )
        genreData = response.json()["js"]
        if genreData:
            return genreData
    except:
        pass


def mac_get_group_names(url, mac, token, proxy=None):
    try:
        genreData = mac_get_groups(url, mac, token, proxy)
        genres = {}
        for i in genreData:
            gid = i["id"]
            name = i["title"]
            genres[gid] = name
        if genres:
            return genres
    except:
        pass


def mac_get_link(url, mac, token, cmd, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url
            + "?type=itv&action=create_link&cmd="
            + cmd
            + "&series=0&forced_storage=false&disable_ad=false&download=false&force_ch_link_check=false&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies,
        )
        data = response.json()
        link = data["js"]["cmd"].split()[-1]
        if link:
            return link
    except:
        pass


def mac_get_epg(url, mac, token, period, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url
            + "?type=itv&action=get_epg_info&period="
            + str(period)
            + "&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies,
        )
        data = response.json()["js"]["data"]
        if data:
            return data
    except:
        pass


def mac_save(id, form):
    source = sources.get(id, copy.deepcopy(default_mac))
    enabled = bool(form.get("enabled", False))
    name = form["name"]
    url = form["url"]
    macs = ast.literal_eval(form["macs"])
    epgTimeOffset = float(request.form["epg time offset"])
    retest = bool(form.get("retest", False))

    for m in dict(macs):
        if retest or macs[m]["expiry"] == "Untested":
            mac = macs[m]["mac"]
            proxy = macs[m]["proxy"]
            token = stb.getToken(url, mac, proxy)
            if token:
                stb.getProfile(url, mac, token, proxy)
                expiry = stb.getExpires(url, mac, token, proxy)
                if expiry:
                    macs[m]["expiry"] = parse_expiery_string(expiry)
                    logger.info(
                        "Successfully tested MAC({}) for Portal({})".format(mac, name)
                    )
                    flash(
                        "Successfully tested MAC({}) for Portal({})".format(mac, name),
                        "success",
                    )
                    continue

            del macs[m]
            logger.error("Error testing MAC({}) for Portal({})".format(mac, name))
            flash("Error testing MAC({}) for Portal({})".format(mac, name), "danger")

    source["enabled"] = enabled
    source["name"] = name
    source["url"] = url
    source["epg time offset"] = epgTimeOffset
    source["macs"] = macs

    sources[id] = source
    save_sources()
    logger.info("Source({}) saved!".format(name))
    flash("Source({}) saved!".format(name), "success")


def mac_get_playlist_table_data(id, source):
    data = []
    url = source["url"]
    macs = source["macs"]
    enabled_channels = source["enabled channels"]
    custom_channel_names = source["custom channel names"]
    custom_groups = source["custom groups"]
    custom_channel_numbers = source["custom channel numbers"]
    custom_epg_ids = source["custom epg ids"]
    fallback_channels = source["fallback channels"]

    all_channels = None
    groups = None

    for m in macs:
        mac = macs[m]["mac"]
        proxy = macs[m]["proxy"]
        try:
            token = mac_get_token(url, mac, proxy)
            mac_get_profile(url, mac, token, proxy)
            all_channels = mac_get_all_channels(url, mac, token, proxy)
            groups = mac_get_group_names(url, mac, token, proxy)
            break
        except:
            pass

    if all_channels and groups:
        for channel in all_channels:
            channel_id = str(channel["id"])

            data.append(
                {
                    "enabled": True if channel_id in enabled_channels else False,
                    "channel name": str(channel["name"]),
                    "custom channel name": str(
                        custom_channel_names.get(channel_id, "")
                    ),
                    "channel number": str(channel["number"]),
                    "custom channel number": str(
                        custom_channel_numbers.get(channel_id, "")
                    ),
                    "group": str(groups.get(str(channel["tv_genre_id"]))),
                    "custom group": custom_groups.get(channel_id, ""),
                    "channel id": channel_id,
                    "epg id": str(channel["xmltv_id"]),
                    "custom epg id": custom_epg_ids.get(channel_id, ""),
                    "fallback": fallback_channels.get(channel_id, ""),
                    "link": "http://"
                    + host
                    + "/play/"
                    + id
                    + "/"
                    + channel_id
                    + "?web=true",
                }
            )

    data = {"data": data}
    return data


def mac_build_stream(source_id, channel_id, ip, web):
    def is_mac_free(max_streams):
        # When changing channels, it takes a while until the stream is finished and the Mac address gets released
        checkInterval = 0.1
        maxIterations = max(math.ceil(5 / checkInterval), 1)
        for _ in range(maxIterations):
            count = 0
            for i in occupied.get(source_id, []):
                if i["mac"] == mac:
                    count = count + 1
            if count < max_streams:
                return True
            else:
                time.sleep(0.1)
        return False

    source = sources[source_id]
    url = source["url"]
    macs = source["macs"]
    source_name = source["name"]
    free_mac = False

    for m in macs:
        channels = None
        cmd = None
        link = None

        mac = macs[m]["mac"]
        proxy = macs[m]["proxy"]
        max_streams = macs[m]["max streams"]

        if max_streams == 0 or is_mac_free(max_streams):
            logger.info(
                "Trying MAC({}) for Source({}) Channel({})".format(
                    mac, source_id, channel_id
                )
            )
            macs[m]["requests"] += 1
            save_sources()
            free_mac = True
            token = mac_get_token(url, mac, proxy)
            if token:
                mac_get_profile(url, mac, token, proxy)
                channels = mac_get_all_channels(url, mac, token, proxy)
        else:
            logger.info("Maximum streams for MAC({}) in use.".format(mac))

        if channels:
            for c in channels:
                if str(c["id"]) == channel_id:
                    channel_name = source.get("custom channel names", {}).get(
                        channel_id
                    )
                    if not channel_name:
                        channel_name = c["name"]

                    cmd = c["cmd"]
                    break

        if cmd:
            if "http://localhost/" in cmd:
                link = mac_get_link(url, mac, token, cmd, proxy)
            else:
                link = cmd.split(" ")[1]

        if link:
            if not settings["test streams"] or test_stream(link, proxy):
                stream = {
                    "type": "mac",
                    "source id": source_id,
                    "source name": source_name,
                    "channel id": channel_id,
                    "channel name": channel_name,
                    "client": ip,
                    "account": m,
                    "start time": datetime.now(timezone.utc).timestamp(),
                    "link": link,
                    "proxy": proxy,
                    "web": web,
                }

                return stream

        logger.info(
            "Unable to connect to Portal({}) using MAC({})".format(source_id, mac)
        )

        if not settings["try all macs"]:
            break

    return None

    # disabled for now
    # Look for fallback
    if not web:
        logger.info(
            "Portal({}):Channel({}) is not working. Looking for fallbacks...".format(
                portalId, channelId
            )
        )

        for portal in portals:
            if portals[portal]["enabled"] == "true":
                fallbackChannels = portals[portal]["fallback channels"]
                if channelName in fallbackChannels.values():
                    url = portals[portal].get("url")
                    macs = list(portals[portal]["macs"].keys())
                    proxy = portals[portal].get("proxy")
                    for mac in macs:
                        channels = None
                        cmd = None
                        link = None
                        if streamsPerMac == 0 or isMacFree():
                            for k, v in fallbackChannels.items():
                                if v == channelName:
                                    try:
                                        token = stb.getToken(url, mac, proxy)
                                        stb.getProfile(url, mac, token, proxy)
                                        channels = stb.getAllChannels(
                                            url, mac, token, proxy
                                        )
                                    except:
                                        logger.info(
                                            "Unable to connect to fallback Portal({}) using MAC({})".format(
                                                portalId, mac
                                            )
                                        )
                                    if channels:
                                        fChannelId = k
                                        for c in channels:
                                            if str(c["id"]) == fChannelId:
                                                cmd = c["cmd"]
                                                break
                                        if cmd:
                                            if "http://localhost/" in cmd:
                                                link = stb.getLink(
                                                    url, mac, token, cmd, proxy
                                                )
                                            else:
                                                link = cmd.split(" ")[1]
                                            if link:
                                                if testStream():
                                                    logger.info(
                                                        "Fallback found for Portal({}):Channel({})".format(
                                                            portalId, channelId
                                                        )
                                                    )
                                                    portal["macs"][mac]["stats"][
                                                        "requests"
                                                    ] += 1
                                                    savePortals(portals)
                                                    if (
                                                        getSettings().get(
                                                            "stream method", "ffmpeg"
                                                        )
                                                        != "redirect"
                                                    ):
                                                        return Response(
                                                            stream_with_context(
                                                                streamData()
                                                            ),
                                                            mimetype="application/octet-stream",
                                                        )
                                                    else:
                                                        logger.info("Redirect sent")
                                                        return redirect(link)

    if freeMac:
        logger.info(
            "No working streams found for Portal({}):Channel({})".format(
                portalId, channelId
            )
        )
    else:
        logger.info(
            "No free MAC for Portal({}):Channel({})".format(portalId, channelId)
        )


# endregion


# region routes
@app.route("/", methods=["GET"])
@authorise
def home():
    return redirect("/sources")


@app.route("/sources", methods=["GET"])
@authorise
def sources_page():
    return render_template("sources.html", sources=sources)


@app.route("/sources/add", methods=["POST"])
@authorise
def add_source():
    id = uuid.uuid4().hex
    type = request.form["type"]

    if type == "mac":
        return render_template("mac.html", source=default_mac, id=id, type="mac")
    elif type == "xtream":
        pass
    elif type == "m3u":
        pass


@app.route("/source/edit", methods=["POST"])
@authorise
def source_edit():
    id = request.form["id"]
    source = sources[id]
    type = source["type"]

    if type == "mac":
        return render_template("mac.html", source=source, id=id, type="mac")
    elif type == "xtream":
        pass
    elif type == "m3u":
        pass


@app.route("/source/save", methods=["POST"])
@authorise
def source_save():
    id = request.form["id"]
    type = request.form["type"]

    if type == "mac":
        mac_save(id, request.form)
    elif type == "xtream":
        pass
    elif type == "m3u":
        pass

    return render_template("sources.html", sources=sources)


@app.route("/source/delete", methods=["POST"])
@authorise
def portalRemove():
    id = request.form["id"]
    portals = getPortals()
    name = portals[id]["name"]
    del portals[id]
    savePortals(portals)
    logger.info("Portal ({}) removed!".format(name))
    flash("Portal ({}) removed!".format(name), "success")
    return redirect("/portals", code=302)


@app.route("/playlist/edit", methods=["POST"])
@authorise
def playlist_edit():
    id = request.form["id"]
    return render_template("playlist_editor.html", id=id)


@app.route("/playlist_table_data", methods=["GET"])
@authorise
def playlist_table_data():
    id = request.args["id"]
    source = sources[id]
    type = source["type"]

    if type == "mac":
        data = mac_get_playlist_table_data(id, source)

    return flask.jsonify(data)


@app.route("/playlist/save", methods=["POST"])
@authorise
def editorSave():
    id = request.form["id"]
    source = sources[id]
    name = source["name"]
    enable_edits = json.loads(request.form["enable edits"])
    number_edits = json.loads(request.form["number edits"])
    name_edits = json.loads(request.form["name edits"])
    group_edits = json.loads(request.form["group edits"])
    epg_edits = json.loads(request.form["epg edits"])
    fallback_edits = json.loads(request.form["fallback edits"])

    for edit in enable_edits:
        channel_id = edit["channel id"]
        enabled = edit["enabled"]
        if enabled:
            source["enabled channels"].append(channel_id)
        else:
            source["enabled channels"] = list(
                filter((channel_id).__ne__, source["enabled channels"])
            )

    for edit in number_edits:
        channel_id = edit["channel id"]
        custom_number = edit["custom number"]
        if custom_number:
            source["custom channel numbers"].update({channel_id: custom_number})
        else:
            source["custom channel numbers"].pop(channel_id)

    for edit in name_edits:
        channel_id = edit["channel id"]
        custom_name = edit["custom name"]
        if custom_name:
            source["custom channel names"].update({channel_id: custom_name})
        else:
            source["custom channel names"].pop(channel_id)

    for edit in group_edits:
        channel_id = edit["channel id"]
        custom_group = edit["custom group"]
        if custom_group:
            source["custom groups"].update({channel_id: custom_group})
        else:
            source["custom groups"].pop(channel_id)

    for edit in epg_edits:
        channel_id = edit["channel id"]
        custom_epg_id = edit["custom epg id"]
        if custom_epg_id:
            source["custom epg ids"].update({channel_id: custom_epg_id})
        else:
            source["custom epg ids"].pop(channel_id)

    for edit in fallback_edits:
        channel_id = edit["channel id"]
        fallback = edit["fallback"]
        if fallback:
            source["fallback channels"].update({channel_id: fallback})
        else:
            source["fallback channels"].pop(channel_id)

    sources[id] = source
    save_sources()
    logger.info("Playlist({}) saved!".format(name))
    flash("Playlist({}) saved!".format(name), "success")

    return redirect("/sources")


@app.route("/playlist/reset", methods=["POST"])
@authorise
def editorReset():
    id = request.form.get("id")
    source = sources[id]

    source["enabled channels"] = []
    source["custom channel numbers"] = {}
    source["custom channel names"] = {}
    source["custom groups"] = {}
    source["custom epg ids"] = {}
    source["fallback channels"] = {}

    sources[id] = source
    save_sources()

    logger.info("Playlist reset!")
    flash("Playlist reset!", "success")

    return redirect("/sources", code=302)


@app.route("/settings", methods=["GET"])
@authorise
def settings():
    return render_template(
        "settings.html", settings=settings, default_settings=default_settings
    )


@app.route("/settings/save", methods=["POST"])
@authorise
def save():
    global settings
    settings = {
        "stream method": request.form.get("stream method"),
        "stream timeout": int(request.form.get("stream timeout")),
        "stream chunk size": int(request.form.get("stream chunk size")),
        "ffmpeg command": request.form.get("ffmpeg command"),
        "test streams": True if request.form.get("test streams") else False,
        "use channel groups": True if request.form.get("use channel groups") else False,
        "use channel numbers": True
        if request.form.get("use channel numbers")
        else False,
        "sort playlists by channel group": True
        if request.form.get("sort playlists by channel group")
        else False,
        "sort playlists by channel number": True
        if request.form.get("sort playlists by channel number")
        else False,
        "sort playlists by channel name": True
        if request.form.get("sort playlists by channel name")
        else False,
        "enable security": True if request.form.get("enable security") else False,
        "username": request.form.get("username"),
        "password": request.form.get("password"),
        "enable hdhr": True if request.form.get("enable hdhr") else False,
        "hdhr name": request.form.get("hdhr name"),
        "hdhr id": request.form.get("hdhr id"),
        "hdhr tuners": int(request.form.get("hdhr tuners")),
    }

    save_settings()
    logger.info("Settings saved!")
    flash("Settings saved!", "success")

    return redirect("/settings")


@app.route("/playlist", methods=["GET"])
@authorise
def playlist():
    return


@app.route("/xmltv", methods=["GET"])
@authorise
def xmltv():
    return


@app.route("/play/<source_id>/<channel_id>", methods=["GET"])
def stream_request(source_id, channel_id):
    web = request.args.get("web")
    ip = request.remote_addr

    logger.info(
        "IP({}) requested Source({}):Channel({})".format(ip, source_id, channel_id)
    )

    type = sources[source_id]["type"]

    if type == "mac":
        stream = mac_build_stream(source_id, channel_id, ip, web)
    elif type == "xtream":
        pass
    elif type == "m3u":
        pass

    if stream:
        return Response(
            stream_with_context(stream_data(stream)),
            mimetype="application/octet-stream",
        )
    else:
        return make_response("No streams available", 503)


@app.route("/dashboard")
@authorise
def dashboard():
    return render_template("dashboard.html")


@app.route("/streaming")
@authorise
def streaming():
    return flask.jsonify(occupied)


@app.route("/log")
@authorise
def log():
    with open("STB-Proxy.log") as f:
        log = f.read()
    return log


# endregion


# region hdhr
def hdhr(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        settings = getSettings()
        security = settings["enable security"]
        username = settings["username"]
        password = settings["password"]
        hdhrenabled = settings["enable hdhr"]
        if (
            security == "false"
            or auth
            and auth.username == username
            and auth.password == password
        ):
            if hdhrenabled:
                return f(*args, **kwargs)
        return make_response("Error", 404)

    return decorated


@app.route("/discover.json", methods=["GET"])
@hdhr
def discover():
    settings = getSettings()
    name = settings["hdhr name"]
    id = settings["hdhr id"]
    tuners = settings["hdhr tuners"]
    data = {
        "BaseURL": host,
        "DeviceAuth": name,
        "DeviceID": id,
        "FirmwareName": "STB-Proxy",
        "FirmwareVersion": "1337",
        "FriendlyName": name,
        "LineupURL": host + "/lineup.json",
        "Manufacturer": "Chris",
        "ModelNumber": "1337",
        "TunerCount": int(tuners),
    }
    return flask.jsonify(data)


@app.route("/lineup_status.json", methods=["GET"])
@hdhr
def status():
    data = {
        "ScanInProgress": 0,
        "ScanPossible": 0,
        "Source": "Antenna",
        "SourceList": ["Antenna"],
    }
    return flask.jsonify(data)


@app.route("/lineup.json", methods=["GET"])
@app.route("/lineup.post", methods=["POST"])
@hdhr
def lineup():
    lineup = []
    portals = getPortals()
    for portal in portals:
        if portals[portal]["enabled"] == "true":
            enabledChannels = portals[portal].get("enabled channels", [])
            if len(enabledChannels) != 0:
                name = portals[portal]["name"]
                url = portals[portal]["url"]
                macs = list(portals[portal]["macs"].keys())
                proxy = portals[portal]["proxy"]
                customChannelNames = portals[portal].get("custom channel names", {})
                customChannelNumbers = portals[portal].get("custom channel numbers", {})

                for mac in macs:
                    try:
                        token = stb.getToken(url, mac, proxy)
                        stb.getProfile(url, mac, token, proxy)
                        allChannels = stb.getAllChannels(url, mac, token, proxy)
                        break
                    except:
                        allChannels = None

                if allChannels:
                    for channel in allChannels:
                        channelId = str(channel.get("id"))
                        if channelId in enabledChannels:
                            channelName = customChannelNames.get(channelId)
                            if channelName == None:
                                channelName = str(channel.get("name"))
                            channelNumber = customChannelNumbers.get(channelId)
                            if channelNumber == None:
                                channelNumber = str(channel.get("number"))

                            lineup.append(
                                {
                                    "GuideNumber": channelNumber,
                                    "GuideName": channelName,
                                    "URL": "http://"
                                    + host
                                    + "/play/"
                                    + portal
                                    + "/"
                                    + channelId,
                                }
                            )
                else:
                    logger.error("Error making lineup for {}, skipping".format(name))

    return flask.jsonify(lineup)


# endregion

if __name__ == "__main__":
    convert_configs()
    settings = load_settings()
    sources = load_sources()
    if debug or (
        "TERM_PROGRAM" in os.environ.keys() and os.environ["TERM_PROGRAM"] == "vscode"
    ):
        logger.info(
            "ATTENTION: Server started in debug mode. Don't use on productive systems!"
        )
        app.run(host="0.0.0.0", port=8001, debug=True)
    else:
        waitress.serve(app, port=8001, _quiet=True, threads=24)
