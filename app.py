import flask
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
)
from datetime import datetime, timezone
from functools import wraps
import secrets
import random

app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(32)

logger = logging.getLogger("STB-Proxy")
logger.setLevel(logging.INFO)
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

if os.getenv("DEBUG"):
    debug = bool(os.getenv("DEBUG"))
else:
    debug = True

occupied = {}
config = {}


def getConfig():
    try:
        with open(configFile) as f:
            data = json.load(f)
    except:
        logger.warning("No exiting config found. Creating a new one")
        data = {}

    data.setdefault("portals", {})
    data.setdefault("settings", {})

    data["settings"].setdefault("sort playlist by channel genre", "false")
    data["settings"].setdefault("sort playlist by channel name", "false")
    data["settings"].setdefault("sort playlist by channel number", "false")
    data["settings"].setdefault("ffmpeg command", "-vcodec copy -acodec copy -f mpegts")
    data["settings"].setdefault("ffprobe timeout", "5")
    data["settings"].setdefault("enable hdhr", "false")
    data["settings"].setdefault("hdhr name", "STB-Proxy")
    data["settings"].setdefault("hdhr id", uuid.uuid4().hex)
    data["settings"].setdefault("hdhr tuners", "1")
    data["settings"].setdefault("enable security", "false")
    data["settings"].setdefault("username", "admin")
    data["settings"].setdefault("password", "12345")

    portals = data.get("portals")
    for portal in portals:
        portals[portal].setdefault("name", "")
        portals[portal].setdefault("url", "")
        # convert old format
        mac = portals[portal].get("mac")
        if mac:
            expiry = portals[portal].get("expires", "Unknown")
            portals[portal].setdefault("macs", {mac: expiry})
            portals[portal].pop("mac")
            portals[portal].pop("expires")
        ####################
        portals[portal].setdefault("macs", [])
        portals[portal].setdefault("streams per mac", 1),
        portals[portal].setdefault("proxy", "")
        portals[portal].setdefault("enabled channels", [])
        portals[portal].setdefault("custom channel numbers", {})
        portals[portal].setdefault("custom channel names", {})
        portals[portal].setdefault("custom genres", {})
        portals[portal].setdefault("custom epg ids", {})
        portals[portal].setdefault("fallback channels", {})

    with open(configFile, "w") as f:
        json.dump(data, f, indent=4)

    return data


def getPortals():
    return config["portals"]


def savePortals(portals):
    global config

    with open(configFile, "w") as f:
        config["portals"] = portals
        json.dump(config, f, indent=4)

    config = getConfig()


def getSettings():
    return config["settings"]


def saveSettings(settings):
    global config

    with open(configFile, "w") as f:
        config["settings"] = settings
        json.dump(config, f, indent=4)

    config = getConfig()


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


@app.route("/", methods=["GET"])
@authorise
def home():
    return redirect("/portals", code=302)


@app.route("/portals", methods=["GET"])
@authorise
def portals():
    portals = getPortals()
    return render_template("portals.html", portals=portals)


@app.route("/portal/add", methods=["POST"])
@authorise
def portalsAdd():
    name = request.form["name"]
    url = request.form["url"]
    macs = request.form["macs"].split(",")
    streamsPerMac = request.form["streams per mac"]
    proxy = request.form["proxy"]
    id = uuid.uuid4().hex
    if url.endswith(".php") == False:
        url = stb.getUrl(url, proxy)
    working = {}
    portals = getPortals()
    for mac in macs:
        try:
            token = stb.getToken(url, mac, proxy)
            expiry = stb.getExpires(url, mac, token, proxy)
            genres = stb.getGenres(url, mac, token, proxy)
            if stb.getAllChannels(url, mac, token, proxy, genres):
                working[mac] = expiry
                logger.info(
                    "Successfully tested MAC({}) for Portal({})".format(mac, name)
                )
                flash(
                    "Successfully tested MAC({}) for Portal({})".format(mac, name),
                    "success",
                )
        except:
            logger.error("Error testing MAC({}) for Portal({})".format(mac, name))
            flash("Error testing MAC({}) for Portal({})".format(mac, name), "danger")
            pass
    if len(working) > 0:
        portals[id] = {
            "name": name,
            "url": url,
            "macs": working,
            "streams per mac": streamsPerMac,
            "proxy": proxy,
        }
        savePortals(portals)
        logger.info("Portal({}) added!".format(name))
    else:
        logger.error(
            "None of the accounts tested OK for Portal({}). Adding not successfull".format(
                name
            )
        )

    return redirect("/portals", code=302)


@app.route("/portal/update", methods=["POST"])
@authorise
def portalUpdate():
    name = request.form["name"]
    url = request.form["url"]
    macs = request.form["macs"].split(",")
    streamsPerMac = request.form["streams per mac"]
    proxy = request.form["proxy"]
    id = request.form["id"]
    if url.endswith(".php") == False:
        url = stb.getUrl(url, proxy)
    working = {}
    portals = getPortals()
    for mac in macs:
        try:
            token = stb.getToken(url, mac, proxy)
            expiry = stb.getExpires(url, mac, token, proxy)
            genres = stb.getGenres(url, mac, token, proxy)
            if stb.getAllChannels(url, mac, token, proxy, genres):
                working[mac] = expiry
                logger.info(
                    "Successfully tested MAC({}) for Portal({})".format(mac, name)
                )
                flash(
                    "Successfully tested MAC({}) for Portal({})".format(mac, name),
                    "success",
                )
        except:
            logger.error("Error testing MAC({}) for Portal({})".format(mac, name))
            flash("Error testing MAC({}) for Portal({})".format(mac, name), "danger")
            pass
    if len(working) > 0:
        portals[id]["name"] = name
        portals[id]["url"] = url
        portals[id]["macs"] = working
        portals[id]["streams per mac"] = streamsPerMac
        portals[id]["proxy"] = proxy
        savePortals(portals)
        logger.info("Portal({}) updated!".format(name))
    else:
        logger.error(
            "None of the accounts tested OK for Portal({}). Update not successfull".format(
                name
            )
        )

    return redirect("/portals", code=302)


@app.route("/portal/remove", methods=["POST"])
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


@app.route("/editor", methods=["GET"])
@authorise
def editor():
    channels = []
    portals = getPortals()
    if len(portals) > 0:
        for portal in portals:
            portalName = portals[portal]["name"]
            url = portals[portal]["url"]
            macs = list(portals[portal]["macs"].keys())
            proxy = portals[portal]["proxy"]
            enabledChannels = portals[portal]["enabled channels"]
            customChannelNames = portals[portal]["custom channel names"]
            customGenres = portals[portal]["custom genres"]
            customChannelNumbers = portals[portal]["custom channel numbers"]
            customEpgIds = portals[portal]["custom epg ids"]
            fallbackChannels = portals[portal]["fallback channels"]

            for mac in macs:
                try:
                    token = stb.getToken(url, mac, proxy)
                    genres = stb.getGenres(url, mac, token, proxy)
                    allChannels = stb.getAllChannels(url, mac, token, proxy, genres)
                    break
                except:
                    allChannels = None
                    genres = None

            if allChannels and genres:
                for channel in allChannels:
                    channelId = str(channel["id"])
                    channelName = str(channel["name"])
                    channelNumber = str(channel["number"])
                    genre = str(genres.get(channel["tv_genre_id"]))
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

    return render_template("editor.html", channels=channels)


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
            portals[portal]["enabled channels"].append(channelId)
        else:
            # portals[portal]["enabled channels"].remove(channelId)
            portals[portal]["enabled channels"] = list(
                filter((channelId).__ne__, portals[portal]["enabled channels"])
            )

    for edit in numberEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        customNumber = edit["custom number"]
        if customNumber:
            portals[portal]["custom channel numbers"].update({channelId: customNumber})
        else:
            portals[portal]["custom channel numbers"].pop(channelId)

    for edit in nameEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        customName = edit["custom name"]
        if customName:
            portals[portal]["custom channel names"].update({channelId: customName})
        else:
            portals[portal]["custom channel names"].pop(channelId)

    for edit in genreEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        customGenre = edit["custom genre"]
        if customGenre:
            portals[portal]["custom genres"].update({channelId: customGenre})
        else:
            portals[portal]["custom genres"].pop(channelId)

    for edit in epgEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        customEpgId = edit["custom epg id"]
        if customEpgId:
            portals[portal]["custom epg ids"].update({channelId: customEpgId})
        else:
            portals[portal]["custom epg ids"].pop(channelId)

    for edit in fallbackEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        channelName = edit["channel name"]
        if channelName:
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
    return render_template("settings.html", settings=settings)


@app.route("/settings/save", methods=["POST"])
@authorise
def save():
    ffmpeg = request.form["ffmpeg command"]
    ffprobe = request.form["ffprobe timeout"]
    enableHdhr = request.form["enable hdhr"]
    hdhrName = request.form["hdhr name"]
    hdhrTuners = request.form["hdhr tuners"]
    enableSecurity = request.form["enable security"]
    username = request.form["username"]
    password = request.form["password"]
    id = getSettings()["hdhr id"]
    sortGenre = request.form["sort playlist by channel genre"]
    sortName = request.form["sort playlist by channel name"]
    sortNumber = request.form["sort playlist by channel number"]
    settings = {
        "ffmpeg command": ffmpeg,
        "ffprobe timeout": ffprobe,
        "enable hdhr": enableHdhr,
        "hdhr name": hdhrName,
        "hdhr tuners": hdhrTuners,
        "enable security": enableSecurity,
        "username": username,
        "password": password,
        "hdhr id": id,
        "sort playlist by channel genre": sortGenre,
        "sort playlist by channel name": sortName,
        "sort playlist by channel number": sortNumber,
    }
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
        enabledChannels = portals[portal]["enabled channels"]
        if len(enabledChannels) != 0:
            name = portals[portal]["name"]
            url = portals[portal]["url"]
            macs = list(portals[portal]["macs"].keys())
            proxy = portals[portal]["proxy"]
            customChannelNames = portals[portal]["custom channel names"]
            customGenres = portals[portal]["custom genres"]
            customChannelNumbers = portals[portal]["custom channel numbers"]
            customEpgIds = portals[portal]["custom epg ids"]

            for mac in macs:
                try:
                    token = stb.getToken(url, mac, proxy)
                    genres = stb.getGenres(url, mac, token, proxy)
                    allChannels = stb.getAllChannels(url, mac, token, proxy, genres)
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
                            genre = genres.get(genreId)
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
                            + '" tvg-chno="'
                            + channelNumber
                            + '" group-title="'
                            + genre
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
    if getSettings().get("sort playlist by channel number", "false") == "true":
        channels.sort(key=lambda k: k.split('tvg-chno="')[1].split('"')[0])
    if getSettings().get("sort playlist by channel genre", "false") == "true":
        channels.sort(key=lambda k: k.split('group-title="')[1].split('"')[0])

    playlist = "#EXTM3U \n"
    playlist = playlist + "\n".join(channels)

    return Response(playlist, mimetype="text/plain")


@app.route("/xmltv", methods=["GET"])
@authorise
def xmltv():
    channels = ET.Element("tv")
    programmes = ET.Element("tv")
    portals = getPortals()
    for portal in portals:
        enabledChannels = portals[portal]["enabled channels"]
        if len(enabledChannels) != 0:
            name = portals[portal]["name"]
            url = portals[portal]["url"]
            macs = list(portals[portal]["macs"].keys())
            proxy = portals[portal]["proxy"]
            customChannelNames = portals[portal]["custom channel names"]

            for mac in macs:
                try:
                    token = stb.getToken(url, mac, proxy)
                    genres = stb.getGenres(url, mac, token, proxy)
                    allChannels = stb.getAllChannels(url, mac, token, proxy, genres)
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
                            channelEle = ET.SubElement(
                                channels, "channel", id=portal + channelId
                            )
                            ET.SubElement(channelEle, "display-name").text = channelName
                            ET.SubElement(channelEle, "icon", src=c.get("logo"))
                            for p in epg.get(channelId):
                                try:
                                    start = (
                                        datetime.utcfromtimestamp(
                                            p.get("start_timestamp")
                                        ).strftime("%Y%m%d%H%M%S")
                                        + " +0000"
                                    )
                                    stop = (
                                        datetime.utcfromtimestamp(
                                            p.get("stop_timestamp")
                                        ).strftime("%Y%m%d%H%M%S")
                                        + " +0000"
                                    )
                                    programmeEle = ET.SubElement(
                                        programmes,
                                        "programme",
                                        start=start,
                                        stop=stop,
                                        channel=portal + channelId,
                                    )
                                    ET.SubElement(programmeEle, "title").text = p.get(
                                        "name"
                                    )
                                    ET.SubElement(programmeEle, "desc").text = p.get(
                                        "descr"
                                    )
                                except:
                                    pass
                    except:
                        pass
            else:
                logger.error("Error making XMLTV for {}, skipping".format(name))

    xmltv = channels
    for programme in programmes.iter("programme"):
        xmltv.append(programme)

    return Response(ET.tostring(xmltv, encoding="unicode"), mimetype="text/xml")


@app.route("/play/<portalId>/<channelId>", methods=["GET"])
def channel(portalId, channelId):
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

        if proxy:
            ffmpegcmd.insert(1, "-http_proxy")
            ffmpegcmd.insert(2, proxy)

        try:
            startTime = datetime.now(timezone.utc).timestamp()
            occupy()
            with subprocess.Popen(
                ffmpegcmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as ffmpeg_sb:
                while True:
                    chunk = ffmpeg_sb.stdout.read(1024)
                    if len(chunk) == 0:
                        break
                    yield chunk
        except:
            pass
        finally:
            unoccupy()
            ffmpeg_sb.kill()

    def testStream():
        timeout = int(getSettings()["ffprobe timeout"]) * int(1000000)
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

    def getFallback():
        portals = getPortals()
        for portal in portals:
            fPortalId = portal
            fallbackChannels = portals[portal]["fallback channels"]
            if channelName in fallbackChannels.values():
                url = portals[portal].get("url")
                macs = list(portals[portal]["macs"].keys())
                proxy = portals[portal].get("proxy")
                for mac in macs:
                    if streamsPerMac == 0 or isMacFree():
                        for k, v in fallbackChannels.items():
                            if v == channelName:
                                try:
                                    token = stb.getToken(url, mac, proxy)          
                                    genres = stb.getGenres(url, mac, token, proxy)
                                    channels = stb.getAllChannels(
                                        url, mac, token, proxy, genres
                                    )
                                except:
                                    channels = None
                                if channels:
                                    cmd = None
                                    link = None
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
                                                return link

    def isMacFree():
        count = 0
        for i in occupied.get(portalId, []):
            if i["mac"] == mac:
                count = count + 1
        if count < streamsPerMac:
            return True
        else:
            return False

    portal = getPortals().get(portalId)
    portalName = portal.get("name")
    url = portal.get("url")
    macs = list(portal["macs"].keys())
    streamsPerMac = int(portal.get("streams per mac"))
    random.shuffle(macs)
    proxy = portal.get("proxy")
    web = request.args.get("web")
    ip = request.remote_addr

    logger.info(
        "IP({}) requested Portal({}):Channel({})".format(ip, portalId, channelId)
    )

    link = None
    freeMac = False
    channels = False

    for mac in macs:
        if streamsPerMac == 0 or isMacFree():
            logger.info(
                "Trying Portal({}):MAC({}):Channel({})".format(portalId, mac, channelId)
            )
            try:
                token = stb.getToken(url, mac, proxy)
                genres = stb.getGenres(url, mac, token, proxy)
                channels = stb.getAllChannels(url, mac, token, proxy, genres)
                freeMac = True
                break
            except:
                logger.info(
                    "Unable to connect to Portal({}) using MAC({})".format(
                        portalId, mac
                    )
                )
                channels = None

    if channels:
        cmd = None
        for c in channels:
            if str(c["id"]) == channelId:
                channelName = portal["custom channel names"].get(channelId)
                if channelName == None:
                    channelName = c["name"]
                    if c["cmds"]: 
                        data = c["cmds"]
                        raw = data[0]["url"]
                        cmd = raw.replace("ffmpeg http : //localhost/", "http://localhost/")
                    else:
                        cmd = c["cmd"]
                break
        
        if cmd:
            if "http://localhost/" in cmd:
                link = stb.getLink(url, mac, token, cmd, proxy)
                logger.info(f"Link grabbed was: {link}")
            else:
                link = cmd.split(" ")[1]

            if testStream():
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
                    return Response(streamData())

                else:
                    ffmpegcmd = [
                        "ffmpeg",
                        "-loglevel",
                        "panic",
                        "-hide_banner",
                        "-i",
                        link,
                    ]
                    ffmpegcmd.extend(getSettings()["ffmpeg command"].split())
                    ffmpegcmd.append("pipe:")
                    return Response(streamData())

            elif not web:
                logger.info(
                    "Portal({}):Channel({}) is not working. Looking for fallbacks...".format(
                        portalId, channelId
                    )
                )
                link = getFallback()
                if link:
                    ffmpegcmd = [
                        "ffmpeg",
                        "-loglevel",
                        "panic",
                        "-hide_banner",
                        "-i",
                        link,
                    ]
                    ffmpegcmd.extend(getSettings()["ffmpeg command"].split())
                    ffmpegcmd.append("pipe:")
                    return Response(streamData())

    if freeMac:
        logger.info(
            "No working streams found for Portal({}):Channel({})".format(
                portalId, channelId
            )
        )
    else:
        logger.info(
            "No free working MAC for Portal({}):Channel({})".format(portalId, channelId)
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
        enabledChannels = portals[portal]["enabled channels"]
        if len(enabledChannels) != 0:
            name = portals[portal]["name"]
            url = portals[portal]["url"]
            macs = list(portals[portal]["macs"].keys())
            proxy = portals[portal]["proxy"]
            customChannelNames = portals[portal]["custom channel names"]
            customChannelNumbers = portals[portal]["custom channel numbers"]

            for mac in macs:
                try:
                    token = stb.getToken(url, mac, proxy)
                    genres = stb.getGenres(url, mac, token, proxy)
                    allChannels = stb.getAllChannels(url, mac, token, proxy, genres)
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
    config = getConfig()
    app.run(host="0.0.0.0", port=8001, debug=debug)
