# STB-Proxy

Play STB portal streams via m3u player

- Map whichever port you like to the default `8001`
- `HOST` should be the docker host ip + the port you chose
- Mounting `/config` is required if you want your credentials to persist through restarts
- To configure go to the HOST + port in a browser eg 10.0.1.200:8084
- Playlist is available at HOST + port + /playlist eg 10.0.1.200:8084/playlist
- Load HOST + port + /playlist in the m3u player of your choice

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
