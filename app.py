import stb
from flask import Flask, render_template, redirect, request, Response
from pathlib import Path
import os
import sys
import json
from urllib import parse
import subprocess


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
            portals = data["portals"]
    except:
        print("Creating config file")
        data = {}
        data["portals"] = []
        portals = []
        savePortals(portals)
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
    names = []
    masterBlacklist = "^((?=[a-zA-Z0-9_-]+).)*$"
    blacklists = []
    portals = getPortals()
    if portals and len(portals) > 0:
        for i in portals:
            names.append(i["name"])
        # ^((?!^word1$|^word2$)(?=[a-zA-Z0-9_-]+).)*$
        masterBlacklist = "^((?!^" + ("$|^".join(names)) + "$)(?=[a-zA-Z0-9_-]+).)*$"
        for i in portals:
            inames = names.copy()
            iname = i["name"]
            inames.remove(iname)
            blacklist = "^((?!^" + ("$|^".join(inames)) + "$)(?=[a-zA-Z0-9_-]+).)*$"
            blacklists.append(blacklist)
    return render_template(
        "portals.html",
        portals=portals,
        masterBlacklist=masterBlacklist,
        blacklists=blacklists,
    )


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
        portals.append(
            {
                "name": name,
                "url": url,
                "mac": mac,
                "proxy": proxy,
                "format": format,
                "expires": expiry,
                "enabled channels": [],
                "custom channel names": {},
                "custom genres": {},
            }
        )
        savePortals(portals)
    except:
        print(sys.exc_info()[1])
        pass
    return redirect("/portals", code=302)


@app.route("/portal/update", methods=["POST"])
def portalUpdate():
    name = request.form["name"]
    oname = request.form["oname"]
    url = stb.getUrl(request.form["url"])
    mac = request.form["mac"]
    proxy = request.form["proxy"]
    format = request.form["format"]
    try:
        portals = getPortals()
        token = stb.getToken(url, mac)
        expiry = stb.getExpires(url, mac, token)
        for i in range(len(portals)):
            if portals[i]["name"] == oname:
                portals[i]["name"] = name
                portals[i]["url"] = url
                portals[i]["mac"] = mac
                portals[i]["proxy"] = proxy
                portals[i]["format"] = format
                portals[i]["expires"] = expiry
                savePortals(portals)
                break
    except:
        print(sys.exc_info()[1])
        pass
    return redirect("/portals", code=302)


@app.route("/portal/remove", methods=["POST"])
def portalRemove():
    name = request.form["name"]
    portals = getPortals()
    for i in range(len(portals)):
        if portals[i]["name"] == name:
            portals.pop(i)
            break
    savePortals(portals)
    return redirect("/portals", code=302)


@app.route("/editor", methods=["GET"])
def editor():
    channels = []
    portals = getPortals()
    if len(portals) > 0:
        for p in portals:
            portalName = p["name"]
            url = p["url"]
            mac = p["mac"]
            enabledChannels = p["enabled channels"]
            customChannelNames = p["custom channel names"]
            customGenres = p["custom genres"]
            try:
                token = stb.getToken(url, mac)
                allChannels = stb.getAllChannels(url, mac, token)
                genres = stb.getGenres(url, mac, token)
                for i in allChannels:
                    channelId = i["id"]
                    channelName = i["name"]
                    genre = genres.get(i["tv_genre_id"])
                    if channelId in enabledChannels:
                        enabled = True
                    else:
                        enabled = False
                    customChannelName = customChannelNames.get(channelId)
                    if customChannelName == None:
                        customChannelName = ""
                    customGenre = customGenres.get(channelId)
                    if customGenre == None:
                        customGenre = ""
                    channels.append(
                        {
                            "enabled": enabled,
                            "channelName": channelName,
                            "customChannelName": customChannelName,
                            "genre": genre,
                            "customGenre": customGenre,
                            "channelId": channelId,
                            "portalName": portalName,
                        }
                    )
            except:
                print(sys.exc_info()[1])
                pass
    return render_template("editor.html", channels=channels)


@app.route("/editor/save", methods=["POST"])
def editorSave():
    enabledEdits = json.loads(request.form["enabledEdits"])
    nameEdits = json.loads(request.form["nameEdits"])
    genreEdits = json.loads(request.form["genreEdits"])
    portals = getPortals()
    for e in enabledEdits:
        portal = e["portal"]
        chid = e["channel id"]
        enabled = e["enabled"]
        for i, p in enumerate(portals):
            if p["name"] == portal:
                enabledChannels = p["enabled channels"]
                if enabled:
                    enabledChannels.append(chid)
                else:
                    enabledChannels.remove(chid)
                enabledChannels = list(set(enabledChannels))
                portals[i]["enabled channels"] = enabledChannels
                break
    for n in nameEdits:
        portal = n["portal"]
        chid = n["channel id"]
        customName = n["custom name"]
        for i, p in enumerate(portals):
            if p["name"] == portal:
                customChannelNames = p["custom channel names"]
                if customName:
                    customChannelNames.update({chid: customName})
                else:
                    customChannelNames.pop(chid)
                portals[i]["custom channel names"] = customChannelNames
                break
    for g in genreEdits:
        portal = g["portal"]
        chid = g["channel id"]
        customGenre = g["custom genre"]
        for i, p in enumerate(portals):
            if p["name"] == portal:
                customGenres = p["custom genres"]
                if customGenre:
                    customGenres.update({chid: customGenre})
                else:
                    customGenres.pop(chid)
                portals[i]["custom genres"] = customGenres
                break
    savePortals(portals)
    return redirect("/editor", code=302)


@app.route("/player", methods=["GET"])
def player():
    channels = []
    for p in getPortals():
        portalName = p["name"]
        url = p["url"]
        mac = p["mac"]
        proxy = p["proxy"]
        enabledChannels = p["enabled channels"]
        customChannelNames = p["custom channel names"]
        customGenres = p["custom genres"]
        if len(enabledChannels) != 0:
            try:
                token = stb.getToken(url, mac)
                allChannels = stb.getAllChannels(url, mac, token)
                genres = stb.getGenres(url, mac, token)
                for i in allChannels:
                    channelId = i["id"]
                    if channelId in enabledChannels:
                        cmd = i["cmd"]
                        channelName = customChannelNames.get(channelId)
                        if channelName == None:
                            channelName = i["name"]
                        genre = customGenres.get(channelId)
                        if genre == None:
                            genre = genres.get(i["tv_genre_id"])
                        epg = stb.getShortEpg(channelId, url, mac, token)
                        try:
                            now = epg[0]["name"]
                        except:
                            now = "No data"
                        try:
                            nex = epg[1]["name"]
                        except:
                            nex = "No data"
                        query = parse.urlencode(
                            {
                                "portalName": portalName,
                                "url": url,
                                "mac": mac,
                                "cmd": cmd,
                                "proxy": proxy,
                                "format": "mp4",
                            }
                        )
                        link = "http://" + host + "/play?" + query
                        channels.append(
                            {
                                "name": channelName,
                                "genre": genre,
                                "link": link,
                                "now": now,
                                "next": nex,
                            }
                        )
                        channels.sort(key=lambda k: k["name"])
            except:
                print(sys.exc_info()[1])
                pass
    return render_template("player.html", channels=channels)


@app.route("/playlist", methods=["GET"])
def playlist():
    channels = []
    for p in getPortals():
        portalName = p["name"]
        url = p["url"]
        mac = p["mac"]
        proxy = p["proxy"]
        format = p["format"]
        enabledChannels = p["enabled channels"]
        customChannelNames = p["custom channel names"]
        customGenres = p["custom genres"]
        if len(enabledChannels) != 0:
            try:
                token = stb.getToken(url, mac)
                allChannels = stb.getAllChannels(url, mac, token)
                genres = stb.getGenres(url, mac, token)
                for i in allChannels:
                    channelId = i["id"]
                    if channelId in enabledChannels:
                        cmd = i["cmd"]
                        channelName = customChannelNames.get(channelId)
                        if channelName == None:
                            channelName = i["name"]
                        genre = customGenres.get(channelId)
                        if genre == None:
                            genre = genres.get(i["tv_genre_id"])
                        query = parse.urlencode(
                            {
                                "portalName": portalName,
                                "url": url,
                                "mac": mac,
                                "cmd": cmd,
                                "proxy": proxy,
                                "format": format,
                            }
                        )
                        channels.append(
                            '#EXTINF:-1 group-title="'
                            + genre
                            + '",'
                            + channelName
                            + "\n"
                            + "http://"
                            + host
                            + "/play?"
                            + query
                        )
            except:
                print(sys.exc_info()[1])
                pass
    channels.sort(key=lambda k: k.split(",")[1])
    playlist = "#EXTM3U \n"
    playlist = playlist + "\n".join(channels)
    return Response(playlist, mimetype="text/plain")


@app.route("/play", methods=["GET"])
def channel():
    def streamData(link, proxy, format):
        if format == "mp4":
            ffmpegcmd = [
                "ffmpeg",
                "-re",
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
        elif format == "mpegts":
            ffmpegcmd = [
                "ffmpeg",
                "-re",
                "-loglevel",
                "panic",
                "-hide_banner",
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
                "-re",
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
            ffmpeg_sb = subprocess.Popen(
                ffmpegcmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE
            )
            for stdout_line in iter(ffmpeg_sb.stdout.readline, ""):
                yield stdout_line
        finally:
            ffmpeg_sb.terminate()

    url = request.args.get("url")
    mac = request.args.get("mac")
    cmd = request.args.get("cmd")
    proxy = request.args.get("proxy")
    format = request.args.get("format")
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
