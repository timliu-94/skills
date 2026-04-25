import os
import re
import hashlib
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup


def sanitize_filename(name: str, max_length: int = 150) -> str:
    """
    清洗文件名
    """
    if not name:
        return "untitled"

    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.rstrip(".")
    if not name:
        name = "untitled"
    return name[:max_length]


def get_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://mp.weixin.qq.com/",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def extract_title(html: str) -> str:
    """
    优先提取微信公众号文章标题
    """
    patterns = [
        r'var\s+msg_title\s*=\s*"([^"]+)"',
        r"var\s+msg_title\s*=\s*'([^']+)'",
        r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
        r"<title>(.*?)</title>",
    ]

    for pattern in patterns:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if m:
            title = re.sub(r"<.*?>", "", m.group(1)).strip()
            if title:
                return title

    return "untitled"


def make_unique_path(directory: Path, filename: str, suffix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{filename}{suffix}"
    if not path.exists():
        return path

    idx = 1
    while True:
        path = directory / f"{filename}_{idx}{suffix}"
        if not path.exists():
            return path
        idx += 1


def guess_extension(content_type: str, url: str) -> str:
    """
    根据 content-type 或 url 猜测扩展名
    """
    content_type = (content_type or "").lower()
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    if "png" in content_type:
        return ".png"
    if "gif" in content_type:
        return ".gif"
    if "webp" in content_type:
        return ".webp"
    if "svg" in content_type:
        return ".svg"

    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}:
        return ext
    return ".jpg"


def is_image_url(url: str) -> bool:
    if not url:
        return False
    url_lower = url.lower()
    return (
        "mmbiz.qpic.cn" in url_lower
        or "mmbiz.qlogo.cn" in url_lower
        or "wx.qlogo.cn" in url_lower
        or any(url_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"])
    )


def download_binary(url: str, save_path: Path) -> bool:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://mp.weixin.qq.com/",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30, stream=True)
        resp.raise_for_status()

        # 微信图片偶尔会返回 text/plain 但实际是图片，所以不强依赖 content-type
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"[下载失败] {url} -> {e}")
        return False


def collect_image_candidates(tag, base_url: str) -> list[str]:
    """
    从 img 标签中收集可能的图片链接
    微信文章里常见字段：
    - src
    - data-src
    - data-original
    """
    candidates = []

    for attr in ["data-src", "data-original", "src"]:
        value = tag.get(attr)
        if value:
            full_url = urljoin(base_url, value)
            candidates.append(full_url)

    # 去重，保持顺序
    seen = set()
    result = []
    for x in candidates:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result


def rewrite_and_download_images(html: str, page_url: str, asset_dir: Path) -> str:
    soup = BeautifulSoup(html, "lxml")
    asset_dir.mkdir(parents=True, exist_ok=True)

    img_index = 1
    downloaded = {}

    for img in soup.find_all("img"):
        candidates = collect_image_candidates(img, page_url)

        target_url = None
        for candidate in candidates:
            if is_image_url(candidate):
                target_url = candidate
                break

        if not target_url and candidates:
            # 没识别出来也尝试第一个
            target_url = candidates[0]

        if not target_url:
            continue

        # 避免重复下载同一图片
        if target_url in downloaded:
            local_rel_path = downloaded[target_url]
            img["src"] = local_rel_path
            # 清理可能残留的远程属性
            for attr in ["data-src", "data-original", "srcset"]:
                if attr in img.attrs:
                    del img.attrs[attr]
            continue

        # 先请求头部/内容推断扩展名，简单起见直接下载
        temp_name = f"img_{img_index:03d}"
        ext = os.path.splitext(urlparse(target_url).path)[1].lower()
        if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}:
            ext = ".jpg"

        local_filename = temp_name + ext
        save_path = asset_dir / local_filename

        ok = download_binary(target_url, save_path)
        if not ok:
            # 若失败，保留原 URL
            continue

        local_rel_path = f"{asset_dir.name}/{local_filename}"
        downloaded[target_url] = local_rel_path

        img["src"] = local_rel_path
        for attr in ["data-src", "data-original", "srcset"]:
            if attr in img.attrs:
                del img.attrs[attr]

        img_index += 1

    return str(soup)


def save_wechat_article(url: str, output_dir: str = "wechat_articles") -> str:
    """
    下载微信公众号文章 HTML，并下载其中引用图片，替换成本地路径
    """
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    html = get_html(url)
    title = sanitize_filename(extract_title(html))

    # HTML 文件路径
    html_path = make_unique_path(output_root, title, ".html")

    # 每篇文章对应一个资源目录
    asset_dir = output_root / f"{html_path.stem}_files"

    new_html = rewrite_and_download_images(html, url, asset_dir)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)

    return str(html_path)


def batch_save_wechat_articles(urls: list[str], output_dir: str = "wechat_articles") -> list[str]:
    results = []
    for url in urls:
        try:
            path = save_wechat_article(url, output_dir=output_dir)
            print(f"[成功] {url} -> {path}")
            results.append(path)
        except Exception as e:
            print(f"[失败] {url} -> {e}")
    return results


if __name__ == "__main__":
    # 单篇
    url = "https://mp.weixin.qq.com/s/SPLTD-hFAsyYAA7V1lU8OA"
    path = save_wechat_article(url)
    print("save successfully：", path)

    # 批量示例
    # urls = [
    #     "https://mp.weixin.qq.com/s/xxx1",
    #     "https://mp.weixin.qq.com/s/xxx2",
    # ]
    # batch_save_wechat_articles(urls)