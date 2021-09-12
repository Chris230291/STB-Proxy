import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import json
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.responses import PlainTextResponse
from fastapi.responses import HTMLResponse
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path
from urllib.parse import urlparse
import subprocess

app = FastAPI()
base_path = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(base_path / "templates"))
app.mount("/static", StaticFiles(directory=str(base_path) + "/static"), name="static")

if os.getenv('HOST'):
    host = os.getenv('HOST')
else:
    host = "localhost:8001"

if os.getenv('CONFIG'):
    config_file = os.getenv('CONFIG')
else:
    config_file = str(base_path) + "/config.json"

session = requests.Session()
retries = Retry(total=5, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504], allowed_methods=frozenset(['GET', 'POST']))
session.mount('http://', HTTPAdapter(max_retries=retries))
session.mount('https://', HTTPAdapter(max_retries=retries))

def getPortals():
    try:
        with open(config_file) as f:
            data = json.load(f)
            portals = data['portals']
            portals.sort(key = lambda k: k['name'])
    except:
        portals = []
    return portals

def getToken(url, mac):
    cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
    headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)'}
    response = session.post(url + '?type=stb&action=handshake&JsHttpRequest=1-xml', cookies=cookies, headers=headers)
    data = response.json()
    token = data['js']['token']
    getProfile(url, mac, token)
    return token

def getProfile(url, mac, token):
    cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
    headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
    response = session.post(url + '?type=stb&action=get_profile&JsHttpRequest=1-xml', cookies=cookies, headers=headers)
    data = response.json()
    return data

def getExpires(url, mac, token):
    cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
    headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
    response = session.post(url + '?type=account_info&action=get_main_info&JsHttpRequest=1-xml', cookies=cookies, headers=headers)
    data = response.json()
    expire = data['js']['phone']
    return expire

@app.get('/', response_class=HTMLResponse)
def home():
    return RedirectResponse('/portals', status_code=302)

@app.get('/portals', response_class=HTMLResponse)
def portals(request: Request):
    names = []
    masterBlacklist = "^((?=[a-zA-Z0-9_-]+).)*$"
    blacklists = []
    portals = getPortals()
    if portals and len(portals) > 0:
        for i in portals:
            names.append(i['name'])
        #^((?!^word1$|^word2$)(?=[a-zA-Z0-9_-]+).)*$
        masterBlacklist = "^((?!^" + ('$|^'.join(names)) + "$)(?=[a-zA-Z0-9_-]+).)*$"
        for i in portals:
            inames = names.copy()
            iname = i['name']
            inames.remove(iname)
            blacklist = "^((?!^" + ('$|^'.join(inames)) + "$)(?=[a-zA-Z0-9_-]+).)*$"
            blacklists.append(blacklist)
    return templates.TemplateResponse('portals.html', {'request': request, 'portals': portals, 'masterBlacklist': masterBlacklist, 'blacklists': blacklists})

@app.post("/portal/add")
def add(request: Request, name: str = Form(...), url: str = Form(...), mac: str = Form (...)):
    url = urlparse(url).scheme + "://" + urlparse(url).netloc
    try:
        response = session.get(url + "/c/")
    except:
        response = None
    if response:
        url = url + "/portal.php"
    else:
        url = url + "/stalker_portal/server/load.php"

    try:
        with open(config_file) as f:
            data = json.load(f)
            portals = data['portals']
    except:
        data = {}
        portals = []
    token = getToken(url, mac)
    with open(config_file, 'w') as f:
        portals.append({"name":name, "url":url, "mac":mac, "expires":getExpires(url, mac, token), "enabled channels":[], "custom channel names":{}, "custom genres":{}})
        data['portals'] = portals
        json.dump(data, f, indent=4)

    return RedirectResponse('/portals', status_code=302)

@app.post("/portal/edit")
def edit(request: Request, oname: str = Form(...), name: str = Form(...), url: str = Form(...), mac: str = Form (...)):
    url = urlparse(url).scheme + "://" + urlparse(url).netloc
    try:
        response = session.get(url + "/c/")
    except:
        response = None
    if response:
        url = url + "/portal.php"
    else:
        url = url + "/stalker_portal/server/load.php"
    
    with open(config_file) as f:
        data = json.load(f)
        portals = data['portals']

    for i in range(len(portals)):
        if portals[i]["name"] == oname:
            portals[i]['name'] = name
            portals[i]['url'] = url
            portals[i]['mac'] = mac
            token = getToken(url, mac)
            portals[i]['expires'] = getExpires(url, mac, token)
            break

    with open(config_file, 'w') as f:
        data['portals'] = portals
        json.dump(data, f, indent=4)

    return RedirectResponse('/portals', status_code=302)

@app.post("/portal/remove")
def remove(request: Request, name: str = Form(...)):
    with open(config_file) as f:
        data = json.load(f)
        portals = data['portals']
    for i in range(len(portals)):
        if portals[i]["name"] == name:
            portals.pop(i)
            break
    with open(config_file, 'w') as f:
        data['portals'] = portals
        json.dump(data, f, indent=4)
    return RedirectResponse('/portals', status_code=302)

@app.get('/editor', response_class=HTMLResponse)
def editor(request: Request):
    channels = []
    portals = getPortals()
    if len(portals) > 0:
        for p in getPortals():
            portalName = p['name']
            url = p['url']
            mac = p['mac']
            token = getToken(url, mac)
            enabledChannels = p['enabled channels']
            customChannelNames = p['custom channel names']
            customGenres = p['custom genres']
            cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
            headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
            channelsData = session.post(url + '?type=itv&action=get_all_channels&force_ch_link_check=&JsHttpRequest=1-xml', cookies=cookies, headers=headers).json()['js']['data']
            genresData = session.post(url + '?action=get_genres&type=itv&JsHttpRequest=1-xml', cookies=cookies, headers=headers).json()['js']
            genres = {}
            for i in genresData:
                gid = i['id']
                name = i['title']
                genres[gid] = name
            for i in channelsData:
                channelId = i['id']
                channelName = i['name']
                genre = genres.get(i['tv_genre_id'])
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
                channels.append({'enabled': enabled, 'channelName':channelName, 'customChannelName':customChannelName, 'genre':genre, 'customGenre':customGenre, 'channelId':channelId, 'portalName':portalName})
        channels.sort(key = lambda k: (-k['enabled'], k['channelName']))
    return templates.TemplateResponse('editor.html', {'request': request, 'channels': channels})

@app.post("/editor/save")
def save(request: Request, enabledEdits: str = Form(...), nameEdits: str = Form(...), genreEdits: str = Form(...)):
    enabledEdits = json.loads(enabledEdits)
    nameEdits = json.loads(nameEdits)
    genreEdits = json.loads(genreEdits)
    with open(config_file) as f:
        data = json.load(f)
        portals = data['portals']

    for e in enabledEdits:
        portal = e['portal']
        chid = e['channel id']
        enabled = e['enabled']
        for i, p in enumerate(portals):
            if p['name'] == portal:
                enabledChannels = p['enabled channels']
                if enabled:
                    enabledChannels.append(chid)
                else:
                    enabledChannels.remove(chid)
                enabledChannels = list(set(enabledChannels))
                portals[i]['enabled channels'] = enabledChannels
                break

    for n in nameEdits:
        portal = n['portal']
        chid = n['channel id']
        customName = n['custom name']
        for i, p in enumerate(portals):
            if p['name'] == portal:
                customChannelNames = p['custom channel names']
                if customName:
                    customChannelNames.update({chid : customName})
                else:
                    customChannelNames.pop(chid)
                portals[i]['custom channel names'] = customChannelNames
                break

    for g in genreEdits:
        portal = g['portal']
        chid = g['channel id']
        customGenre = g['custom genre']
        for i, p in enumerate(portals):
            if p ['name'] == portal:
                customGenres = p['custom genres']
                if customGenre:
                    customGenres.update({chid : customGenre})
                else:
                    customGenres.pop(chid)
                portals[i]['custom genres'] = customGenres
                break

    with open(config_file, 'w') as f:
        data['portals'] = portals
        json.dump(data, f, indent=4)
    return RedirectResponse('/editor', status_code=302)

@app.get('/player', response_class=HTMLResponse)
def player(request: Request):
    channels = []
    for p in getPortals():
        portalName = p['name']
        url = p['url']
        mac = p['mac']
        token = getToken(url, mac)
        enabledChannels = p['enabled channels']
        customChannelNames = p['custom channel names']
        customGenres = p['custom genres']
        cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
        headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
        if len(enabledChannels) != 0:
            channelsData = session.post(url + '?type=itv&action=get_all_channels&force_ch_link_check=&JsHttpRequest=1-xml', cookies=cookies, headers=headers).json()['js']['data']
            genresData = session.post(url + '?action=get_genres&type=itv&JsHttpRequest=1-xml', cookies=cookies, headers=headers).json()['js']
            genres = {}
            for i in genresData:
                gid = i['id']
                name = i['title']
                genres[gid] = name
            for i in channelsData:
                channelId = i['id']
                if channelId in enabledChannels:
                    channelName = customChannelNames.get(channelId)
                    if channelName == None:
                        channelName = i['name']
                    genre = customGenres.get(channelId)
                    if genre == None:
                        genre = genres.get(i['tv_genre_id'])
                    epg = session.post(url + '?type=itv&action=get_short_epg&ch_id=' + str(channelId) + '&size=10&JsHttpRequest=1-xml', cookies=cookies, headers=headers).json()['js']
                    try:
                        now = epg[0]['name']
                    except:
                        now = "No data"
                    try:
                        nex = epg[1]['name']
                    except:
                        nex = "No data"
                    link = 'http://' + host + '/stream/' + portalName + '/' + channelId
                    channels.append({"name":channelName, "genre":genre, "link":link, "now":now, "next":nex})
                    channels.sort(key = lambda k: k['name'])
    return templates.TemplateResponse('player.html', {'request': request, 'channels': channels})

@app.get('/playlist')
def playlist():
    channels = []
    for p in getPortals():
        portalName = p['name']
        url = p['url']
        mac = p['mac']
        token = getToken(url, mac)
        enabledChannels = p['enabled channels']
        customChannelNames = p['custom channel names']
        customGenres = p['custom genres']
        cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
        headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
        if len(enabledChannels) != 0:
            channelsData = session.post(url + '?type=itv&action=get_all_channels&force_ch_link_check=&JsHttpRequest=1-xml', cookies=cookies, headers=headers).json()['js']['data']
            genresData = session.post(url + '?action=get_genres&type=itv&JsHttpRequest=1-xml', cookies=cookies, headers=headers).json()['js']
            genres = {}
            for i in genresData:
                gid = i['id']
                name = i['title']
                genres[gid] = name
            for i in channelsData:
                channelId = i['id']
                if channelId in enabledChannels:
                    channelName = customChannelNames.get(channelId)
                    if channelName == None:
                        channelName = i['name']
                    genre = customGenres.get(channelId)
                    if genre == None:
                        genre = genres.get(i['tv_genre_id'])
                    channels.append('#EXTINF:-1 group-title="' + genre + '",' + channelName + '\n' + 'http://' + host + "/channel/" + portalName + "/" + channelId)
    channels.sort(key = lambda k: k.split(',')[1])
    playlist = '#EXTM3U \n'
    playlist = playlist + "\n".join(channels)
    return PlainTextResponse(playlist)

@app.get('/channel/{portalName}/{channelId}')
def channel(portalName, channelId):
    for p in getPortals():
        if p['name'] == portalName:
            url = p['url']
            mac = p['mac']
            break
    token = getToken(url, mac)
    cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
    headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
    response = session.post(url + '?type=itv&action=create_link&cmd=http://localhost/ch/' + str(channelId) + '&JsHttpRequest=1-xml', cookies=cookies, headers=headers)
    data = response.json()
    link = data['js']['cmd'].split()[-1]
    return RedirectResponse(link)

@app.get('/stream/{portalName}/{channelId}')
def stream(portalName, channelId):
    def streamData(link):
        ffmpegcmd = [
            'ffmpeg',
            '-re',
            '-loglevel', 'panic', '-hide_banner',
            '-i', link,
            '-vcodec', 'copy',
            '-f', 'mp4',
            '-movflags', 'frag_keyframe+empty_moov',
            '-reconnect_at_eof', '1',
            '-reconnect_streamed', '1',
            '-reconnect_on_network_error', '1',
            '-reconnect_on_http_error', '4xx,5xx',
            'pipe:'
        ]

        ffmpeg_sb = subprocess.Popen(ffmpegcmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)

        try:
            for stdout_line in iter(ffmpeg_sb.stdout.readline, ""):
                yield stdout_line
        except:
            ffmpeg_sb.terminate()

    for p in getPortals():
        if p['name'] == portalName:
            url = p['url']
            mac = p['mac']
            break
    token = getToken(url, mac)
    cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
    headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
    response = session.post(url + '?type=itv&action=create_link&cmd=http://localhost/ch/' + str(channelId) + '&JsHttpRequest=1-xml', cookies=cookies, headers=headers)
    data = response.json()
    link = data['js']['cmd'].split()[-1]
    return StreamingResponse(streamData(link), media_type="video/mp4")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")
