from logging import error
import requests
from retrying import retry
from urllib.parse import urlparse
import re
import math
import json

@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getUrl(url, proxy=None):
    def parseResponse(url, data):
        java = data.text.replace(' ', '').replace("'", '').replace('+', '')
        pattern = re.search(r'varpattern.*\/(\(http.*)\/;', java).group(1)
        result = re.search(pattern, url)
        protocolIndex = re.search(
            r'this\.portal_protocol.*(\d).*;', java).group(1)
        ipIndex = re.search(r'this\.portal_ip.*(\d).*;', java).group(1)
        pathIndex = re.search(r'this\.portal_path.*(\d).*;', java).group(1)
        protocol = result.group(int(protocolIndex))
        ip = result.group(int(ipIndex))
        path = result.group(int(pathIndex))
        portalPatern = re.search(
            r'this\.ajax_loader=(.*\.php);', java).group(1)
        portal = portalPatern.replace('this.portal_protocol', protocol).replace(
            'this.portal_ip', ip).replace('this.portal_path', path)
        return portal

    url = urlparse(url).scheme + "://" + urlparse(url).netloc
    urls = ["/c/xpcom.common.js", "/client/xpcom.common.js", "/c_/xpcom.common.js",
            "/stalker_portal/c/xpcom.common.js", "/stalker_portal/c_/xpcom.common.js"]

    proxies = {"http": proxy, "https": proxy}
    headers = {"User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)"}

    try:
        for i in urls:
            try:
                response = requests.get(
                    url + i, headers=headers, proxies=proxies)
            except:
                response = None
            if response:
                return parseResponse(url + i, response)
    except Exception as err:
        pass
    raise Exception(f"Error getting Portal URL: {err}")


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getToken(url, mac, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {"User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)"}
    try:
        response = requests.get(
            url + "?type=stb&action=handshake&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()
        token = data["js"]["token"]
        if token:
            getProfile(url, mac, token, proxy)
            return token
    except Exception as err:
        pass
    raise Exception(f"Error getting token: {err}")


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getProfile(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }
    try:
        response = requests.get(
            url + "?type=stb&action=get_profile&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()
        if data:
            return data
    except Exception as err:
        pass
    raise Exception(f"Error getting profile: {err}")

def getExpires(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }
    try:
        response = requests.get(
            url + "?type=account_info&action=get_main_info&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()
        expire = data["js"]["phone"]
        if expire:
            return expire
    except:
        pass
    return "Unknown"


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getAllChannels(url, mac, token, proxy=None, genres=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }
    try:
        response = requests.get(
            url
            + "?type=itv&action=get_all_channels&force_ch_link_check=&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        channels = response.json()["js"]["data"]

        if genres:
            adults_genres = [k for k, v in genres.items() if 'adult' in v.lower() or 'xxx'in v.lower() or 'porn' in v.lower()]
            if adults_genres:
                try: 
                    for value in adults_genres:
                        for numbers in range(50):
                            response = requests.get(
                            url
                            + f'?type=itv&action=get_ordered_list&genre={value}&p={numbers}&JsHttpRequest=1-xml',
                            cookies=cookies,
                            headers=headers,
                            proxies=proxies
                            )
                            if response.json()["js"]["data"]:
                                adults = response.json()["js"]["data"]
                                channels += adults
                except Exception as err:
                    print(f"New Error Ocurred when getting Adult Playlist: {err}")
                finally:
                    pass  

        if channels:
            return channels
    except Exception as err:
        pass
    raise Exception(f"Error getting channels: {err}")


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getGenres(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }
    try:
        response = requests.get(
            url + "?action=get_genres&type=itv&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        genreData = response.json()["js"]
        genres = {}
        for i in genreData:
            gid = i["id"]
            name = i["title"]
            genres[gid] = name
        if genres:
            return genres
            
    except Exception as err:
        pass
    raise Exception(f"Error getting genres: {err}")

@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getLink(url, mac, token, cmd, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "Authorization": "Bearer " + token,
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Host": "magnum-ott.net",
    }
    try:
        response = requests.get(
            url + "?type=itv&action=create_link&cmd=" + cmd +
            "&series=0&forced_storage=false&disable_ad=false&download=false&force_ch_link_check=false&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()
        link = data["js"]["cmd"].split()[-1]
        if link:
            return link
    except Exception as err:
        pass
    raise Exception(f"Error getting link: {err}")

@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getEpg(url, mac, token, period, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }
    try:
        response = requests.get(
            url + "?type=itv&action=get_epg_info&period=" +
            str(period) + "&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()["js"]["data"]
        if data:
            return data
    except Exception as err:
        pass
    raise Exception(f"Error data EPG not found: {err}")


def getVods(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }
    try:
        response = requests.get(
            url + "?type=vod&action=get_ordered_list&p=1&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()["js"]
        pages = math.ceil(int(data["total_items"]) /
                          int(data["max_page_items"]))
        vods = response.json()["js"]["data"]

        for i in range(2, pages):
            response = requests.get(
                url + "?type=vod&action=get_ordered_list&p=" +
                str(i) + "&JsHttpRequest=1-xml",
                cookies=cookies,
                headers=headers,
                proxies=proxies
            )
            vods = vods + response.json()["js"]["data"]
        if vods:
            return vods
    except Exception as err:
        pass
    raise Exception(f"Error VOD(Movies) data not found: {err}")


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getVodLink(url, mac, token, cmd, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }
    try:
        response = requests.get(
            url + "?type=vod&action=create_link&cmd=" + cmd + "&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()
        link = data["js"]["cmd"].split()[-1]
        if link:
            return link
    except Exception as err:
        pass
    raise Exception(f"Error VOD link: {err}")


def getSeries(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }
    try:
        response = requests.get(
            url + "?type=series&action=get_ordered_list&p=1&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()["js"]
        if data:
            return data
    except Exception as err:
        pass
    raise Exception(f"Error VOD(TVShows) data not found: {err}")


def test(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
        "X-User-Agent": "Model: MAG250; Link: WiFi",
    }
    try:
        response = requests.get(
            url + "?type=series&action=get_ordered_list&movie_id=2198%3A1&category=2198:1&genre=*&season_id=0&episode_id=0&force_ch_link_check=&from_ch_id=0&fav=0&sortby=added&hd=0&not_ended=0&p=1&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()["js"]
        if data:
            return data
    except Exception as err:
        pass
    raise Exception(f"Error VOD data not found: {err}")
