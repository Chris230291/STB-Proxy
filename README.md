# STB-Proxy

- Play STB portal streams via m3u player
- Combine multiple portals
- Enable/disable channels individually
- Rename channels
- Set custom genres

# Docker
- Map whichever port you like to the default `8001`
- `HOST` should be the docker hosts ip + the port you chose
- Mounting `/config` is required for settings to persist through restarts
- To configure go to the HOST + port in a browser eg 10.0.1.200:8084
- Playlist is available at HOST + port + /playlist eg 10.0.1.200:8084/playlist

example:
```
docker create \
--name=STB-Proxy \
--restart=always \
-p 8084:8001 \
-e HOST=10.0.1.200:8084 \
-v </host/path>:/config \
chris230291/stb-proxy:latest
```

# Without Docker

- Requires: `python 3` `fastapi` `requests` `uvicorn` `jinja2` `python-multipart` `aiofiles` `ffmpeg`
- Download the repo
- Doubble click `app.py`
- Go to `http://localhost:8001` in a browser and enter Portal URL + MAC
- Load `http://localhost:8001/playlist` in a m3u player, eg VLC
