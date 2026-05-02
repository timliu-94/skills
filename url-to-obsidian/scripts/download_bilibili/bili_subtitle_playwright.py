import asyncio
import argparse
import json
import re
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, Response


SUBTITLE_BUTTON_SELECTOR = ".bpx-player-ctrl-subtitle-result"
SUBTITLE_LANGUAGE_SELECTOR = ".bpx-player-ctrl-subtitle-language-item-text"


def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:120] or "bilibili_subtitle"


def parse_cookie_string(cookie_string: str) -> list[dict]:
    """
    将 Chrome 复制出来的 Cookie 字符串转成 Playwright 可注入格式。
    不要包含开头的 Cookie:，也不要加中文引号。
    """
    cookie_string = cookie_string.strip().strip("“”\"'")

    cookies = []
    for item in cookie_string.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue

        name, value = item.split("=", 1)
        cookies.append(
            {
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".bilibili.com",
                "path": "/",
            }
        )

    return cookies


def is_bilibili_subtitle_json(data: dict) -> bool:
    """
    判断是否为 B 站字幕 JSON。
    """
    if not isinstance(data, dict):
        return False

    body = data.get("body")
    if not isinstance(body, list) or not body:
        return False

    first = body[0]
    if not isinstance(first, dict):
        return False

    return "from" in first and "to" in first and "content" in first


def extract_subtitle_text(data: dict) -> str:
    """
    从 B 站字幕 JSON 中提取 body[*].content。
    """
    body = data.get("body", [])

    lines = []
    for item in body:
        content = str(item.get("content", "")).strip()
        if content:
            lines.append(content)

    return "\n".join(lines)


def is_possible_subtitle_url(url: str) -> bool:
    """
    粗略判断是否可能是字幕 JSON 请求。
    如果抓不到，可以直接 return True，监听所有 JSON Response。
    """
    url_lower = url.lower()
    keywords = [
        "subtitle",
        "ai_subtitle",
        "aisubtitle",
        "bfs/subtitle",
        "bfs/ai",
    ]
    return any(k in url_lower for k in keywords)


async def check_login_status(page: Page) -> bool:
    """
    检查 Cookie 是否已经成功登录 B 站。
    """
    await page.goto(
        "https://api.bilibili.com/x/web-interface/nav",
        wait_until="domcontentloaded",
        timeout=30000,
    )

    text = await page.text_content("body")
    data = json.loads(text)

    is_login = data.get("data", {}).get("isLogin") is True

    if is_login:
        print("[登录] Cookie 有效，当前已登录")
    else:
        print("[登录] Cookie 无效或已过期")

    return is_login


async def click_subtitle_and_choose_chinese(page: Page) -> None:
    """
    模拟用户操作：
    1. 点击“字幕”
    2. 选择“中文”或“中文（自动生成）”
    """

    # 让播放器控制栏显示出来
    await page.mouse.move(800, 700)
    await page.wait_for_timeout(800)

    subtitle_button = page.locator(SUBTITLE_BUTTON_SELECTOR).first
    await subtitle_button.wait_for(state="visible", timeout=15000)
    await subtitle_button.click()
    print("[操作] 已点击字幕按钮")

    await page.wait_for_timeout(800)

    language_items = page.locator(SUBTITLE_LANGUAGE_SELECTOR)
    count = await language_items.count()

    if count == 0:
        raise RuntimeError("没有找到字幕语言选项，请检查 class 是否变化。")

    target_index: Optional[int] = None

    for i in range(count):
        text = (await language_items.nth(i).inner_text()).strip()
        print(f"[发现字幕选项] {i}: {text}")

        if "中文" in text or "AI" in text or "自动生成" in text:
            target_index = i
            break

    if target_index is None:
        raise RuntimeError("没有找到中文或 AI 字幕选项。")

    await language_items.nth(target_index).click()
    print("[操作] 已选择中文字幕")

    await page.wait_for_timeout(3000)


async def download_bilibili_subtitle_txt(
    video_url: str,
    cookie_string: str,
    output_dir: str = "subtitles",
    headless: bool = False,
    wait_seconds: int = 30,
) -> Optional[Path]:
    """
    主流程：
    打开视频页 -> 注入 Cookie -> 点击字幕 -> 选择中文 -> 捕获字幕 JSON -> 保存 TXT
    """

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    saved_file: Optional[Path] = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        cookies = parse_cookie_string(cookie_string)

        if not cookies:
            raise RuntimeError("Cookie 为空，请传入 B 站登录 Cookie。")

        await context.add_cookies(cookies)
        print("[登录] 已注入 Cookie")

        page = await context.new_page()

        is_login = await check_login_status(page)
        if not is_login:
            await browser.close()
            raise RuntimeError("Cookie 无效或已过期，请重新复制 B 站 Cookie。")

        async def handle_response(response: Response):
            nonlocal saved_file

            if saved_file is not None:
                return

            url = response.url

            if not is_possible_subtitle_url(url):
                return

            try:
                content_type = response.headers.get("content-type", "")

                if "json" not in content_type.lower() and not url.lower().endswith(".json"):
                    return

                data = await response.json()

                if not is_bilibili_subtitle_json(data):
                    return

                subtitle_text = extract_subtitle_text(data)

                if not subtitle_text.strip():
                    return

                title = await page.title()
                title = title.replace("_哔哩哔哩_bilibili", "")
                title = safe_filename(title)

                txt_path = output_path / f"{title}_subtitle.txt"

                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(subtitle_text)

                saved_file = txt_path
                print(f"[完成] 已保存字幕 TXT：{txt_path}")

            except Exception:
                return

        page.on("response", handle_response)

        print(f"[打开] {video_url}")
        await page.goto(video_url, wait_until="domcontentloaded", timeout=60000)

        await page.wait_for_timeout(5000)

        await click_subtitle_and_choose_chinese(page)

        print(f"[监听] 等待字幕 JSON Response，最多 {wait_seconds} 秒")

        for _ in range(wait_seconds):
            if saved_file is not None:
                break
            await page.wait_for_timeout(1000)

        await browser.close()

    return saved_file


def main():
    parser = argparse.ArgumentParser(
        description="使用 Playwright 下载 B 站官方 AI 字幕，并直接保存为 TXT"
    )

    parser.add_argument(
        "url",
        help="B 站视频 URL，例如：https://www.bilibili.com/video/BV1nm41197Aw",
    )

    cookie = """enable_web_push=DISABLE; DedeUserID=397795255; DedeUserID__ckMd5=542307cdcaf7ea48; enable_feed_channel=ENABLE; header_theme_version=OPEN; theme-tip-show=SHOWED; buvid4=96357499-E13E-ACDF-037D-AC27F4F2381987812-023110620-DLQaI8fO0w9k5D8WGot8/A%3D%3D; theme-avatar-tip-show=SHOWED; LIVE_BUVID=AUTO1717557868431015; PVID=1; buvid3=E160E344-2AA0-FA3A-4C28-41283E0A508270647infoc; b_nut=1762581870; _uuid=9C468A16-E910F-A12E-FF11-4DA821088457C70669infoc; buvid_fp=a98d17e95c360c508fe075d3ca0fafd9; CURRENT_QUALITY=120; rpdid=|(u~l~lm~Rk|0J'u~~uY)l|m~; _tea_utm_cache_586864={%22creative_id%22:1438149715}; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Nzc4NTI0MDYsImlhdCI6MTc3NzU5MzE0NiwicGx0IjotMX0.ocUmVYAwl3KpTNOam5Els24t3V09yEPSezZ2wH_jObI; bili_ticket_expires=1777852346; SESSDATA=e1229484%2C1793275552%2Ca9d53%2A52CjC95EWeDimRW_h8Tr7wKPIm5Z1Du9yTs7TjMABunfF8xLFHZxHskzI6QHSVk1xPw9MSVkUxWnFRanZlTHBQSXg1WlZlcnlwdzdLdGY2bm1JNDcxX2drMHBkMnhtbnVXX0hmdTJaQlNJY0JJd0FnVmx5RWtKaWtSWUo5U1pHcUwxMDE1S09EdDV3IIEC; bili_jct=570b3add74762629ce72753ed37d0406; sid=8f0stv2c; bmg_af_switch=1; bmg_src_def_domain=i2.hdslb.com; home_feed_column=4; CURRENT_FNVAL=4048; browser_resolution=709-730; bp_t_offset_397795255=1197809955869032448; b_lsid=F7361C7C_19DE8BCB9DA"""

    parser.add_argument(
        "-o",
        "--output-dir",
        default="subtitles",
        help="字幕 TXT 保存目录，默认 subtitles",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="无头模式运行。首次调试建议不要加。",
    )

    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=30,
        help="等待字幕 JSON Response 的最长时间，默认 30 秒。",
    )

    args = parser.parse_args()

    saved = asyncio.run(
        download_bilibili_subtitle_txt(
            video_url=args.url,
            cookie_string=cookie,
            output_dir=args.output_dir,
            headless=args.headless,
            wait_seconds=args.wait_seconds,
        )
    )

    if saved:
        print(f"[成功] 字幕 TXT 文件路径：{saved}")
    else:
        print("[失败] 没有捕获到字幕 TXT。")
        print("可能原因：")
        print("1. 该视频没有 B 站官方 AI 字幕；")
        print("2. 字幕按钮或语言选项 class 已变化；")
        print("3. Cookie 虽然有效，但当前视频字幕需要其他权限；")
        print("4. 字幕 JSON 请求在点击前已经加载。")


if __name__ == "__main__":
    main()