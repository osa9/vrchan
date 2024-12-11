import httpx
import base64
import pyotp
from typing import Literal, Any


class VRChatAPI:
    def __init__(
        self,
        username: str,
        password: str,
        cookie_auth: str | None = None,
        cookie_2fa: str | None = None,
        base_url: str | None = None,
        totp_secret: str | None = None,
    ):
        self.username = username
        self.password = password
        self.totp_secret = totp_secret
        self.base_url = base_url or "https://api.vrchat.cloud/api/1"
        self.session = httpx.Client()

        if cookie_auth:
            self.session.cookies.set("auth", cookie_auth, "api.vrchat.cloud", "/")
        if cookie_2fa:
            self.session.cookies.set(
                "twoFactorAuth", cookie_2fa, "api.vrchat.cloud", "/"
            )

    def _filter_none(self, params: dict[str, Any]):
        return {k: v for k, v in params.items() if v is not None}

    def _url(self, path: str):
        return f"{self.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        auto_login: bool = True,
        params: dict[str, Any] | None = None,
        **kwargs,
    ):
        params = self._filter_none(params) if params else None

        res = self.session.request(
            method, self._url(path), follow_redirects=True, params=params, **kwargs
        )

        if res.status_code == httpx.codes.OK:
            return res.json()

        # ログインが必要な場合
        if res.status_code == httpx.codes.UNAUTHORIZED:
            if not auto_login:
                raise Exception("Unauthorized")

            self.login()
            return self._request(method, path, auto_login=False, **kwargs)

        raise Exception(res.json())

    def _get(self, path: str, params: dict[str, Any] | None = None, **kwargs):
        return self._request("GET", path, params=params, **kwargs)

    def _post(self, path: str, params: dict[str, Any] | None = None, **kwargs):
        return self._request("POST", path, params=params, **kwargs)

    def _login(self):
        user = self.get_user(self.username, self.password)
        tfa = user.get("requiresTwoFactorAuth")
        if "totp" in tfa:
            return self.verify_2fa(input("Enter 2FA code: "))
        elif tfa:
            raise Exception(f"Not supported 2FA method: {tfa}")
        return user

    def get_cookies(self):
        res = []
        for cookie in self.session.cookies.jar:
            res.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                }
            )
        return res

    def set_cookies(self, cookies: list[dict]):
        for cookie in cookies:
            self.session.cookies.set(
                cookie["name"], cookie["value"], cookie["domain"], cookie["path"]
            )

    def login(self):
        print(f"Logging in as {self.username}")
        """
        ログインしてユーザー情報を取得する
        """
        basic_auth = base64.urlsafe_b64encode(
            f"{self.username}:{self.password}".encode()
        ).decode()

        response = self._get(
            "/auth/user",
            auto_login=False,
            headers={"Authorization": f"Basic {basic_auth}"},
        )

        # 2FAが必要な時
        tfa = response.get("requiresTwoFactorAuth")
        if not tfa:
            return response

        if "totp" in tfa:
            self.verify_2fa()

        raise Exception(f"Not supported 2FA method: {tfa}")

    def verify_2fa(self, *, code: str | None = None):
        if not code:
            code = pyotp.TOTP(self.totp_secret).now()

        return self._post(
            "/auth/twofactorauth/totp/verify",
            json={"code": code},
            auto_login=False,
        )

    def get_group_instances(self, group_id: str):
        return self._get(f"/groups/{group_id}/instances")

    def get_announcement(self, group_id: str):
        return self._get(f"/groups/{group_id}/announcement")

    def get_posts(
        self,
        group_id: str,
        n: int | None = None,
        offset: int | None = None,
        public_only: bool | None = None,
    ):
        params = {}
        if n:
            params["n"] = n
        if offset:
            params["offset"] = offset
        if public_only:
            params["publicOnly"] = public_only
        return self._get(
            f"/groups/{group_id}/posts",
            params=params,
        )

    def search_world(
        self,
        *,
        search: str | None = None,
        n: int | None = None,
        offset: int | None = None,
        tag: str | None = None,
        sort: Literal[
            "popularity",
            "heat",
            "hotness",
            "trust",
            "shuffle",
            "random",
            "favorites",
        ]
        | None = None,
    ):
        params = {
            "search": search,
            "n": n,
            "offset": offset,
            "sort": sort,
            "tag": tag,
        }
        return self._get("/worlds", params=params)

    def get_info_push(self, include: str, require: str):
        """
        include: user-all
        require: world-category
        """
        params = {
            "include": include,
            "require": require,
        }
        return self._get("/infoPush", params=params)
