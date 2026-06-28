"""LiveTrans Voice — 英文→中文翻译服务 (MyMemory API)"""
import urllib.request
import urllib.parse
import json


def translate(text: str, source: str = "en", target: str = "zh-CN") -> str:
    """英文→中文翻译，失败返回原文"""
    try:
        params = urllib.parse.urlencode({
            "q": text[:500],
            "langpair": f"{source}|{target}"
        })
        url = f"https://api.mymemory.translated.net/get?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "LiveTrans/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = data.get("responseData", {}).get("translatedText", "")
            if result:
                return result
    except Exception:
        pass
    return text  # 降级：返回原文
