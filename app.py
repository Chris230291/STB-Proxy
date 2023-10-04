import flask
import threading
import stb
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
    stream_with_context
)
import math
import time
import requests
from datetime import datetime, timezone
from functools import wraps
import secrets
import waitress

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
    configFile = os.getenv("CONFIG")
else:
    configFile = os.path.join(basePath, "config.json")
    
if os.getenv("DEBUG_MODE"):
    debug_str = os.getenv("DEBUG_MODE")
    debug = debug_str.lower() == 'true' or debug_str == '1'
else:
    debug = False

# Set log level
if debug:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

occupied = {}
config = {}

d_ffmpegcmd = "ffmpeg -re -http_proxy <proxy> -timeout <timeout> -i <url> -map 0 -codec copy -f mpegts pipe:"

defaultSettings = {
    "stream method": "ffmpeg",
    "ffmpeg command": "ffmpeg -re -http_proxy <proxy> -timeout <timeout> -i <url> -map 0 -codec copy -f mpegts pipe:",
    "stream timeout": "5",
    "test streams": "true",
    "try all macs": "false",
    "use channel genres": "true",
    "use channel numbers": "true",
    "sort playlist by channel genre": "false",
    "sort playlist by channel number": "false",
    "sort playlist by channel name": "false",
    "enable security": "false",
    "username": "admin",
    "password": "12345",
    "enable hdhr": "false",
    "hdhr name": "STB-Proxy",
    "hdhr id": str(uuid.uuid4().hex),
    "hdhr tuners": "1",
}

defaultPortal = {
    "enabled": "true",
    "name": "",
    "url": "",
    "macs": {},
    "streams per mac": "1",
    "epgTimeOffset": "0",
    "proxy": "",
    "enabled channels": [],
    "custom channel names": {},
    "custom channel numbers": {},
    "custom genres": {},
    "custom epg ids": {},
    "fallback channels": {},
}


maxWaitTimeFree = 5  # Time to wait for freed mac
bufferSize = 1024  # Buffer size in bytes (1024=1kB)

def loadConfig():
    try:
        with open(configFile) as f:
            data = json.load(f)
    except:
        logger.warning("No existing config found. Creating a new one")
        data = {}

    data.setdefault("portals", {})
    data.setdefault("settings", {})

    settings = data["settings"]
    settingsOut = {}

    for setting, default in defaultSettings.items():
        value = settings.get(setting)
        if not value or type(default) != type(value):
            value = default
        settingsOut[setting] = value

    data["settings"] = settingsOut

    portals = data["portals"]
    portalsOut = {}

    for portal in portals:
        portalsOut[portal] = {}
        for setting, default in defaultPortal.items():
            value = portals[portal].get(setting)
            if not value or type(default) != type(value):
                value = default
            portalsOut[portal][setting] = value

    data["portals"] = portalsOut

    with open(configFile, "w") as f:
        json.dump(data, f, indent=4)

    return data


def getPortals():
    return config["portals"]


def savePortals(portals):
    with open(configFile, "w") as f:
        config["portals"] = portals
        json.dump(config, f, indent=4)


def getSettings():
    return config["settings"]


def saveSettings(settings):
    with open(configFile, "w") as f:
        config["settings"] = settings
        json.dump(config, f, indent=4)


def authorise(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        settings = getSettings()
        security = settings["enable security"]
        username = settings["username"]
        password = settings["password"]
        if (
            security == "false"
            or auth
            and auth.username == username
            and auth.password == password
        ):
            return f(*args, **kwargs)

        return make_response(
            "Could not verify your login!",
            401,
            {"WWW-Authenticate": 'Basic realm="Login Required"'},
        )

    return decorated


def moveMac(portalId, mac):
    portals = getPortals()
    logger.info("Moving MAC({}) for Portal({})".format(mac, portals[portalId]["name"]))
    macs = portals[portalId]["macs"]
    x = macs[mac]
    del macs[mac]
    macs[mac] = x
    portals[portalId]["macs"] = macs
    savePortals(portals)


@app.route("/", methods=["GET"])
@authorise
def home():
    return redirect("/portals", code=302)


@app.route("/portals", methods=["GET"])
@authorise
def portals():
    return render_template("portals.html", portals=getPortals())


@app.route("/portal/add", methods=["POST"])
@authorise
def portalsAdd():
    id = uuid.uuid4().hex
    enabled = "true"
    name = request.form["name"]
    url = request.form["url"]
    macs = list(set(request.form["macs"].split(",")))
    streamsPerMac = request.form["streams per mac"]
    epgTimeOffset = request.form["epg time offset"]
    proxy = request.form["proxy"]

    if not url.endswith(".php"):
        url = stb.getUrl(url, proxy)
        if not url:
            logger.error("Error getting URL for Portal({})".format(name))
            flash("Error getting URL for Portal({})".format(name), "danger")
            return redirect("/portals", code=302)

    macsd = {}

    for mac in macs:
        token = stb.getToken(url, mac, proxy)
        if token:
            stb.getProfile(url, mac, token, proxy)
            expiry = stb.getExpires(url, mac, token, proxy)
            if expiry:
                macsd[mac] = expiry
                logger.info(
                    "Successfully tested MAC({}) for Portal({})".format(mac, name)
                )
                flash(
                    "Successfully tested MAC({}) for Portal({})".format(mac, name),
                    "success",
                )
                continue

        logger.error("Error testing MAC({}) for Portal({})".format(mac, name))
        flash("Error testing MAC({}) for Portal({})".format(mac, name), "danger")

    if len(macsd) > 0:
        portal = {
            "enabled": enabled,
            "name": name,
            "url": url,
            "macs": macsd,
            "streams per mac": streamsPerMac,
            "epgTimeOffset": epgTimeOffset,
            "proxy": proxy,
        }

        for setting, default in defaultPortal.items():
            if not portal.get(setting):
                portal[setting] = default

        portals = getPortals()
        portals[id] = portal
        savePortals(portals)
        logger.info("Portal({}) added!".format(portal["name"]))

    else:
        logger.error(
            "None of the MACs tested OK for Portal({}). Adding not successfull".format(
                name
            )
        )

    return redirect("/portals", code=302)


@app.route("/portal/update", methods=["POST"])
@authorise
def portalUpdate():
    id = request.form["id"]
    enabled = request.form.get("enabled", "false")
    name = request.form["name"]
    url = request.form["url"]
    newmacs = list(set(request.form["macs"].split(",")))
    streamsPerMac = request.form["streams per mac"]
    epgTimeOffset = request.form["epg time offset"]
    proxy = request.form["proxy"]
    retest = request.form.get("retest", None)

    if not url.endswith(".php"):
        url = stb.getUrl(url, proxy)
        if not url:
            logger.error("Error getting URL for Portal({})".format(name))
            flash("Error getting URL for Portal({})".format(name), "danger")
            return redirect("/portals", code=302)

    portals = getPortals()
    oldmacs = portals[id]["macs"]
    macsout = {}
    deadmacs = []

    for mac in newmacs:
        if retest or mac not in oldmacs.keys():
            token = stb.getToken(url, mac, proxy)
            if token:
                stb.getProfile(url, mac, token, proxy)
                expiry = stb.getExpires(url, mac, token, proxy)
                if expiry:
                    macsout[mac] = expiry
                    logger.info(
                        "Successfully tested MAC({}) for Portal({})".format(mac, name)
                    )
                    flash(
                        "Successfully tested MAC({}) for Portal({})".format(mac, name),
                        "success",
                    )
            if mac not in macsout.keys():
                deadmacs.append(mac)

        if mac in oldmacs.keys() and mac not in deadmacs:
            macsout[mac] = oldmacs[mac]
            continue

        logger.error("Error testing MAC({}) for Portal({})".format(mac, name))
        flash("Error testing MAC({}) for Portal({})".format(mac, name), "danger")

    if len(macsout) > 0:
        portals[id]["enabled"] = enabled
        portals[id]["name"] = name
        portals[id]["url"] = url
        portals[id]["macs"] = macsout
        portals[id]["streams per mac"] = streamsPerMac
        portals[id]["epgTimeOffset"] = epgTimeOffset
        portals[id]["proxy"] = proxy
        savePortals(portals)
        logger.info("Portal({}) updated!".format(name))
        flash("Portal({}) updated!".format(name), "success")

    else:
        logger.error(
            "None of the MACs tested OK for Portal({}). Adding not successfull".format(
                name
            )
        )

    return redirect("/portals", code=302)


@app.route("/portal/remove", methods=["POST"])
@authorise
def portalRemove():
    id = request.form["deleteId"]
    portals = getPortals()
    name = portals[id]["name"]
    del portals[id]
    savePortals(portals)
    logger.info("Portal ({}) removed!".format(name))
    flash("Portal ({}) removed!".format(name), "success")
    return redirect("/portals", code=302)


@app.route("/editor", methods=["GET"])
@authorise
def editor():
    return render_template("editor.html")


@app.route("/editor_data", methods=["GET"])
@authorise
def editor_data():
    channels = []
    portals = getPortals()
    for portal in portals:
        if portals[portal]["enabled"] == "true":
            portalName = portals[portal]["name"]
            url = portals[portal]["url"]
            macs = list(portals[portal]["macs"].keys())
            proxy = portals[portal]["proxy"]
            enabledChannels = portals[portal].get("enabled channels", [])
            customChannelNames = portals[portal].get("custom channel names", {})
            customGenres = portals[portal].get("custom genres", {})
            customChannelNumbers = portals[portal].get("custom channel numbers", {})
            customEpgIds = portals[portal].get("custom epg ids", {})
            fallbackChannels = portals[portal].get("fallback channels", {})

            for mac in macs:
                try:
                    token = stb.getToken(url, mac, proxy)
                    stb.getProfile(url, mac, token, proxy)
                    allChannels = stb.getAllChannels(url, mac, token, proxy)
                    genres = stb.getGenreNames(url, mac, token, proxy)
                    break
                except:
                    allChannels = None
                    genres = None

            if allChannels and genres:
                for channel in allChannels:
                    channelId = str(channel["id"])
                    channelName = str(channel["name"])
                    channelNumber = str(channel["number"])
                    genre = str(genres.get(str(channel["tv_genre_id"])))
                    if channelId in enabledChannels:
                        enabled = True
                    else:
                        enabled = False
                    customChannelNumber = customChannelNumbers.get(channelId)
                    if customChannelNumber == None:
                        customChannelNumber = ""
                    customChannelName = customChannelNames.get(channelId)
                    if customChannelName == None:
                        customChannelName = ""
                    customGenre = customGenres.get(channelId)
                    if customGenre == None:
                        customGenre = ""
                    customEpgId = customEpgIds.get(channelId)
                    if customEpgId == None:
                        customEpgId = ""
                    fallbackChannel = fallbackChannels.get(channelId)
                    if fallbackChannel == None:
                        fallbackChannel = ""
                    channels.append(
                        {
                            "portal": portal,
                            "portalName": portalName,
                            "enabled": enabled,
                            "channelNumber": channelNumber,
                            "customChannelNumber": customChannelNumber,
                            "channelName": channelName,
                            "customChannelName": customChannelName,
                            "genre": genre,
                            "customGenre": customGenre,
                            "channelId": channelId,
                            "customEpgId": customEpgId,
                            "fallbackChannel": fallbackChannel,
                            "link": "http://"
                            + host
                            + "/play/"
                            + portal
                            + "/"
                            + channelId
                            + "?web=true",
                        }
                    )
            else:
                logger.error(
                    "Error getting channel data for {}, skipping".format(portalName)
                )
                flash(
                    "Error getting channel data for {}, skipping".format(portalName),
                    "danger",
                )

    data = {"data": channels}

    return flask.jsonify(data)


@app.route("/editor/save", methods=["POST"])
@authorise
def editorSave():
    enabledEdits = json.loads(request.form["enabledEdits"])
    numberEdits = json.loads(request.form["numberEdits"])
    nameEdits = json.loads(request.form["nameEdits"])
    genreEdits = json.loads(request.form["genreEdits"])
    epgEdits = json.loads(request.form["epgEdits"])
    fallbackEdits = json.loads(request.form["fallbackEdits"])
    portals = getPortals()
    for edit in enabledEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        enabled = edit["enabled"]
        if enabled:
            portals[portal].setdefault("enabled channels", [])
            portals[portal]["enabled channels"].append(channelId)
        else:
            portals[portal]["enabled channels"] = list(
                filter((channelId).__ne__, portals[portal]["enabled channels"])
            )

    for edit in numberEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        customNumber = edit["custom number"]
        if customNumber:
            portals[portal].setdefault("custom channel numbers", {})
            portals[portal]["custom channel numbers"].update({channelId: customNumber})
        else:
            portals[portal]["custom channel numbers"].pop(channelId)

    for edit in nameEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        customName = edit["custom name"]
        if customName:
            portals[portal].setdefault("custom channel names", {})
            portals[portal]["custom channel names"].update({channelId: customName})
        else:
            portals[portal]["custom channel names"].pop(channelId)

    for edit in genreEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        customGenre = edit["custom genre"]
        if customGenre:
            portals[portal].setdefault("custom genres", {})
            portals[portal]["custom genres"].update({channelId: customGenre})
        else:
            portals[portal]["custom genres"].pop(channelId)

    for edit in epgEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        customEpgId = edit["custom epg id"]
        if customEpgId:
            portals[portal].setdefault("custom epg ids", {})
            portals[portal]["custom epg ids"].update({channelId: customEpgId})
        else:
            portals[portal]["custom epg ids"].pop(channelId)

    for edit in fallbackEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        channelName = edit["channel name"]
        if channelName:
            portals[portal].setdefault("fallback channels", {})
            portals[portal]["fallback channels"].update({channelId: channelName})
        else:
            portals[portal]["fallback channels"].pop(channelId)

    savePortals(portals)
    logger.info("Playlist config saved!")
    flash("Playlist config saved!", "success")

    return redirect("/editor", code=302)


@app.route("/editor/reset", methods=["POST"])
@authorise
def editorReset():
    portals = getPortals()
    for portal in portals:
        portals[portal]["enabled channels"] = []
        portals[portal]["custom channel numbers"] = {}
        portals[portal]["custom channel names"] = {}
        portals[portal]["custom genres"] = {}
        portals[portal]["custom epg ids"] = {}
        portals[portal]["fallback channels"] = {}

    savePortals(portals)
    logger.info("Playlist reset!")
    flash("Playlist reset!", "success")

    return redirect("/editor", code=302)


@app.route("/settings", methods=["GET"])
@authorise
def settings():
    settings = getSettings()
    return render_template(
        "settings.html", settings=settings, defaultSettings=defaultSettings
    )


@app.route("/settings/save", methods=["POST"])
@authorise
def save():
    settings = {}

    for setting, _ in defaultSettings.items():
        value = request.form.get(setting, "false")
        settings[setting] = value

    saveSettings(settings)
    logger.info("Settings saved!")
    flash("Settings saved!", "success")
    return redirect("/settings", code=302)


@app.route("/playlist", methods=["GET"])
@authorise
def playlist():
    channels = []
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
                customGenres = portals[portal].get("custom genres", {})
                customChannelNumbers = portals[portal].get("custom channel numbers", {})
                customEpgIds = portals[portal].get("custom epg ids", {})

                for mac in macs:
                    try:
                        token = stb.getToken(url, mac, proxy)
                        stb.getProfile(url, mac, token, proxy)
                        allChannels = stb.getAllChannels(url, mac, token, proxy)
                        genres = stb.getGenreNames(url, mac, token, proxy)
                        break
                    except:
                        allChannels = None
                        genres = None

                if allChannels and genres:
                    for channel in allChannels:
                        channelId = str(channel.get("id"))
                        if channelId in enabledChannels:
                            channelName = customChannelNames.get(channelId)
                            if channelName == None:
                                channelName = str(channel.get("name"))
                            genre = customGenres.get(channelId)
                            if genre == None:
                                genreId = str(channel.get("tv_genre_id"))
                                genre = str(genres.get(genreId))
                            channelNumber = customChannelNumbers.get(channelId)
                            if channelNumber == None:
                                channelNumber = str(channel.get("number"))
                            epgId = customEpgIds.get(channelId)
                            if epgId == None:
                                epgId = portal + channelId
                            channels.append(
                                "#EXTINF:-1"
                                + ' tvg-id="'
                                + epgId
                                + (
                                    '" tvg-chno="' + channelNumber
                                    if getSettings().get("use channel numbers", "true")
                                    == "true"
                                    else ""
                                )
                                + (
                                    '" group-title="' + genre
                                    if getSettings().get("use channel genres", "true")
                                    == "true"
                                    else ""
                                )
                                + '",'
                                + channelName
                                + "\n"
                                + "http://"
                                + host
                                + "/play/"
                                + portal
                                + "/"
                                + channelId
                            )
                else:
                    logger.error("Error making playlist for {}, skipping".format(name))

    if getSettings().get("sort playlist by channel name", "true") == "true":
        channels.sort(key=lambda k: k.split(",")[1].split("\n")[0])
    if getSettings().get("use channel numbers", "true") == "true":
        if getSettings().get("sort playlist by channel number", "false") == "true":
            channels.sort(key=lambda k: k.split('tvg-chno="')[1].split('"')[0])
    if getSettings().get("use channel genres", "true") == "true":
        if getSettings().get("sort playlist by channel genre", "false") == "true":
            channels.sort(key=lambda k: k.split('group-title="')[1].split('"')[0])

    playlist = "#EXTM3U \n"
    playlist = playlist + "\n".join(channels)

    return Response(playlist, mimetype="text/plain")


@app.route("/xmltv", methods=["GET"])
@authorise
def xmltv():
    
    def float_to_time_stamp(decimal_hours):
        hours = int(decimal_hours)
        minutes = int((decimal_hours - hours) * 60)
        
        sign = '+' if hours >= 0 else '-'
        hours = abs(hours)
        
        return f"{sign}{hours:02d}{minutes:02d}"
    
    channels = ET.Element("tv")
    programmes = ET.Element("tv")
    portals = getPortals()
    for portal in portals:
        if portals[portal]["enabled"] == "true":
            enabledChannels = portals[portal].get("enabled channels", [])
            if len(enabledChannels) != 0:
                name = portals[portal]["name"]
                url = portals[portal]["url"]
                macs = list(portals[portal]["macs"].keys())
                proxy = portals[portal]["proxy"]
                epgTimeOffset = float(portals[portal]["epgTimeOffset"])
                customChannelNames = portals[portal].get("custom channel names", {})
                customEpgIds = portals[portal].get("custom epg ids", {})

                for mac in macs:
                    try:
                        token = stb.getToken(url, mac, proxy)
                        stb.getProfile(url, mac, token, proxy)
                        allChannels = stb.getAllChannels(url, mac, token, proxy)
                        epg = stb.getEpg(url, mac, token, 24, proxy)
                        break
                    except:
                        allChannels = None
                        epg = None

                if allChannels and epg:
                    for c in allChannels:
                        try:
                            channelId = c.get("id")
                            if str(channelId) in enabledChannels:
                                channelName = customChannelNames.get(str(channelId))
                                if channelName == None:
                                    channelName = str(c.get("name"))
                                epgId = customEpgIds.get(channelId)
                                if epgId == None:
                                    epgId = portal + channelId
                                channelEle = ET.SubElement(
                                    channels, "channel", id=epgId
                                )
                                ET.SubElement(
                                    channelEle, "display-name"
                                ).text = channelName
                                ET.SubElement(channelEle, "icon", src=c.get("logo"))
                                for p in epg.get(channelId):
                                    try:
                                        start = (
                                            datetime.utcfromtimestamp(
                                                p.get("start_timestamp")
                                            ).strftime("%Y%m%d%H%M%S")
                                            + " " + float_to_time_stamp(epgTimeOffset)
                                        )
                                        stop = (
                                            datetime.utcfromtimestamp(
                                                p.get("stop_timestamp")
                                            ).strftime("%Y%m%d%H%M%S")
                                            + " " + float_to_time_stamp(epgTimeOffset)
                                        )
                                        programmeEle = ET.SubElement(
                                            programmes,
                                            "programme",
                                            start=start,
                                            stop=stop,
                                            channel=epgId,
                                        )
                                        ET.SubElement(
                                            programmeEle, "title"
                                        ).text = p.get("name")
                                        ET.SubElement(
                                            programmeEle, "desc"
                                        ).text = p.get("descr")
                                    except:
                                        pass
                        except:
                            pass
                else:
                    logger.error("Error making XMLTV for {}, skipping".format(name))

    xmltv = channels
    for programme in programmes.iter("programme"):
        xmltv.append(programme)

    return Response(
        ET.tostring(xmltv, encoding="unicode", xml_declaration=True),
        mimetype="text/xml",
    )


@app.route("/play/<portalId>/<channelId>", methods=["GET"])
def channel(portalId, channelId):
    def genFfmpegCmd():
        if web:
            ffmpegcmd = [
                "ffmpeg",
                "-loglevel",
                "panic",
                "-hide_banner",
                "-i",
                link,
                "-vcodec",
                "copy",
                "-f",
                "mp4",
                "-movflags",
                "frag_keyframe+empty_moov",
                "pipe:",
            ]
            if proxy:
                ffmpegcmd.insert(1, "-http_proxy")
                ffmpegcmd.insert(2, proxy)
        else:
            ffmpegcmd = str(getSettings()["ffmpeg command"])
            ffmpegcmd = ffmpegcmd.replace("<url>", link)
            ffmpegcmd = ffmpegcmd.replace(
                "<timeout>",
                str(int(getSettings()["stream timeout"]) * int(1000000)),
            )
            if proxy:
                ffmpegcmd = ffmpegcmd.replace("<proxy>", proxy)
            else:
                ffmpegcmd = ffmpegcmd.replace("-http_proxy <proxy>", "")
            " ".join(ffmpegcmd.split())  # cleans up multiple whitespaces
            ffmpegcmd = ffmpegcmd.split()
        return ffmpegcmd

    def streamData():
        
        def occupy():
            occupied.setdefault(portalId, [])
            occupied.get(portalId, []).append(
                {
                    "mac": mac,
                    "channel id": channelId,
                    "channel name": channelName,
                    "client": ip,
                    "portal name": portalName,
                    "start time": startTime,
                }
            )
            logger.info("Occupied Portal({}):MAC({})".format(portalId, mac))

        def unoccupy():
            occupied.get(portalId, []).remove(
                {
                    "mac": mac,
                    "channel id": channelId,
                    "channel name": channelName,
                    "client": ip,
                    "portal name": portalName,
                    "start time": startTime,
                }
            )
            logger.info("Unoccupied Portal({}):MAC({})".format(portalId, mac))

        def calcStreamDuration():
            # calc streaming duration
            streamDuration = datetime.now(timezone.utc).timestamp() - startTime 
            return streamDuration

        def startffmpeg():
            def read_stderr(ffmpeg_sp, last_stderr):
                while ffmpeg_sp.poll() is None:
                    try:
                        line = ffmpeg_sp.stderr.readline()
                    except Exception as e:
                        break
                    if not line:
                        break
                    # Decode new line and keep latest 10 lines
                    stderr_text = line.decode('utf-8').strip()
                    logger.debug("FFMPEG stderr: " + stderr_text)
                    last_stderr.append(stderr_text)
                    if len(last_stderr) > 10: 
                        last_stderr.pop(0) 
                        
            last_stderr = [] # list to save the last stderr output
            try:
                with subprocess.Popen(
                    ffmpegcmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ) as ffmpeg_sp:
                    # Start reading stderr of ffmpeg in seperate thread
                    stderr_thread = threading.Thread(target=read_stderr, args=(ffmpeg_sp, last_stderr))
                    stderr_thread.start()

                    while True:
                        # read ffmpeg stdout buffer
                        chunk = ffmpeg_sp.stdout.read(bufferSize)

                        if len(chunk) == 0:
                            logger.debug("No streaming data from ffmpeg detected.")
                            if ffmpeg_sp.poll() is not None:
                                logger.debug("Ffmpeg process closed unexpectedly with return / error code ({}).".format(str(ffmpeg_sp.poll())))
                                # Check errors
                                error_text = "\n".join(last_stderr)
                                if "I/O error" in error_text:
                                    logger.info("Stream to client ({}) from Portal ({}) was closed.".format(ip, portalName))
                                    # Check mac over-allocation
                                    if calcStreamDuration() < 120:
                                        logger.info("A forced disconnection by the server after a short streaming time indicates that mac address might be over-used.")
                                        moveMac(portalId, mac)
                                elif "Operation timed out" in error_text:
                                    logger.info("Stream to client ({}) from Portal ({}) timed out.".format(ip, portalName))
                                else:
                                    logger.debug("Stream with ffmpeg process stopped with unknown error:\n{}".format(error_text))
                                # stop streaming
                                break
                        yield chunk
            except Exception as e:
                pass
            finally:
                if stderr_thread.is_alive():
                    stderr_thread.join(timeout=0.2)  # Wait for the end of the stderr thread
                ffmpeg_sp.kill()
                
        def startdirectbuffer():
            reqTimeout = int(getSettings()["stream timeout"]) # Request timeout in seconds
            try:
                # Send a request to the source video stream URL
                response = requests.get(link, stream=True, timeout=reqTimeout)
                #response.raise_for_status() # Throws exception in case of HTTP error

                # Check if the request was successful
                if response.status_code == 200:
                    # Start Streaming
                    for chunk in response.iter_content(chunk_size=bufferSize):
                        if len(chunk) == 0:
                            logger.info("No streaming data.")
                            return
                        yield chunk
                else:
                    logger.error("Couldn't connect to stream URL ({}).\n Request stopped with status code ({}).".format(link, response.status_code))
            except requests.exceptions.Timeout:
                logger.error("Stream request to URL ({}) timed out.".format(link))
            except requests.exceptions.RequestException as e:
                logger.error("Stream request to URL ({}) ended with error:\n{}".format(link, e))
            except Exception as e:
                logger.error("Stream from direct buffer raised an unknown error:\n{}".format(e))
                
            # stream ended / closed by server
            logger.info("Stream to client ({}) from Portal ({}) was closed.".format(ip, portalName))
            if calcStreamDuration() < 120:
                logger.info("A forced disconnection by the server after a short streaming time indicates that mac address might be over-used.")
                moveMac(portalId, mac)
            
        # Start new stream
        startTime = datetime.now(timezone.utc).timestamp()
        try:
            occupy()
            if web or getSettings().get("stream method", "ffmpeg") == "ffmpeg":
                # Generate specific ffmpeg command
                ffmpegcmd = genFfmpegCmd()
                
                logger.debug("Start Stream by ffmpeg.")
                for chunk in startffmpeg():
                    yield chunk
            elif getSettings().get("stream method", "buffer") == "buffer":
                logger.debug("Start Stream by direct buffer.")
                for chunk in startdirectbuffer():
                    yield chunk
            else:
                logger.error("Unknown streaming method.")
        except GeneratorExit:
            logger.info('Stream closed by client.')
            pass
        except Exception as e:
            pass
        finally:
            unoccupy()

    def testStream():
        timeout = int(getSettings()["stream timeout"]) * int(1000000)
        ffprobecmd = ["ffprobe", "-timeout", str(timeout), "-i", link]

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

    def isMacFree():
        # When changing channels, it takes a while until the stream is finished and the Mac address gets released    
        checkInterval=0.1
        maxIterations = max(math.ceil(maxWaitTimeFree/checkInterval),1)
        for _ in range(maxIterations):
            count = 0
            for i in occupied.get(portalId, []):
                if i["mac"] == mac:
                    count = count + 1
            if count < streamsPerMac:
                return True
            else:
                time.sleep(0.1)
        return False 

    portal = getPortals().get(portalId)
    portalName = portal.get("name")
    url = portal.get("url")
    macs = list(portal["macs"].keys())
    streamsPerMac = int(portal.get("streams per mac"))
    proxy = portal.get("proxy")
    web = request.args.get("web")
    ip = request.remote_addr

    logger.info(
        "IP({}) requested Portal({}):Channel({})".format(ip, portalId, channelId)
    )

    freeMac = False
    for mac in macs:
        channels = None
        cmd = None
        link = None
        if streamsPerMac == 0 or isMacFree():
            logger.info(
                "Trying Portal({}):MAC({}):Channel({})".format(portalId, mac, channelId)
            )
            freeMac = True
            token = stb.getToken(url, mac, proxy)
            if token:
                stb.getProfile(url, mac, token, proxy)
                channels = stb.getAllChannels(url, mac, token, proxy)
        else:
            logger.info(
                "Maximum streams for MAC({}) in use.".format(mac)
            )
        if channels:
            for c in channels:
                if str(c["id"]) == channelId:
                    channelName = portal.get("custom channel names", {}).get(channelId)
                    if channelName == None:
                        channelName = c["name"]
                    cmd = c["cmd"]
                    break

        if cmd:
            if "http://localhost/" in cmd:
                link = stb.getLink(url, mac, token, cmd, proxy)
            else:
                link = cmd.split(" ")[1]

        if link:
            if getSettings().get("test streams", "true") == "false" or testStream():
                    if getSettings().get("stream method", "ffmpeg") != "redirect":
                        return Response(
                            stream_with_context(streamData()), mimetype="application/octet-stream"
                        )
                    else:
                        logger.info("Redirect sent")
                        return redirect(link)

        logger.info(
            "Unable to connect to Portal({}) using MAC({})".format(portalId, mac)
        )
        # Try with next mac address
        moveMac(portalId, mac)

        if not getSettings().get("try all macs", "false") == "true":
            break

    # Look for fallback 
    if not web:
        logger.info(
            "Portal({}):Channel({}) is not working. Looking for fallbacks...".format(
                portalId, channelId
            )
        )

        portals = getPortals()
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
                                            "Unable to connect to fallback Portal({}) using MAC({})".format(portalId, mac)
                                        )
                                    if channels:
                                        fChannelId = k
                                        for c in channels:
                                            if str(c["id"]) == fChannelId:
                                                cmd = c["cmd"]
                                                break
                                        if cmd:
                                            if "http://localhost/" in cmd:
                                                link = stb.getLink(url, mac, token, cmd, proxy)
                                            else:
                                                link = cmd.split(" ")[1]
                                            if link:
                                                if testStream():
                                                    logger.info(
                                                        "Fallback found for Portal({}):Channel({})".format(portalId, channelId)
                                                    )
                                                    if getSettings().get("stream method", "ffmpeg") != "redirect":
                                                        return Response(
                                                            stream_with_context(streamData()),
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


# HD Homerun #


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


if __name__ == "__main__":
    config = loadConfig()
    if debug:
        # If DEBUG is active, use default flask development sever in debug mode
        logger.info("ATTENTION: Server started in debug mode. Don't use on productive systems!")
        # Flask server in debug mode can lead to errors in vscode debugger
        app.run(host="0.0.0.0", port=8001, debug=debug)
        #app.run(host="0.0.0.0", port=8001, debug=False)
    else:
        # On release use waitress server with multi-threading
        waitress.serve(app, port=8001, _quiet=True, threads=24)
