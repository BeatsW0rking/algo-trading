./curl_chrome116 --rate 10/s https://truthsocial.com/api/v1/accounts/107780257626128497/statuses?exclude_replies=true&with_muted=true&limit=1

./curl_chrome116 -X POST \
-F 'client_name=Test Application x' \
-F 'redirect_uris=urn:ietf:wg:oauth:2.0:oob' \
-F 'scopes=read push' \
-F 'website=https://myappx.example' \
https://truthsocial.com/api/v1/apps

{"id":"11200545","name":"Test Application","website":"https://myapp.example","redirect_uri":"urn:ietf:wg:oauth:2.0:oob","client_id":"gSOXMC9F3aTum2BRollFharrJwO2DAhdW02wVoomzrk","client_secret":"o7MiHgEdo4VHHYslWxLP5jb9VVvWcTVZDc42KtQ-fps","vapid_key":"BB90KucI3YPKandew0b-kA4RQkBJMkRKA9_oIpRlhJjd024ayzmcqCzQ8AmZX1qXFkuqea2YRymHI9Atuc4tmf4="}

{"id":"11200546","name":"Test Application x","website":"https://myappx.example","redirect_uri":"urn:ietf:wg:oauth:2.0:oob","client_id":"oZCjB9ZJboRytSKvNHpLfqsre_L6pC0ZBOXO71pf2Zk","client_secret":"UI8NIuYBnduOxv_BqiQiucuUyGW5Q5FOaqfeoO1erDE","vapid_key":"BB90KucI3YPKandew0b-kA4RQkBJMkRKA9_oIpRlhJjd024ayzmcqCzQ8AmZX1qXFkuqea2YRymHI9Atuc4tmf4="}

./curl_chrome116 -X POST \
-F 'client_id=oZCjB9ZJboRytSKvNHpLfqsre_L6pC0ZBOXO71pf2Zk' \
-F 'client_secret=UI8NIuYBnduOxv_BqiQiucuUyGW5Q5FOaqfeoO1erDE' \
-F 'redirect_uri=urn:ietf:wg:oauth:2.0:oob' \
-F 'grant_type=client_credentials' \
https://truthsocial.com/oauth/token

-F 'grant_type=client_credentials' \
-F 'grant_type=authorization_code' \


./curl_chrome116 https://truthsocial.com/.well-known/oauth-authorization-server

=========== Experimantal =  ===============
./curl_chrome116 -X POST \
-F 'client_id=oZCjB9ZJboRytSKvNHpLfqsre_L6pC0ZBOXO71pf2Zk' \
-F 'client_secret=UI8NIuYBnduOxv_BqiQiucuUyGW5Q5FOaqfeoO1erDE' \
-F 'redirect_uri=urn:ietf:wg:oauth:2.0:oob' \
-F 'grant_type=client_credentials' \
https://truthsocial.com/api/v1/push/subscription

{
  "client_id": "9X1Fdd-pxNsAgEDNi_SfhJWi8T-vLuV2WVzKIbkTCw4",
  "client_secret": "ozF8jzI4968oTKFkEnsBC-UbLPCdrSv0MkXGQu2o_-M",
  "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
  "grant_type": "password",
  "scope": "read write follow push",
  "username": "beatsWorking",
  "password": "&mB4NCJ6rBcHXhF"
}
'authorization=Bearer xjLfg_7GMbXNHyeH2pT7p2FiY5mi5mskoBkeEYKZCe4'

"urls": {
        "streaming_api": "wss://truthsocial.com"
    },
"access_token": "fKS0Wb0s7-RQiBaXmgWgCbXbs4jU9GafFVovs44F81U"

===================================================
-F 'client_id=9X1Fdd-pxNsAgEDNi_SfhJWi8T-vLuV2WVzKIbkTCw4' \
-F 'client_secret=ozF8jzI4968oTKFkEnsBC-UbLPCdrSv0MkXGQu2o_-M' \
-F 'redirect_uri=urn:ietf:wg:oauth:2.0:oob' \
-F 'grant_type=password' \
-F 'scopes=read write follow push' \
-F 'username=beatsWorking' \
-F 'password=&mB4NCJ6rBcHXhF' \

./curl_chrome116 -X POST \
-H 'Content-Type: application/json' \
--data '{"client_id": "9X1Fdd-pxNsAgEDNi_SfhJWi8T-vLuV2WVzKIbkTCw4","client_secret": "ozF8jzI4968oTKFkEnsBC-UbLPCdrSv0MkXGQu2o_-M","redirect_uri": "urn:ietf:wg:oauth:2.0:oob","grant_type": "password","scope": "read write follow push","username": "beatsWorking","password": "&mB4NCJ6rBcHXhF"}' \
https://truthsocial.com/oauth/token


./curl_chrome116 -X POST \
-H 'authorization: Bearer xjLfg_7GMbXNHyeH2pT7p2FiY5mi5mskoBkeEYKZCe4' \
https://truthsocial.com/api/v1/push/subscription