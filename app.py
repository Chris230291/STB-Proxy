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
import time

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


def getPortals():
    try:
        with open(config_file) as f:
            data = json.load(f)
            portals = data.get("portals")
            # portals = dict(sorted(portals.items(), key = lambda x: x[1]['name']))
    except:
        print("Creating config file")
        data = {}
        data["portals"] = {}
        portals = {}
        savePortals(portals)
    for portal in portals:
        portals[portal].setdefault("name", "")
        portals[portal].setdefault("url", "")
        portals[portal].setdefault("mac", "")
        portals[portal].setdefault("proxy", "")
        portals[portal].setdefault("format", "redirect")
        portals[portal].setdefault("expires", "")
        portals[portal].setdefault("enabled channels", [])
        portals[portal].setdefault("custom channel numbers", {})
        portals[portal].setdefault("custom channel names", {})
        portals[portal].setdefault("custom genres", {})
        portals[portal].setdefault("custom epg ids", {})
    return portals


def savePortals(portals):
    with open(config_file, "w") as f:
        data = {}
        data["portals"] = portals
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
    name = request.form["name"]
    url = stb.getUrl(request.form["url"])
    mac = request.form["mac"]
    proxy = request.form["proxy"]
    format = request.form["format"]
    try:
        portals = getPortals()
        token = stb.getToken(url, mac)
        expiry = stb.getExpires(url, mac, token)
        id = uuid.uuid4().hex
        portals[id] = {
            "name": name,
            "url": url,
            "mac": mac,
            "proxy": proxy,
            "format": format,
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
    name = request.form["name"]
    url = stb.getUrl(request.form["url"])
    mac = request.form["mac"]
    proxy = request.form["proxy"]
    format = request.form["format"]
    try:
        portals = getPortals()
        token = stb.getToken(url, mac)
        expiry = stb.getExpires(url, mac, token)
        portals[id]["name"] = name
        portals[id]["url"] = url
        portals[id]["mac"] = mac
        portals[id]["proxy"] = proxy
        portals[id]["format"] = format
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
            portalName = portals[portal]["name"]
            url = portals[portal]["url"]
            mac = portals[portal]["mac"]
            enabledChannels = portals[portal]["enabled channels"]
            customChannelNames = portals[portal]["custom channel names"]
            customGenres = portals[portal]["custom genres"]
            customChannelNumbers = portals[portal]["custom channel numbers"]
            customEpgIds = portals[portal]["custom epg ids"]
            try:
                token = stb.getToken(url, mac)
                allChannels = stb.getAllChannels(url, mac, token)
                genres = stb.getGenres(url, mac, token)
                for channel in allChannels:
                    channelId = channel["id"]
                    channelName = channel["name"]
                    channelNumber = channel["number"]
                    genre = genres.get(channel["tv_genre_id"])
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
                            "link": "http://"
                            + host
                            + "/play/"
                            + portal
                            + "/"
                            + channelId
                            + "?format=mp4",
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
    portals = getPortals()
    for edit in enabledEdits:
        portal = edit["portal"]
        channelId = edit["channel id"]
        enabled = edit["enabled"]
        if enabled:
            portals[portal]["enabled channels"].append(channelId)
        else:
            portals[portal]["enabled channels"].remove(channelId)

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

    savePortals(portals)
    return redirect("/editor", code=302)


#@app.route("/player", methods=["GET"])
#def player():
    channels = []
    portals = getPortals()
    for portal in portals:
        url = portals[portal]["url"]
        mac = portals[portal]["mac"]
        enabledChannels = portals[portal]["enabled channels"]
        customChannelNames = portals[portal]["custom channel names"]
        customGenres = portals[portal]["custom genres"]
        if len(enabledChannels) != 0:
            try:
                token = stb.getToken(url, mac)
                allChannels = stb.getAllChannels(url, mac, token)
                genres = stb.getGenres(url, mac, token)
                allEpgs = stb.getEpg(url, mac, token, 1)
                for channel in allChannels:
                    try:
                        channelId = channel.get("id")
                        if channelId in enabledChannels:
                            channelName = customChannelNames.get(channelId)
                            if channelName == None:
                                channelName = channel.get("name")
                            genre = customGenres.get(channelId)
                            if genre == None:
                                genreId = channel.get("tv_genre_id")
                                genre = genres.get(genreId)
                            epg = allEpgs.get(channelId, [])
                            link = (
                                "http://"
                                + host
                                + "/play/"
                                + portal
                                + "/"
                                + channelId
                                + "?format=mp4"
                            )
                            channels.append(
                                {
                                    "name": channelName,
                                    "genre": genre,
                                    "link": link,
                                    "epg": epg,
                                }
                            )
                    except:
                        pass
            except:
                print("Error getting channels for " + portals[portal]["name"])
                pass
            channels.sort(key=lambda k: k["name"])
            now = int(time.time())
    return render_template("player.html", channels=channels, now=now)


@app.route("/playlist", methods=["GET"])
def playlist():
    channels = []
    portals = getPortals()
    for portal in portals:
        name = portals[portal]["name"]
        url = portals[portal]["url"]
        mac = portals[portal]["mac"]
        enabledChannels = portals[portal]["enabled channels"]
        customChannelNames = portals[portal]["custom channel names"]
        customGenres = portals[portal]["custom genres"]
        customChannelNumbers = portals[portal]["custom channel numbers"]
        customEpgIds = portals[portal]["custom epg ids"]
        if len(enabledChannels) != 0:
            try:
                token = stb.getToken(url, mac)
                allChannels = stb.getAllChannels(url, mac, token)
                genres = stb.getGenres(url, mac, token)
                for channel in allChannels:
                    channelId = channel.get("id")
                    if channelId in enabledChannels:
                        channelName = customChannelNames.get(channelId)
                        if channelName == None:
                            channelName = channel.get("name")
                        genre = customGenres.get(channelId)
                        if genre == None:
                            genreId = channel.get("tv_genre_id")
                            genre = genres.get(genreId)
                        channelNumber = customChannelNumbers.get(channelId)
                        if channelNumber == None:
                            channelNumber = channel.get("number")
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


@app.route("/play/<portal>/<channel>", methods=["GET"])
def channel(portal, channel):
    def streamData(link, proxy, format):
        if format == "mp4":
            ffmpegcmd = [
                "ffmpeg",
                "-loglevel",
                "panic",
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
        elif format == "mpegts":
            ffmpegcmd = [
                "ffmpeg",
                "-loglevel",
                "panic",
                "-i",
                link,
                "-c",
                "copy",
                "-f",
                "mpegts",
                "pipe:",
            ]
        elif format == "hls":
            ffmpegcmd = [
                "ffmpeg",
                "-loglevel",
                "panic",
                "-hide_banner",
                "-i",
                link,
                "-c",
                "copy",
                "-f",
                "hls",
                "pipe:",
            ]

        if proxy:
            ffmpegcmd.insert(5, "-http_proxy")
            ffmpegcmd.insert(6, proxy)

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

        #print("Stream Ended")

    portal = getPortals().get(portal)
    url = portal.get("url")
    mac = portal.get("mac")
    proxy = portal.get("proxy")
    format = request.args.get("format")
    if format is None:
        format = portal.get("format")

    token = stb.getToken(url, mac)
    channels = stb.getAllChannels(url, mac, token)
    for c in channels:
        if c["id"] == channel:
            cmd = c["cmd"]
            break

    if format == "redirect":
        try:
            token = stb.getToken(url, mac)
            if "http://localhost/" in cmd:
                link = stb.getLink(url, mac, token, cmd)
            else:
                link = cmd.split(" ")[1]
            return redirect(link, code=302)
        except:
            print(sys.exc_info()[1])
            pass
    else:
        try:
            token = stb.getToken(url, mac)
            if "http://localhost/" in cmd:
                link = stb.getLink(url, mac, token, cmd)
            else:
                link = cmd.split(" ")[1]
            return Response(streamData(link, proxy, format))
        except:
            print(sys.exc_info()[1])
            pass


@app.route("/xmltv", methods=["GET"])
def xmltv():
    channels = ET.Element("tv")
    programmes = ET.Element("tv")
    portals = getPortals()
    for portal in portals:
        name = portals[portal]["name"]
        url = portals[portal]["url"]
        mac = portals[portal]["mac"]
        enabledChannels = portals[portal]["enabled channels"]
        customChannelNames = portals[portal]["custom channel names"]
        if len(enabledChannels) != 0:
            try:
                token = stb.getToken(url, mac)
                allChannels = stb.getAllChannels(url, mac, token)
                epg = stb.getEpg(url, mac, token, 24)
                for c in allChannels:
                    try:
                        channelId = c.get("id")
                        if channelId in enabledChannels:
                            channelName = customChannelNames.get(channelId)
                            if channelName == None:
                                channelName = c.get("name")
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
            except:
                print("Error making XMLTV for " + name)

    xmltv = channels
    for programme in programmes.iter("programme"):
        xmltv.append(programme)

    return Response(ET.tostring(xmltv, encoding="unicode"), mimetype="text/xml")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
