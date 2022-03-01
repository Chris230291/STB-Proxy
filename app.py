import stb
from flask import Flask, render_template, redirect, request, Response
from pathlib import Path
import os
import sys
import json
import subprocess
import uuid
import xml.etree.cElementTree as ET
from datetime import datetime

app = Flask(__name__)
basePath = Path(__file__).resolve().parent

if os.getenv("HOST"):
    host = os.getenv("HOST")
else:
    host = "localhost:8001"


if os.getenv("CONFIG"):
    config_file = os.getenv("CONFIG")
else:
    config_file = str(basePath) + "/config.json"


def getConfig():
    try:
        with open(config_file) as f:
            data = json.load(f)
    except:
        print("Creating config file")
        data = {}

    data.setdefault("portals", {})
    data.setdefault("settings", {})
    data["settings"].setdefault(
        "ffmpeg command", "-vcodec copy -acodec copy -f mpegts")
    data["settings"].setdefault("ffprobe timeout", "5")
    data["settings"].setdefault("hdhr name", "STB-Proxy")
    data["settings"].setdefault("hdhr id", uuid.uuid4().hex)
    data["settings"].setdefault("hdhr tuners", "1")

    portals = data.get("portals")
    for portal in portals:
        portals[portal].setdefault("enabled", "true")
        portals[portal].setdefault("name", "")
        portals[portal].setdefault("url", "")
        portals[portal].setdefault("mac", "")
        portals[portal].setdefault("proxy", "")
        portals[portal].setdefault("ffmpeg", "false")
        portals[portal].setdefault("expires", "")
        portals[portal].setdefault("enabled channels", [])
        portals[portal].setdefault("custom channel numbers", {})
        portals[portal].setdefault("custom channel names", {})
        portals[portal].setdefault("custom genres", {})
        portals[portal].setdefault("custom epg ids", {})
        portals[portal].setdefault("fallback channels", {})

    with open(config_file, "w") as f:
        json.dump(data, f, indent=4)

    return data


def getPortals():
    data = getConfig()
    return data["portals"]


def savePortals(portals):
    with open(config_file) as f:
        data = json.load(f)
    with open(config_file, "w") as f:
        data["portals"] = portals
        json.dump(data, f, indent=4)


def getSettings():
    data = getConfig()
    return data["settings"]


def saveSettings(settings):
    with open(config_file) as f:
        data = json.load(f)
    with open(config_file, "w") as f:
        data["settings"] = settings
        json.dump(data, f, indent=4)


@app.route("/", methods=["GET"])
def home():
    return redirect("/portals", code=302)


@app.route("/portals", methods=["GET"])
def portals():
    portals = getPortals()
    return render_template("portals.html", portals=portals)


@app.route("/portal/add", methods=["POST"])
def portalsAdd():
    enabled = request.form["enabled"]
    name = request.form["name"]
    url = request.form["url"]
    mac = request.form["mac"]
    proxy = request.form["proxy"]
    ffmpeg = request.form["ffmpeg"]
    if url.endswith('.php') == False:
        url = stb.getUrl(url, proxy)
    try:
        portals = getPortals()
        token = stb.getToken(url, mac, proxy)
        expiry = stb.getExpires(url, mac, token, proxy)
        id = uuid.uuid4().hex
        portals[id] = {
            "enabled": enabled,
            "name": name,
            "url": url,
            "mac": mac,
            "proxy": proxy,
            "ffmpeg": ffmpeg,
            "expires": expiry,
        }
        savePortals(portals)
    except:
        print("Error adding portal")
        pass
    return redirect("/portals", code=302)


@app.route("/portal/update", methods=["POST"])
def portalUpdate():
    id = request.form["id"]
    enabled = request.form["enabled"]
    name = request.form["name"]
    url = request.form["url"]
    mac = request.form["mac"]
    proxy = request.form["proxy"]
    ffmpeg = request.form["ffmpeg"]
    if url.endswith('.php') == False:
        url = stb.getUrl(url, proxy)
    try:
        portals = getPortals()
        token = stb.getToken(url, mac, proxy)
        expiry = stb.getExpires(url, mac, token, proxy)
        portals[id]["enabled"] = enabled
        portals[id]["name"] = name
        portals[id]["url"] = url
        portals[id]["mac"] = mac
        portals[id]["proxy"] = proxy
        portals[id]["ffmpeg"] = ffmpeg
        portals[id]["expires"] = expiry
        savePortals(portals)
    except:
        print("Error updating portal")
        pass
    return redirect("/portals", code=302)


@app.route("/portal/remove", methods=["POST"])
def portalRemove():
    id = request.form["id"]
    portals = getPortals()
    del portals[id]
    savePortals(portals)
    return redirect("/portals", code=302)


@app.route("/editor", methods=["GET"])
def editor():
    channels = []
    portals = getPortals()
    if len(portals) > 0:
        for portal in portals:
            if portals[portal]["enabled"] == "true":
                portalName = portals[portal]["name"]
                url = portals[portal]["url"]
                mac = portals[portal]["mac"]
                proxy = portals[portal]["proxy"]
                enabledChannels = portals[portal]["enabled channels"]
                customChannelNames = portals[portal]["custom channel names"]
                customGenres = portals[portal]["custom genres"]
                customChannelNumbers = portals[portal]["custom channel numbers"]
                customEpgIds = portals[portal]["custom epg ids"]
                fallbackChannels = portals[portal]["fallback channels"]
                try:
                    token = stb.getToken(url, mac, proxy)
                    allChannels = stb.getAllChannels(url, mac, token, proxy)
                    genres = stb.getGenres(url, mac, token, proxy)
                    for channel in allChannels:
                        channelId = str(channel["id"])
                        channelName = str(channel["name"])
                        channelNumber = str(channel["number"])
                        genre = str(genres.get(channel["tv_genre_id"]))
                        if channelId in enabledChannels:
                            enabled = True
                        else:
                            enabled = False
                        customChannelNumber = customChannelNumbers.get(
                            channelId)
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
                except:
                    print(sys.exc_info()[1])
                    pass
    return render_template("editor.html", channels=channels)


@app.route("/editor/save", methods=["POST"])
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
            #portals[portal]["enabled channels"].remove(channelId)
            portals[portal]["enabled channels"] = list(filter((channelId).__ne__, portals[portal]["enabled channels"]))

    for edit in numberEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        customNumber = edit["custom number"]
        if customNumber:
            portals[portal]["custom channel numbers"].update(
                {channelId: customNumber})
        else:
            portals[portal]["custom channel numbers"].pop(channelId)

    for edit in nameEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        customName = edit["custom name"]
        if customName:
            portals[portal]["custom channel names"].update(
                {channelId: customName})
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
            portals[portal]["fallback channels"].update(
                {channelId: channelName})
        else:
            portals[portal]["fallback channels"].pop(channelId)

    savePortals(portals)
    return redirect("/editor", code=302)


@app.route("/settings", methods=["GET"])
def settings():
    settings = getSettings()
    return render_template("settings.html", settings=settings)


@app.route("/settings/save", methods=["POST"])
def save():
    ffmpeg = request.form["ffmpeg command"]
    ffprobe = request.form["ffprobe timeout"]
    hdhrName = request.form["hdhr name"]
    hdhrTuners = request.form["hdhr tuners"]
    id = getSettings()["hdhr id"]
    settings = {"ffmpeg command": ffmpeg,
                "ffprobe timeout": ffprobe,
                "hdhr name": hdhrName,
                "hdhr tuners": hdhrTuners,
                "hdhr id": id
                }
    saveSettings(settings)
    return redirect("/settings", code=302)


@app.route("/playlist", methods=["GET"])
def playlist():
    channels = []
    portals = getPortals()
    for portal in portals:
        if portals[portal]["enabled"] == "true":
            name = portals[portal]["name"]
            url = portals[portal]["url"]
            mac = portals[portal]["mac"]
            proxy = portals[portal]["proxy"]
            enabledChannels = portals[portal]["enabled channels"]
            customChannelNames = portals[portal]["custom channel names"]
            customGenres = portals[portal]["custom genres"]
            customChannelNumbers = portals[portal]["custom channel numbers"]
            customEpgIds = portals[portal]["custom epg ids"]
            if len(enabledChannels) != 0:
                try:
                    token = stb.getToken(url, mac, proxy)
                    allChannels = stb.getAllChannels(url, mac, token, proxy)
                    genres = stb.getGenres(url, mac, token, proxy)
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
                except:
                    print("Error making playlist for " + name)
                    pass
    channels.sort(key=lambda k: k.split(",")[1])
    playlist = "#EXTM3U \n"
    playlist = playlist + "\n".join(channels)
    return Response(playlist, mimetype="text/plain")


@app.route("/xmltv", methods=["GET"])
def xmltv():
    channels = ET.Element("tv")
    programmes = ET.Element("tv")
    portals = getPortals()
    for portal in portals:
        if portals[portal]["enabled"] == "true":
            name = portals[portal]["name"]
            url = portals[portal]["url"]
            mac = portals[portal]["mac"]
            proxy = portals[portal]["proxy"]
            enabledChannels = portals[portal]["enabled channels"]
            customChannelNames = portals[portal]["custom channel names"]
            if len(enabledChannels) != 0:
                try:
                    token = stb.getToken(url, mac, proxy)
                    allChannels = stb.getAllChannels(url, mac, token, proxy)
                    epg = stb.getEpg(url, mac, token, 24, proxy)
                    for c in allChannels:
                        try:
                            channelId = c.get("id")
                            if str(channelId) in enabledChannels:
                                channelName = customChannelNames.get(
                                    str(channelId))
                                if channelName == None:
                                    channelName = str(c.get("name"))
                                channelEle = ET.SubElement(
                                    channels, "channel", id=portal + channelId
                                )
                                ET.SubElement(
                                    channelEle, "display-name").text = channelName
                                ET.SubElement(channelEle, "icon",
                                              src=c.get("logo"))
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
                except:
                    print("Error making XMLTV for " + name)

    xmltv = channels
    for programme in programmes.iter("programme"):
        xmltv.append(programme)

    return Response(ET.tostring(xmltv, encoding="unicode"), mimetype="text/xml")


@app.route("/play/<portal>/<channel>", methods=["GET"])
def channel(portal, channel):
    def streamData(ffmpegcmd):
        try:
            with subprocess.Popen(
                ffmpegcmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as ffmpeg_sb:
                for chunk in iter(ffmpeg_sb.stdout.readline, ""):
                    yield chunk
                    if ffmpeg_sb.poll() is not None:
                        break
        except:
            pass
        finally:
            ffmpeg_sb.kill()

    def testStream(link, proxy):
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

    portal = getPortals().get(portal)
    url = portal.get("url")
    mac = portal.get("mac")
    proxy = portal.get("proxy")
    ffmpeg = portal.get("ffmpeg")
    web = request.args.get("web")

    token = stb.getToken(url, mac, proxy)
    channels = stb.getAllChannels(url, mac, token, proxy)

    for c in channels:
        if str(c["id"]) == channel:
            name = portal["custom channel names"].get(channel)
            if name == None:
                name = c["name"]
            cmd = c["cmd"]
            break

    if "http://localhost/" in cmd:
        link = stb.getLink(url, mac, token, cmd, proxy)
    else:
        link = cmd.split(" ")[1]

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
            ffmpegcmd.insert(4, "-http_proxy")
            ffmpegcmd.insert(5, proxy)

        return Response(streamData(ffmpegcmd))

    if not testStream(link, proxy):
        portals = getPortals()
        found = False
        for portal in portals:
            if portals[portal]["enabled"] == "true":
                fallbackChannels = portals[portal]["fallback channels"]
                if name in fallbackChannels.values():
                    url = portals[portal].get("url")
                    mac = portals[portal].get("mac")
                    proxy = portals[portal].get("proxy")
                    ffmpeg = portals[portal].get("ffmpeg")
                    token = stb.getToken(url, mac, proxy)
                    if not token:
                        break
                    channels = stb.getAllChannels(url, mac, token, proxy)

                    for k, v in fallbackChannels.items():
                        if v == name:
                            channel = k
                            for c in channels:
                                if str(c["id"]) == channel:
                                    cmd = c["cmd"]
                                    break

                            if "http://localhost/" in cmd:
                                link = stb.getLink(url, mac, token, cmd, proxy)
                            else:
                                link = cmd.split(" ")[1]

                            if testStream(link, proxy):
                                found = True
                                break
            if found:
                break

    if ffmpeg == "true":
        ffmpegcmd = [
            "ffmpeg",
            "-loglevel",
            "panic",
            "-hide_banner",
            "-i",
            link,
        ]

        if proxy:
            ffmpegcmd.insert(4, "-http_proxy")
            ffmpegcmd.insert(5, proxy)

        ffmpegcmd.extend(getSettings()["ffmpeg command"].split())
        ffmpegcmd.append("pipe:")

        return Response(streamData(ffmpegcmd))
    else:
        return redirect(link, code=302)


@app.route("/discover.json", methods=["GET"])
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
        "TunerCount": int(tuners)
    }
    return Response(json.dumps(data, indent=4), status=200, mimetype='application/json')


@app.route('/lineup_status.json', methods=["GET"])
def status():
    data = {
        'ScanInProgress': 0,
        'ScanPossible': 0,
        'Source': "Antenna",
        'SourceList': ['Antenna']
    }
    return Response(json.dumps(data, indent=4), status=200, mimetype='application/json')


@app.route('/lineup.json', methods=["GET"])
@app.route('/lineup.post', methods=["POST"])
def lineup():
    lineup = []
    portals = getPortals()
    for portal in portals:
        if portals[portal]["enabled"] == "true":
            name = portals[portal]["name"]
            url = portals[portal]["url"]
            mac = portals[portal]["mac"]
            proxy = portals[portal]["proxy"]
            enabledChannels = portals[portal]["enabled channels"]
            customChannelNames = portals[portal]["custom channel names"]
            customChannelNumbers = portals[portal]["custom channel numbers"]
            if len(enabledChannels) != 0:
                try:
                    token = stb.getToken(url, mac, proxy)
                    allChannels = stb.getAllChannels(url, mac, token, proxy)
                    for channel in allChannels:
                        channelId = str(channel.get("id"))
                        if channelId in enabledChannels:
                            channelName = customChannelNames.get(channelId)
                            if channelName == None:
                                channelName = str(channel.get("name"))
                            channelNumber = customChannelNumbers.get(channelId)
                            if channelNumber == None:
                                channelNumber = str(channel.get("number"))

                            lineup.append({'GuideNumber': channelNumber, 'GuideName': channelName,
                                          'URL': "http://" + host + "/play/" + portal + "/" + channelId})
                except:
                    print("Error making lineup for " + name)
                    pass
    return json.dumps(lineup)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
