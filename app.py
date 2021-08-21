import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import json
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.responses import PlainTextResponse
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
from pathlib import Path
from urllib.parse import urlparse

app = FastAPI()
base_path = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(base_path / "templates"))
portal = "www.example.com"
mac = "00:00:00:00:00:00"
path = "/portal.php"
token = "1234"

if os.getenv('HOST'):
    host = os.getenv('HOST')
else:
    host = "localhost:8001"

if os.getenv('CONFIG'):
    config_file = os.getenv('CONFIG')
else:
    config_file = str(base_path) + "/config.json"

def getconfig():
    global portal, mac, path
    if os.path.isfile(config_file):
        with open(config_file) as f:
            data = json.load(f)
            portal = data['portal']
            mac = data['mac']
            path = data['path']
    else:
        print ("No config found. Creating one.")
        with open(config_file, 'w') as f:
            data = {"portal": "www.example.com", "mac": "00:00:00:00:00:00", "path": "/portal.php"}
            json.dump(data, f)
        with open(config_file) as f:
            data = json.load(f)
            portal = data['portal']
            mac = data['mac']
            path = data['path']

def gettoken():
    cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
    headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)'}
    with requests.Session() as s:
        retries = Retry(
        total=5,
        backoff_factor=0.2,
        status_forcelist=[500, 502, 503, 504]),
        allowed_methods = frozenset(['GET', 'POST'])
        s.mount('http://', HTTPAdapter(max_retries=retries))
        s.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            response = s.post(portal + path + '?type=stb&action=handshake&JsHttpRequest=1-xml', cookies=cookies, headers=headers)
            data = response.json()
            token = data['js']['token']
        except:
            token = None
    return token

def getprofile():
    cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
    headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
    with requests.Session() as s:
        retries = Retry(
        total=5,
        backoff_factor=0.2,
        status_forcelist=[500, 502, 503, 504]),
        allowed_methods = frozenset(['GET', 'POST'])
        s.mount('http://', HTTPAdapter(max_retries=retries))
        s.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            response = s.post(portal + path + '?type=stb&action=get_profile&JsHttpRequest=1-xml', cookies=cookies, headers=headers)
            data = response.json()
        except:
            data = None
    return data

def getinfo():
    cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
    headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
    with requests.Session() as s:
        retries = Retry(
        total=5,
        backoff_factor=0.2,
        status_forcelist=[500, 502, 503, 504]),
        allowed_methods = frozenset(['GET', 'POST'])
        s.mount('http://', HTTPAdapter(max_retries=retries))
        s.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            response = s.post(portal + path + '?type=account_info&action=get_main_info&JsHttpRequest=1-xml', cookies=cookies, headers=headers)
            data = response.json()
        except:
            data = None
    return data

def getgenres():
    cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
    headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
    with requests.Session() as s:
        retries = Retry(
        total=5,
        backoff_factor=0.2,
        status_forcelist=[500, 502, 503, 504]),
        allowed_methods = frozenset(['GET', 'POST'])
        s.mount('http://', HTTPAdapter(max_retries=retries))
        s.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            response = s.post(portal + path + '?action=get_genres&type=itv&JsHttpRequest=1-xml', cookies=cookies, headers=headers)
            data = response.json()['js']
            genres = {}
            for i in data:
                gid = i['id']
                name = i['title']
                genres[gid] = name
        except:
            genres = None
    return genres

def makeplaylist():
    cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
    headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
    with requests.Session() as s:
        retries = Retry(
        total=5,
        backoff_factor=0.2,
        status_forcelist=[500, 502, 503, 504]),
        allowed_methods = frozenset(['GET', 'POST'])
        s.mount('http://', HTTPAdapter(max_retries=retries))
        s.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            response = s.post(portal + path + '?type=itv&action=get_all_channels&force_ch_link_check=&JsHttpRequest=1-xml', cookies=cookies, headers=headers)
            data = response.json()['js']['data']
            channels = []
            for i in data:
                chid = i['id']
                name = i['name']
                channels.append('#EXTINF:-1,' + name + '\n' + 'http://' + host + '/channel/' + chid)
            playlist = '#EXTM3U \n'
            playlist = playlist + "\n".join(channels)
        except:
            playlist = None
    return playlist

def getlink(channel):
    cookies = {'mac': mac, 'stb_lang': 'en', 'timezone': 'Europe/London'}
    headers = {'User-Agent': 'Mozilla/5.0 (QtEmbedded; U; Linux; C)', 'Authorization': 'Bearer ' + token}
    with requests.Session() as s:
        retries = Retry(
        total=5,
        backoff_factor=0.2,
        status_forcelist=[500, 502, 503, 504]),
        allowed_methods = frozenset(['GET', 'POST'])
        s.mount('http://', HTTPAdapter(max_retries=retries))
        s.mount('https://', HTTPAdapter(max_retries=retries))
        try:
            response = s.post(portal + path + '?type=itv&action=create_link&cmd=http://localhost/ch/' + str(channel) + '&JsHttpRequest=1-xml', cookies=cookies, headers=headers)
            data = response.json()
            link = data['js']['cmd'].split()[-1]
        except:
            link = None
    return link

@app.get('/', response_class=HTMLResponse)
def config(request: Request):
    getconfig()
    return templates.TemplateResponse('config.html', {'request': request, 'portal': portal, 'mac': mac})

@app.post("/submit")
def submit(request: Request, portal: str = Form(...), mac: str = Form (...)):
    portal = urlparse(portal).scheme + "://" + urlparse(portal).netloc
    with requests.Session() as s:
            retries = Retry(
            total=5,
            backoff_factor=0.2,
            status_forcelist=[500, 502, 503, 504]),
            allowed_methods = frozenset(['GET', 'POST'])
            s.mount('http://', HTTPAdapter(max_retries=retries))
            s.mount('https://', HTTPAdapter(max_retries=retries))
            try:
                response = s.get(portal + "/c/")
            except:
                response = None
    if response:
        path = "/portal.php"
    else:
        path = "/stalker_portal/server/load.php"
    with open(config_file, 'w') as f:
        data = {"portal": portal, "mac": mac, "path": path}
        json.dump(data, f)
    global token
    getconfig()
    token = gettoken()
    if token and getprofile() and getinfo():
        html = '''
            <!DOCTYPE html>
            <html>
            <body onload="myFunction();">
            <script>
            function myFunction() {
              alert("Success!");
            }
            </script>
            </body>
            </html>
            '''
    else:
        html = '''
            <!DOCTYPE html>
            <html>
            <body onload="myFunction();">
            <script>
            function myFunction() {
              alert("Unable to connect");
            }
            </script>
            </body>
            </html>
            '''
    return HTMLResponse(content=html)

@app.get('/playlist')
def playlist():
    global token
    getconfig()
    if token and getprofile() and getinfo():
        return PlainTextResponse(makeplaylist())
    else:
        token = gettoken()
        if token and getprofile() and getinfo():
            return PlainTextResponse(makeplaylist())
        else:
            print("Bad credentials")

@app.get('/channel/{chid}')
def channel(chid):
    global token
    getconfig()
    if token and getprofile() and getinfo():
        return RedirectResponse(getlink(chid))
    else:
        token = gettoken()
        if token and getprofile() and getinfo():
            return RedirectResponse(getlink(chid))
        else:
            print("Bad credentials")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")
