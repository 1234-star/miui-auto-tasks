"""
Date: 2023-11-13 19:55:22
LastEditors: Night-stars-1 nujj1042633805@gmail.com
LastEditTime: 2025-02-11 00:59:19
"""

import json
import time
from traceback import print_exc

from jsonpath_ng import parse
from jsonpath_ng.exceptions import JsonPathParserError

from .config import ConfigManager
from .data_model import GeetestResult
from .logger import log
from .request import request

_conf = ConfigManager.data_obj


def find_key(data: dict, key: str):
    """递归查找字典中的key"""
    for dkey, dvalue in data.items():
        if dkey == key:
            return dvalue
        if isinstance(dvalue, dict):
            find_key(dvalue, key)
    return None


def get_validate_other(
    gt: str, challenge: str, result: str
) -> GeetestResult:  # pylint: disable=invalid-name
    """获取人机验证结果"""
    try:
        validate = ""
        if _conf.preference.get_geetest_url:
            params = _conf.preference.get_geetest_params.copy()
            params = json.loads(
                json.dumps(params)
                .replace("{gt}", gt)
                .replace("{challenge}", challenge)
                .replace("{result}", str(result))
            )
            data = _conf.preference.get_geetest_data.copy()
            data = json.loads(
                json.dumps(data)
                .replace("{gt}", gt)
                .replace("{challenge}", challenge)
                .replace("{result}", str(result))
            )
            for i in range(_conf.preference.get_geetest_try_count):
                log.info(f"第{i}次获取结果")
                response = request(
                    _conf.preference.get_geetest_method,
                    _conf.preference.get_geetest_url,
                    params=params,
                    json=data,
                )
                log.debug(response.text)
                result = response.json()
                geetest_validate_expr = parse(
                    _conf.preference.get_geetest_validate_path
                )
                geetest_validate_match = geetest_validate_expr.find(result)
                if len(geetest_validate_match) > 0:
                    validate = geetest_validate_match[0].value
                geetest_challenge_expr = parse(
                    _conf.preference.get_geetest_challenge_path
                )
                geetest_challenge_match = geetest_challenge_expr.find(result)
                if len(geetest_challenge_match) > 0:
                    challenge = geetest_challenge_match[0].value
                if validate and challenge:
                    return GeetestResult(challenge=challenge, validate=validate)
                time.sleep(1)
            return GeetestResult(challenge="", validate="")
        else:
            return GeetestResult(challenge="", validate="")
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("获取人机验证结果异常")
        return GeetestResult(challenge="", validate="")


def _solve_geetest_by_2captcha(
    gt: str, challenge: str, page_url: str
) -> GeetestResult:
    """使用 2captcha 解决极验验证"""
    api_key = _conf.preference.two_captcha_api_key
    if not api_key:
        return GeetestResult(challenge="", validate="")
    try:
        payload = {
            "key": api_key,
            "method": "geetest",
            "gt": gt,
            "challenge": challenge,
            "pageurl": page_url,
            "json": 1,
        }
        response = request(
            "post",
            "https://2captcha.com/in.php",
            data=payload,
        )
        log.debug(response.text)
        submit_result = response.json()
        if submit_result.get("status") != 1:
            log.error(f"2captcha提交失败: {submit_result.get('request')}")
            return GeetestResult(challenge="", validate="")
        captcha_id = str(submit_result.get("request"))
        for _ in range(_conf.preference.get_geetest_try_count):
            time.sleep(5)
            result_resp = request(
                "get",
                "https://2captcha.com/res.php",
                params={"key": api_key, "action": "get", "id": captcha_id, "json": 1},
            )
            log.debug(result_resp.text)
            result_data = result_resp.json()
            if result_data.get("status") == 1:
                req = result_data.get("request")
                if isinstance(req, str):
                    try:
                        req = json.loads(req)
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass
                if isinstance(req, dict):
                    validate = req.get("validate", "")
                    solved_challenge = req.get("challenge", challenge)
                    if validate:
                        return GeetestResult(
                            challenge=solved_challenge, validate=validate
                        )
            elif result_data.get("request") != "CAPCHA_NOT_READY":
                log.error(f"2captcha返回错误: {result_data.get('request')}")
                break
        return GeetestResult(challenge="", validate="")
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("调用2captcha解决极验失败")
        return GeetestResult(challenge="", validate="")


def get_validate(
    gt: str, challenge: str, page_url: str | None = None
) -> GeetestResult:  # pylint: disable=invalid-name
    """创建人机验证并结果"""
    try:
        validate = ""
        result = ""
        page_url = (
            page_url
            or _conf.preference.two_captcha_pageurl
            or "https://account.xiaomi.com"
        )
        if _conf.preference.two_captcha_api_key:
            solved = _solve_geetest_by_2captcha(gt, challenge, page_url)
            if solved.validate and solved.challenge:
                return solved
        if _conf.preference.geetest_url:
            params = _conf.preference.geetest_params.copy()
            params = json.loads(
                json.dumps(params).replace("{gt}", gt).replace("{challenge}", challenge)
            )
            data = _conf.preference.geetest_data.copy()
            data = json.loads(
                json.dumps(data).replace("{gt}", gt).replace("{challenge}", challenge)
            )
            response = request(
                _conf.preference.geetest_method,
                _conf.preference.geetest_url,
                params=params,
                json=data,
            )
            log.debug(response.text)
            result = response.json()
            try:
                geetest_validate_expr = parse(_conf.preference.geetest_validate_path)
                geetest_validate_match = geetest_validate_expr.find(result)
                if len(geetest_validate_match) > 0:
                    validate = geetest_validate_match[0].value
                geetest_challenge_expr = parse(_conf.preference.geetest_challenge_path)
                geetest_challenge_match = geetest_challenge_expr.find(result)
                if len(geetest_challenge_match) > 0:
                    challenge = geetest_challenge_match[0].value
                geetest_result_expr = parse(_conf.preference.geetest_result_path)
                geetest_result_match = geetest_result_expr.find(result)
                if len(geetest_result_match) > 0:
                    result = geetest_result_match[0].value
            except JsonPathParserError:
                print_exc()
            if validate and challenge:
                return GeetestResult(challenge=challenge, validate=validate)
            else:
                return get_validate_other(gt=gt, challenge=challenge, result=result)
        else:
            return GeetestResult(challenge="", validate="")
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("获取人机验证结果异常")
        return GeetestResult(challenge="", validate="")
