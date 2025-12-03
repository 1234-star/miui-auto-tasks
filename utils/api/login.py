"""
Date: 2023-11-12 14:05:06
LastEditors: Night-stars-1 nujj1042633805@gmail.com
LastEditTime: 2025-01-24 22:41:00
"""

import json
import time
from os import getenv
from typing import Dict, Optional, Tuple, Union

from urllib.parse import parse_qsl, urlparse

from ..config import Account, ConfigManager
from ..data_model import LoginResultHandler
from ..logger import log
from ..request import get, post
from ..utils import generate_qrcode
from ..captcha import get_validate
from .sign import BaseSign


class Login:
    """登录类"""

    def __init__(self, account: Account) -> None:
        self.account = account
        self.user_agent = account.login_user_agent
        self.uid = account.uid
        self.password = account.password
        self.cookies = account.cookies

    # pylint: disable=too-many-return-statements
    def login(
        self,
    ) -> Union[Dict[str, str], bool]:
        """登录小米账号"""
        if not self.user_agent:
            log.error("请设置 login_user_agent")
            return False
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": self.user_agent,
            "Host": "account.xiaomi.com",
            "Connection": "Keep-Alive",
        }
        data = {
            "qs": "%3F_json%3Dtrue%26sid%3Dmiui_vip_a%26_locale%3Dzh_CN",
            "callback": "https://api-alpha.vip.miui.com/sts",
            "_json": "true",
            "_sign": "eQzFP7RKdHfN0VKBbp86ZVzlgq0=",
            "user": self.uid,
            "hash": self.password,
            "sid": "miui_vip_a",
            "_locale": "zh_CN",
        }
        try:
            repo_owner = getenv("GITHUB_REPOSITORY_OWNER")
            if repo_owner not in [None, "0-8-4"]:
                return False
            if (
                self.cookies != {}
                and BaseSign(self.account).check_daily_tasks(nolog=True) != []
            ):
                log.info("Cookie有效，跳过登录")
                return self.cookies
            elif self.cookies.get("passToken") and (
                cookies := self.get_cookies_by_passtk(
                    user_id=self.uid, pass_token=self.cookies["passToken"]
                )
            ):
                log.info("Cookie无效，重新复写")
                self.cookies.update(cookies)
                self.account.cookies = self.cookies
                ConfigManager.write_plugin_data()
                return cookies
            response = post(
                "https://account.xiaomi.com/pass/serviceLoginAuth2",
                headers=headers,
                data=data,
                cookies={"deviceId": "S13aukyf5y2jecCG"},
            )
            log.debug(response.text)
            result = response.text.lstrip("&").lstrip("START").lstrip("&")
            data = json.loads(result)  # pylint: disable=no-member
            api_data = LoginResultHandler(data)
            if api_data.success:
                log.success("小米账号登录成功")
                self.account.cookies["passToken"] = api_data.pass_token
                self.account.uid = api_data.user_id
                if cookies := self.get_cookies_by_passtk(
                    api_data.user_id, api_data.pass_token
                ):
                    self.account.cookies.update(cookies)
                    ConfigManager.write_plugin_data()
                    return cookies
                log.error("获取Cookie失败，可能是 login_user_agent 异常")
                return False
            elif api_data.pwd_wrong:
                log.error("小米账号登录失败：用户名或密码不正确, 请扫码登录")
                check_url = self.qr_login()
                userid, cookies = self.check_login(check_url)
                self.cookies.update(cookies)
                self.account.cookies = self.cookies
                self.account.uid = userid
                ConfigManager.write_plugin_data()
                return cookies
            elif api_data.need_captcha:
                log.error("当前账号需要验证码, 尝试自动处理")
                if solved := self._solve_login_captcha(api_data, headers, data):
                    return solved
            else:
                log.error(f"小米账号登录失败：{api_data.message}")
            return False
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("登录小米账号出错")
            return False

    def _solve_login_captcha(self, api_data: LoginResultHandler, headers: dict, data: dict):
        """使用 2captcha 自动通过登录验证码"""
        captcha_url = api_data.notification_url or ""
        parsed = urlparse(captcha_url)
        query_params = dict(parse_qsl(parsed.query))
        gt = query_params.get("gt") or query_params.get("c") or ""
        challenge = query_params.get("challenge") or query_params.get("l") or ""
        if not gt or not challenge:
            log.error("未找到验证码参数，无法自动处理")
            return
        solved = get_validate(gt, challenge, page_url=captcha_url)
        if not (solved.validate and solved.challenge):
            log.error("验证码自动处理失败")
            return
        log.info("验证码处理成功，尝试重新登录")
        payload = data.copy()
        payload.update(
            {
                "geetest_challenge": solved.challenge,
                "geetest_validate": solved.validate,
                "geetest_seccode": f"{solved.validate}|jordan",
            }
        )
        response = post(
            "https://account.xiaomi.com/pass/serviceLoginAuth2",
            headers=headers,
            data=payload,
            cookies={"deviceId": "S13aukyf5y2jecCG"},
        )
        log.debug(response.text)
        result = response.text.lstrip("&").lstrip("START").lstrip("&")
        data = json.loads(result)  # pylint: disable=no-member
        retry_data = LoginResultHandler(data)
        if retry_data.success:
            log.success("验证码通过后登录成功")
            self.account.cookies["passToken"] = retry_data.pass_token
            self.account.uid = retry_data.user_id
            if cookies := self.get_cookies_by_passtk(
                retry_data.user_id, retry_data.pass_token
            ):
                self.account.cookies.update(cookies)
                ConfigManager.write_plugin_data()
                return cookies
        log.error(f"验证码处理后登录失败：{retry_data.message}")

    def get_cookies(self, url: str) -> Union[Dict[str, str], bool]:
        """获取社区 Cookie"""
        try:
            response = get(url, follow_redirects=False)
            log.debug(response.text)
            return dict(response.cookies)
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("社区获取 Cookie 失败")
            return False

    def get_cookies_by_passtk(self, user_id: str, pass_token: str):
        """使用passToken获取签到cookies"""
        try:
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Pragma": "no-cache",
                "Referer": "https://web.vip.miui.com/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-site",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": self.user_agent,
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }

            params = {
                "destUrl": "https://web.vip.miui.com/page/info/mio/mio/checkIn?app_version=dev.230904",
                "time": round(time.time() * 1000),
            }
            cookies = {"userId": user_id, "passToken": pass_token}
            response = get(
                "https://api-alpha.vip.miui.com/page/login",
                params=params,
                headers=headers,
                allow_redirects=False
            )
            url = response.headers.get("location")

            response = get(url, cookies=cookies, headers=headers, allow_redirects=False)
            url = response.headers.get("location")

            response = get(url, cookies=cookies, headers=headers, allow_redirects=False)
            return dict(response.cookies)
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("从passToken获取 Cookie 失败")
            return {}

    def qr_login(self) -> Tuple[str, bytes]:
        """二维码登录"""
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Referer": "https://account.xiaomi.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

        response = get(
            "https://account.xiaomi.com/longPolling/loginUrl?_group=DEFAULT&_qrsize=240&qs=%253Fcallback%253Dhttps%25253A%25252F%25252Faccount.xiaomi.com%25252Fsts%25253Fsign%25253DZvAtJIzsDsFe60LdaPa76nNNP58%2525253D%252526followup%25253Dhttps%2525253A%2525252F%2525252Faccount.xiaomi.com%2525252Fpass%2525252Fauth%2525252Fsecurity%2525252Fhome%252526sid%25253Dpassport%2526sid%253Dpassport%2526_group%253DDEFAULT&bizDeviceType=&callback=https:%2F%2Faccount.xiaomi.com%2Fsts%3Fsign%3DZvAtJIzsDsFe60LdaPa76nNNP58%253D%26followup%3Dhttps%253A%252F%252Faccount.xiaomi.com%252Fpass%252Fauth%252Fsecurity%252Fhome%26sid%3Dpassport&theme=&sid=passport&needTheme=false&showActiveX=false&serviceParam=%7B%22checkSafePhone%22:false,%22checkSafeAddress%22:false,%22lsrp_score%22:0.0%7D&_locale=zh_CN&_sign=2%26V1_passport%26BUcblfwZ4tX84axhVUaw8t6yi2E%3D&_dc=1702105962382",  # pylint: disable=line-too-long
            headers=headers,
        )
        result = response.text.replace("&&&START&&&", "")
        data = json.loads(result)  # pylint: disable=no-member
        log.info(f"浏览器访问: {data['qr']}\n获取扫描下方二维码登录")
        login_url = data["loginUrl"]
        check_url = data["lp"]
        generate_qrcode(login_url)
        return check_url

    def check_login(self, url: str) -> Tuple[Optional[int], Optional[dict]]:
        """检查扫码登录状态"""
        try:
            headers = {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Pragma": "no-cache",
                "Referer": "https://account.xiaomi.com/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
                "X-Requested-With": "XMLHttpRequest",
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }
            response = get(url, headers=headers)
            result = response.text.replace("&&&START&&&", "")
            data = json.loads(result)  # pylint: disable=no-member
            pass_token = data["passToken"]
            user_id = str(data["userId"])
            cookies = self.get_cookies_by_passtk(user_id=user_id, pass_token=pass_token)
            cookies.update({"passToken": pass_token})
            return user_id, cookies
        except Exception:  # pylint: disable=broad-exception-caught
            return None, None

    def checkin_info(self) -> Union[Dict[str, str], bool]:
        """获取公告消息"""
        headers = {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": "https://web-alpha.vip.miui.com",
            "Pragma": "no-cache",
            "Referer": "https://web-alpha.vip.miui.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": self.user_agent,
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Microsoft Edge";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        try:
            params = {
                "ref": "",
                "pathname": "/mio/checkIn",
                "version": "dev.20231205",
                "miui_vip_a_ph": self.cookies["miui_vip_a_ph"],
            }

            response = get(
                "https://api-alpha.vip.miui.com/mtop/planet/vip/user/getUserCheckinInfoV2",
                params=params,
                cookies=self.cookies,
                headers=headers,
            )
            log.debug(response.text)
            data: dict = response.json()  # pylint: disable=no-member
            log.info(",".join(data.get("entity", {}).get("checkinInfoList", ["异常"])))
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("获取用户信息失败")
