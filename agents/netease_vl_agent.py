#!/usr/bin/env python3
"""
网易云「看图操作」独立 Agent — 使用 VL 看截图并驱动键盘/鼠标。

支持两种 VL 提供商（NETEASE_VL_PROVIDER 环境变量）：
- dashscope（默认）：Qwen VL，需 DASHSCOPE_API_KEY。官方支持 image_url 多模态。
- deepseek：DeepSeek，需 DEEPSEEK_API_KEY。注意：官方 api.deepseek.com 的 deepseek-chat
  不支持图片输入，会返回 400。若要用 DeepSeek，需接入支持 vision 的兼容端点。

流程：截屏 → OCR 得到可点击元素 → 截图+元素发给 VL → 解析 action → 执行。

可选 OCR：pip install Pillow pytesseract && brew install tesseract tesseract-lang
调试：NETEASE_OCR_DEBUG=1 打印 OCR 结果；NETEASE_OCR_PSM=6 若 PSM11 识别不佳。

Usage:
  export NETEASE_VL_PROVIDER=dashscope
  export DASHSCOPE_API_KEY=your_key
  python -m agents.netease_vl_agent "搜索并播放 晴天"
"""

import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

# 可选：OCR 用于切割屏幕、定位文字/图标
try:
    from PIL import Image
    import pytesseract
    from pytesseract import Output
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False

# Qwen VL (DashScope) - 支持 image_url
_DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DASHSCOPE_MODEL = "qwen-vl-plus"

# DeepSeek - 官方 chat 不支持图片，保留供兼容端点使用
_DEEPSEEK_BASE = "https://api.deepseek.com"
_DEEPSEEK_MODEL = "deepseek-chat"

_MAX_ROUNDS = 16

# 本仓库 scripts 目录下网易云脚本
_ROOT = Path(__file__).resolve().parent.parent
_NETEASE_SCRIPT = _ROOT / "scripts" / "netease_cloud_music.py"


def _take_screenshot() -> bytes | None:
    """macOS 截屏到临时文件，返回 PNG 字节。"""
    if sys.platform != "darwin":
        return None
    fd, path = tempfile.mkstemp(suffix=".png")
    try:
        os.close(fd)
        r = subprocess.run(
            ["screencapture", "-x", "-t", "png", path],
            capture_output=True,
            timeout=5,
        )
        if r.returncode != 0:
            return None
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def _preprocess_for_ocr(img: "Image.Image") -> "Image.Image":
    """提升截图对比度，便于 OCR 识别小字（如网易云「单曲」标签）。"""
    from PIL import ImageEnhance, ImageOps
    # 转为 RGB（兼容 RGBA）
    if img.mode != "RGB":
        img = img.convert("RGB")
    # 若 Retina 屏截图分辨率高，缩小到常见尺寸可提升 Tesseract 稳定性
    w, h = img.size
    if w > 1920 or h > 1080:
        scale = min(1920 / w, 1080 / h, 1.0)
        if scale < 1.0:
            nw, nh = int(w * scale), int(h * scale)
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.LANCZOS
            img = img.resize((nw, nh), resample)
    # 增强对比度（网易云 UI 对比有时偏弱）
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.2)
    return img


def _get_screen_elements(png: bytes) -> tuple[int, int, list[dict]]:
    """对截图做 OCR，得到 (宽度, 高度, 可点击元素列表)。元素为 {"id", "text", "cx", "cy", "w", "h"}。
    若未装 Pillow/pytesseract 或 OCR 失败，返回 (0, 0, [])。"""
    if not _OCR_AVAILABLE:
        return 0, 0, []
    try:
        img = Image.open(io.BytesIO(png))
        w, h = img.size
        img_proc = _preprocess_for_ocr(img)
        # PSM 11=稀疏文本（适合 GUI 标签）；可用 NETEASE_OCR_PSM=6 覆盖
        psm = os.environ.get("NETEASE_OCR_PSM", "11")
        config = f"--psm {psm} --oem 3"
        data = pytesseract.image_to_data(
            img_proc, lang="chi_sim+eng", output_type=Output.DICT, config=config
        )
        n = len(data.get("text", []))
        elements = []
        seen_boxes: set[tuple[int, int, int, int]] = set()
        for i in range(n):
            text = (data.get("text") or [""])[i] or ""
            text = text.strip()
            if not text or len(text) > 30:
                continue
            conf = int((data.get("conf") or [0])[i] or -1)
            if conf < 0:
                continue
            if conf == 0 and len(text) > 2:
                continue
            left = int((data.get("left") or [0])[i] or 0)
            top = int((data.get("top") or [0])[i] or 0)
            width = int((data.get("width") or [0])[i] or 0)
            height = int((data.get("height") or [0])[i] or 0)
            if width < 3 or height < 3:
                continue
            # 坐标映射回原图（若做了缩放）
            ow, oh = img.size
            pw, ph = img_proc.size
            if pw != ow or ph != oh:
                sx, sy = ow / pw, oh / ph
                left = int(left * sx)
                top = int(top * sy)
                width = int(width * sx)
                height = int(height * sy)
            key = (left // 8, top // 8, width // 8, height // 8)
            if key in seen_boxes:
                continue
            seen_boxes.add(key)
            cx = left + width // 2
            cy = top + height // 2
            elements.append({
                "id": len(elements),
                "text": text,
                "cx": cx,
                "cy": cy,
                "w": width,
                "h": height,
            })
        # 合并相邻的「单」「曲」为「单曲」
        merged: list[dict] = []
        used: set[int] = set()
        for i, a in enumerate(elements):
            if i in used:
                continue
            if a["text"] in ("单", "曲"):
                other = "曲" if a["text"] == "单" else "单"
                for j, b in enumerate(elements):
                    if j <= i or j in used or b["text"] != other:
                        continue
                    if abs(a["cy"] - b["cy"]) < 15 and abs(a["cx"] - b["cx"]) < 80:
                        used.add(i)
                        used.add(j)
                        mx = (a["cx"] + b["cx"]) // 2
                        my = (a["cy"] + b["cy"]) // 2
                        merged.append({"id": len(merged), "text": "单曲", "cx": mx, "cy": my, "w": a["w"] + b["w"], "h": max(a["h"], b["h"])})
                        break
                else:
                    merged.append({**a, "id": len(merged)})
                continue
            merged.append({**a, "id": len(merged)})
        elements = merged
        # 优先展示与网易云相关的元素。「单曲」选项卡在顶部，与下方「单曲>」标题区分
        def _score(e: dict) -> tuple:
            t, cy_val = (e["text"], e["cy"])
            s = 0
            if t == "单曲" or (t.strip() == "单曲" and ">" not in t):
                s = 120
            elif "单曲" in t and ">" in t:
                s = 70
            elif "单曲" in t or t in ("单", "曲"):
                s = 100
            elif t in ("综合", "歌单", "歌手") and cy_val < h * 0.4:
                s = 95
            elif "歌手" in t or "专辑" in t:
                s = 90
            elif any(c in t for c in "播放暂停下一首上一首"):
                s = 80
            elif 80 < cy_val < h - 80:
                s = 50
            if cy_val < 60 or cy_val > h - 60:
                s -= 30
            return (-s, cy_val)
        elements.sort(key=_score)
        for i, e in enumerate(elements):
            e["id"] = i
        if os.environ.get("NETEASE_OCR_DEBUG"):
            dbg = [(e["text"], e["cx"], e["cy"]) for e in elements[:30]]
            print(f"[OCR] w={w} h={h} elements={len(elements)} sample={dbg[:15]}", file=sys.stderr)
        return w, h, elements
    except Exception as e:
        if os.environ.get("NETEASE_OCR_DEBUG"):
            print(f"[OCR] error: {e}", file=sys.stderr)
        return 0, 0, []


def _build_vl_prompt_parts(
    user_goal: str,
    elements: list[dict] | None,
    img_size: tuple[int, int] = (0, 0),
) -> tuple[str, str]:
    """构造 system 和 user prompt 文本。"""
    use_elements = elements and len(elements) > 0
    if use_elements:
        click_rule = (
            "- {\"action\": \"click\", \"element_id\": 整数} — 点击上面「当前屏幕检测到的可点击区域」中对应 id 的元素（中心坐标已给出），必须从列表中选 id，不要自己写 x,y。"
        )
        elements_blob = "当前屏幕检测到的可点击区域（OCR 文字/图标位置，请用 element_id 选择）：\n" + "\n".join(
            f"  id={e['id']} 文字=\"{e['text']}\" 中心=({e['cx']},{e['cy']})"
            for e in elements[:120]
        )
    else:
        w, h = img_size
        size_hint = f"（截图尺寸约 {w}×{h} 像素）" if w and h else ""
        click_rule = (
            "- {\"action\": \"click\", \"x\": 整数, \"y\": 整数} — 通过看图直接估计要点击区域的中心像素坐标。"
            f"例如「单曲」标签通常在搜索结果页左侧，「第一首歌」在第一行文字中心。必须给出准确的 x,y{size_hint}。"
        )
        elements_blob = ""

    system_prompt = """你是网易云音乐界面分析助手。用户会给你一张当前屏幕截图和一条「用户目标」。
你只能回复一个 JSON 对象，不要其他任何文字。可选 action：
- {"action": "search", "query": "关键词"} — 仅打开搜索框并输入关键词、回车，展示搜索结果（不自动播放）
""" + click_rule + """
- {"action": "key", "name": "next"|"previous"|"play_pause"} — 发送下一首/上一首/播放暂停
- {"action": "tab_to_single"} — 用 Tab 键切换到「单曲」标签（当 OCR 无法定位时使用）
- {"action": "done", "message": "说明"} — 任务已完成或无法继续

重要：必须用鼠标点击完成操作，禁止跳过点击步骤！
「搜索某首歌然后播放」必须分步完成，每步只做一个 action：
1) 若当前还未搜索：先返回 {"action": "search", "query": "歌曲名"}，只做搜索。
2) 若截图里已是搜索结果页（当前是「综合」视图）：必须返回 click 点击顶部的「单曲」选项卡（在「综合」右侧的横向标签，y 较小），不要点下面的「单曲>」标题。若无 element_id 可点，可返回 {"action": "tab_to_single"} 用键盘切换。
3) 若截图里已是单曲列表（有歌曲行）：必须返回 click 点击第一首歌曲那一行，禁止返回 done。
4) 只有在点完第一首歌、界面已显示在播放后，才可返回 {\"action\": \"done\", \"message\": \"已播放\"}。"""

    is_search_play = (
        "搜索" in user_goal or "搜 " in user_goal or "播一首" in user_goal
        or "搜索并播放" in user_goal or "搜并播" in user_goal
    )
    if is_search_play:
        prompt_text = (
            "当前用户目标：" + user_goal + "\n\n"
            "第一步：只做搜索。从用户目标中提取歌曲名/关键词，返回 {\"action\": \"search\", \"query\": \"歌曲名\"}。"
            "执行后下一轮会再给你截图，你再看图点「单曲」、再点第一首歌播放。"
        )
    else:
        prompt_text = (
            "当前用户目标：" + user_goal + "\n\n请只返回一个 JSON 对象，例如 "
            '{"action": "key", "name": "next"} 或 {"action": "click", "element_id": 0} 或 {"action": "done", "message": "已处理"}。'
        )
    if use_elements:
        prompt_text = elements_blob + "\n\n" + prompt_text
    return system_prompt, prompt_text


def _call_qwen_vl(
    image_b64: str,
    user_goal: str,
    history: list[dict],
    elements: list[dict] | None = None,
    img_size: tuple[int, int] = (0, 0),
) -> str:
    """调用 Qwen VL (DashScope)：支持 image_url 多模态。"""
    api_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("请设置环境变量 DASHSCOPE_API_KEY（provider=dashscope 时）")

    base = os.environ.get("DASHSCOPE_BASE_URL", _DASHSCOPE_BASE).rstrip("/")
    model = os.environ.get("QWEN_VL_MODEL", _DASHSCOPE_MODEL)
    url = f"{base}/chat/completions"
    system_prompt, prompt_text = _build_vl_prompt_parts(user_goal, elements, img_size)

    content = [
        {"type": "text", "text": prompt_text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
    ]
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": content})

    body = {"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 512}

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    return (msg.get("content") or "").strip()


def _call_deepseek_vl(
    image_b64: str,
    user_goal: str,
    history: list[dict],
    elements: list[dict] | None = None,
    img_size: tuple[int, int] = (0, 0),
) -> str:
    """调用 DeepSeek VL。注意：官方 api.deepseek.com 的 deepseek-chat 不支持 image_url。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise ValueError("请设置环境变量 DEEPSEEK_API_KEY（provider=deepseek 时）")

    base = os.environ.get("DEEPSEEK_BASE_URL", _DEEPSEEK_BASE).rstrip("/")
    model = os.environ.get("DEEPSEEK_VL_MODEL", _DEEPSEEK_MODEL)
    url = f"{base}/chat/completions"
    system_prompt, prompt_text = _build_vl_prompt_parts(user_goal, elements, img_size)

    content = [
        {"type": "text", "text": prompt_text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
    ]
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": content})

    body = {"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 512}

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    return (msg.get("content") or "").strip()


def _call_vl(
    image_b64: str,
    user_goal: str,
    history: list[dict],
    elements: list[dict] | None = None,
    img_size: tuple[int, int] = (0, 0),
) -> str:
    """根据 NETEASE_VL_PROVIDER 调用对应 VL。"""
    provider = (os.environ.get("NETEASE_VL_PROVIDER", "dashscope") or "dashscope").strip().lower()
    if provider == "deepseek":
        return _call_deepseek_vl(image_b64, user_goal, history, elements, img_size)
    return _call_qwen_vl(image_b64, user_goal, history, elements, img_size)


def _parse_action(text: str) -> dict | None:
    """从 VL 回复中解析出单个 JSON 对象。"""
    text = text.strip()
    # 先尝试整段解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 再找第一个 { ... } 平衡括号
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _run_action(action: dict, elements: list[dict] | None = None) -> str:
    """执行 action，返回执行结果描述。elements 为当轮 OCR 得到的可点击列表，用于 element_id 解析。"""
    act = action.get("action")
    if not act:
        return "无效 action"

    if act == "done":
        return action.get("message", "done")

    if act == "key":
        name = action.get("name", "")
        if name not in ("next", "previous", "play_pause"):
            return f"未知 key name: {name}"
        if not _NETEASE_SCRIPT.exists():
            return "未找到 netease_cloud_music.py"
        r = subprocess.run(
            [sys.executable, str(_NETEASE_SCRIPT), name],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(_ROOT),
        )
        if r.returncode != 0:
            return r.stderr or r.stdout or "执行失败"
        return r.stdout or "已执行"

    if act == "search":
        query = action.get("query", "").strip()
        if not query:
            return "search 缺少 query"
        if not _NETEASE_SCRIPT.exists():
            return "未找到 netease_cloud_music.py"
        r = subprocess.run(
            [sys.executable, str(_NETEASE_SCRIPT), "search", query],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(_ROOT),
        )
        if r.returncode != 0:
            return r.stderr or r.stdout or "执行失败"
        return r.stdout or "已执行搜索，请根据下一张截图点「单曲」再点第一首播放"

    if act == "tab_to_single":
        try:
            for app in ("NeteaseMusic", "NetEase Cloud Music", "网易云音乐"):
                r = subprocess.run(
                    ["osascript", "-e", f'tell application "{app}" to activate'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if r.returncode == 0:
                    break
            time.sleep(0.8)
            subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 48'], capture_output=True, timeout=5)
            time.sleep(0.25)
            subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 48'], capture_output=True, timeout=5)
            return "已用 Tab 切换到单曲，请根据下一张截图点第一首歌"
        except Exception as e:
            return f"tab_to_single 失败: {e}"

    if act == "click":
        x, y = None, None
        eid = action.get("element_id")
        if eid is not None and elements:
            for e in elements:
                if e.get("id") == eid:
                    x, y = e.get("cx"), e.get("cy")
                    break
        if x is None and y is None:
            x, y = action.get("x"), action.get("y")
        if x is None or y is None:
            return "click 缺少 element_id 或 x,y"
        xi, yi = int(x), int(y)
        try:
            # 使用 w: 和末尾 p 避免 cliclick 已知问题（光标消失直到用户移动）。点击后再微移以唤醒光标显示。
            r = subprocess.run(
                [
                    "cliclick",
                    f"m:{xi},{yi}",
                    "w:80",
                    "c:.",
                    "w:80",
                    f"m:{xi+2},{yi+2}",
                    f"m:{xi},{yi}",
                    "p",
                ],
                capture_output=True,
                timeout=5,
            )
            if r.returncode != 0:
                return "cliclick 未安装或失败，请 brew install cliclick"
            return "已点击"
        except FileNotFoundError:
            return "cliclick 未安装，请 brew install cliclick"

    return f"未知 action: {act}"


def run_agent(user_goal: str) -> str:
    """主循环：截屏 → VL → 解析 action → 执行 → 直到 done 或达到最大轮数。"""
    if not user_goal or not user_goal.strip():
        return "请提供一条用户目标，例如：播放下一首、搜索并播放 晴天"

    goal = user_goal.strip()
    history: list[dict] = []
    last_result: str = ""

    for round_num in range(_MAX_ROUNDS):
        png = _take_screenshot()
        if not png:
            return "截屏失败（仅支持 macOS）"
        img_w, img_h, elements = _get_screen_elements(png)
        image_b64 = base64.b64encode(png).decode("utf-8")

        try:
            reply = _call_vl(
                image_b64, goal, history,
                elements=elements if elements else None,
                img_size=(img_w, img_h),
            )
        except Exception as e:
            return f"调用 VL 失败: {e}"

        action = _parse_action(reply)
        if not action:
            history.append({"role": "assistant", "content": reply})
            history.append({"role": "user", "content": "请只返回一个 JSON 对象，不要其他文字。例如 {\"action\": \"key\", \"name\": \"next\"}"})
            continue

        if action.get("action") == "done":
            return action.get("message", "完成")

        result = _run_action(action, elements=elements)
        last_result = result
        if action.get("action") in ("search", "tab_to_single"):
            time.sleep(1.2)
        history.append({"role": "assistant", "content": reply})
        click_hint = (
            '{"action": "click", "element_id": 上面的id} 或 {"action": "tab_to_single"} 或 '
            '{"action": "done", "message": "..."}。'
            if elements else
            '{"action": "click", "x": 整数, "y": 整数} 或 {"action": "tab_to_single"} 或 {"action": "done", "message": "..."}。'
        )
        last_act = action.get("action")
        just_clicked = (last_act == "click" and "已点击" in result)
        if last_act == "search":
            follow = (
                f"执行结果：{result}\n\n"
                "上一步已执行搜索。现在必须切换到单曲：优先用 click 点击顶部的「单曲」选项卡（在综合右侧）。"
                "若无合适元素可点，可返回 {\"action\": \"tab_to_single\"} 用键盘切换。"
                f" 只返回一个 JSON：{click_hint}"
            )
        elif just_clicked:
            follow = (
                f"执行结果：{result}\n\n"
                "重要：若当前截图里已在播放、或你上一步点的是第一首歌，必须立即返回 "
                '{"action": "done", "message": "已播放"}。否则：在搜索结果页点「单曲」，在单曲列表点第一首。'
                + (f" 格式：{click_hint}" if not elements else "")
            )
        else:
            follow = (
                f"执行结果：{result}\n\n"
                "必须用 click 完成：在搜索结果页点「单曲」，在单曲列表点第一首歌。禁止直接返回 done。"
                f" 只返回一个 JSON，如 {click_hint}"
            )
        history.append({"role": "user", "content": follow})

    # 若最后一轮是成功点击，可能是 VL 没返回 done，视为已完成
    if last_result and "已点击" in last_result:
        return "已执行点击操作；若已点过第一首，可视为搜索并播放已完成。"
    return "已达到最大轮数，未得到 done"


def main() -> int:
    goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    out = run_agent(goal)
    print(out)
    return 0 if "失败" not in out and "错误" not in out else 1


if __name__ == "__main__":
    sys.exit(main())
