#!/usr/bin/env python3
"""
NetEase Cloud Music (网易云音乐) control script — macOS.

纯 computer use：不依赖任何第三方包，仅通过激活应用 + 系统按键/剪贴板/鼠标点击操作网易云。
实现思路（与 Windows 句柄操作等价）：
  1. 激活应用：AppleScript tell application "NeteaseMusic" to activate
  2. 发键/剪贴板：System Events 的 key code / keystroke，或 set the clipboard + Cmd+V
  3. 鼠标点击：取「单曲」控件 position/size 算中心坐标，用 cliclick 移动鼠标到该点并点击（需 brew install cliclick）；未安装则回退 Tab×2

参考过开源实现（如 cloud-music-mcp 的快捷键、搜索流程），但本脚本不调用其 API/URL Scheme。

Actions: 播放/暂停/下一首/上一首（激活后发键）；搜索（Cmd+F + 剪贴板粘贴）；搜歌并播第一首（搜索 → 切单曲 → 下移 → Enter）。
需在 系统设置 > 隐私与安全性 > 辅助功能 中授权终端/Cursor。

Usage:
  python scripts/netease_cloud_music.py play_pause
  python scripts/netease_cloud_music.py next
  python scripts/netease_cloud_music.py previous
  python scripts/netease_cloud_music.py search "关键词"
  python scripts/netease_cloud_music.py search_play_first "关键词"
  python scripts/netease_cloud_music.py status
"""

import os
import sys
import subprocess
import time

# AppleScript app name: try common display names and bundle names
NETEASE_APP_NAMES = ("NetEase Cloud Music", "网易云音乐", "NeteaseMusic")


def _run_osascript(script: str) -> tuple[bool, str]:
    """Run osascript -e script; return (ok, stderr_or_stdout)."""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "").strip()
        return True, (r.stdout or "").strip()
    except FileNotFoundError:
        return False, "osascript not found"
    except subprocess.TimeoutExpired:
        return False, "osascript timed out"


def _is_netease_installed() -> bool:
    """Check if NetEase Cloud Music app exists (no launch)."""
    paths = [
        "/Applications/NeteaseMusic.app",
        "/Applications/NetEase Cloud Music.app",
        "/Applications/网易云音乐.app",
        os.path.expanduser("~/Applications/NeteaseMusic.app"),
        os.path.expanduser("~/Applications/NetEase Cloud Music.app"),
        os.path.expanduser("~/Applications/网易云音乐.app"),
    ]
    for path in paths:
        try:
            if os.path.isdir(path):
                return True
        except Exception:
            pass
    try:
        # Spotlight: find any .app path containing NetEase or 网易云
        for query in ("NetEase", "网易云"):
            r = subprocess.run(
                ["mdfind", query],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if r.returncode == 0 and r.stdout:
                for line in r.stdout.strip().split("\n"):
                    if line.rstrip().endswith(".app"):
                        return True
    except Exception:
        pass
    return False


def _activate_netease() -> bool:
    """Activate NetEase Cloud Music; try English and Chinese app name."""
    for app_name in NETEASE_APP_NAMES:
        script = f'tell application "{app_name}" to activate'
        ok, err = _run_osascript(script)
        if ok:
            return True
        if "not found" in err.lower() or "doesn't understand" in err.lower() or "2691" in err or "2753" in err:
            continue
        return True  # other error might still mean app is there
    return False


_ACTIVATE_DELAY = 0.7


def _activate_then_send_key(key_code: int, *, command: bool = False, control: bool = False, shift: bool = False) -> bool:
    """一次 osascript 内完成：激活网易云 → delay → 发键。焦点不会在中间被 Terminal 抢走."""
    mods = []
    if command:
        mods.append("command down")
    if control:
        mods.append("control down")
    if shift:
        mods.append("shift down")
    mod_str = " using {" + ", ".join(mods) + "}" if mods else ""
    script = f'''
        try
            tell application "NeteaseMusic" to activate
        on error
            try
                tell application "NetEase Cloud Music" to activate
            on error
                try
                    tell application "网易云音乐" to activate
                end try
            end try
        end try
        delay {_ACTIVATE_DELAY}
        tell application "System Events" to key code {key_code}{mod_str}
    '''
    lines = [line.strip() for line in script.strip().split("\n") if line.strip()]
    cmd = ["osascript"]
    for line in lines:
        cmd.extend(["-e", line])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def _activate_then_search(query: str) -> bool:
    """一次 osascript 内：剪贴板写入关键词 → 激活 → Cmd+F → Cmd+A 全选 → Cmd+V 粘贴 → Enter（不依赖输入法）."""
    # 剪贴板内容在 AppleScript 里要转义 \ 和 "
    esc = (query or "").replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
        set the clipboard to "{esc}"
        try
            tell application "NeteaseMusic" to activate
        on error
            try
                tell application "NetEase Cloud Music" to activate
            on error
                try
                    tell application "网易云音乐" to activate
                end try
            end try
        end try
        delay {_ACTIVATE_DELAY}
        tell application "System Events" to key code 3 using {{command down}}
        delay 0.4
        tell application "System Events" to key code 0 using {{command down}}
        delay 0.2
        tell application "System Events" to key code 9 using {{command down}}
        delay 0.3
        tell application "System Events" to key code 36
    '''
    lines = [line.strip() for line in script.strip().split("\n") if line.strip()]
    cmd = ["osascript"]
    for line in lines:
        cmd.extend(["-e", line])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def _activate_then_search_play_first(query: str) -> bool:
    """搜歌 → 等待 → 用 cliclick 把鼠标移到「单曲」中心并点击（需 brew install cliclick）；否则 Tab×2 → Down → Enter."""
    esc = (query or "").replace("\\", "\\\\").replace('"', '\\"')
    proc = _process_name()
    script = f'''
        set the clipboard to "{esc}"
        try
            tell application "NeteaseMusic" to activate
        on error
            try
                tell application "NetEase Cloud Music" to activate
            on error
                try
                    tell application "网易云音乐" to activate
                end try
            end try
        end try
        delay {_ACTIVATE_DELAY}
        tell application "System Events" to key code 3 using {{command down}}
        delay 0.4
        tell application "System Events" to key code 0 using {{command down}}
        delay 0.2
        tell application "System Events" to key code 9 using {{command down}}
        delay 0.3
        tell application "System Events" to key code 36
        delay 1.2
        tell application "System Events"
            set didClick to false
            set cx to 0
            set cy to 0
            try
                tell process "{proc}"
                    set tabEl to first button of window 1 whose name is "单曲"
                    set p to position of tabEl
                    set s to size of tabEl
                    set cx to (item 1 of p) + (item 1 of s) / 2
                    set cy to (item 2 of p) + (item 2 of s) / 2
                end tell
                set didClick to true
            on error
                try
                    tell process "{proc}"
                        set allEls to entire contents of window 1
                        repeat with el in allEls
                            try
                                if name of el is "单曲" then
                                    set p to position of el
                                    set s to size of el
                                    set cx to (item 1 of p) + (item 1 of s) / 2
                                    set cy to (item 2 of p) + (item 2 of s) / 2
                                    set didClick to true
                                    exit repeat
                                end if
                            end try
                        end repeat
                    end tell
                end try
            end try
            if didClick and cx > 0 and cy > 0 then
                try
                    do shell script "cliclick m:" & (cx as integer) & "," & (cy as integer)
                    delay 0.1
                    do shell script "cliclick c:."
                on error
                    set didClick to false
                end try
            end if
            if not didClick then
                key code 48
                delay 0.25
                key code 48
                delay 0.25
            end if
        end tell
        delay 0.4
        tell application "System Events" to key code 125
        delay 0.15
        tell application "System Events" to key code 36
    '''
    lines = [line.strip() for line in script.strip().split("\n") if line.strip()]
    cmd = ["osascript"]
    for line in lines:
        cmd.extend(["-e", line])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        return r.returncode == 0
    except Exception:
        return False


def _process_name() -> str:
    """NeteaseMusic 在 System Events 里的 process 名（tell process 用）。"""
    ok, out = _run_osascript('tell application "System Events" to get name of every process')
    if not ok or not out:
        return "NeteaseMusic"
    processes = (out or "").replace(", ", ",").split(",")
    for name in ("NeteaseMusic", "NetEase Cloud Music", "网易云音乐"):
        if name in processes:
            return name
    return "NeteaseMusic"


def _send_key(
    key_code: int,
    *,
    control: bool = False,
    option: bool = False,
    command: bool = False,
    shift: bool = False,
    to_process: bool = True,
) -> bool:
    """Send key code. to_process=True 时发给网易云进程；False 时发给系统（用于全局快捷键）."""
    mods = []
    if control:
        mods.append("control down")
    if shift:
        mods.append("shift down")
    if option:
        mods.append("option down")
    if command:
        mods.append("command down")
    mod_str = " using {" + ", ".join(mods) + "}" if mods else ""
    if to_process:
        proc = _process_name()
        script = f'tell application "System Events" to tell process "{proc}" to key code {key_code}{mod_str}'
    else:
        script = f'tell application "System Events" to key code {key_code}{mod_str}'
    ok, _ = _run_osascript(script)
    return ok


def _send_keystroke(char: str, *, command: bool = False) -> bool:
    """Send keystroke to NeteaseMusic process."""
    esc = char.replace("\\", "\\\\").replace('"', '\\"')
    mod_str = ' using {command down}' if command else ""
    proc = _process_name()
    script = f'tell application "System Events" to tell process "{proc}" to keystroke "{esc}"{mod_str}'
    ok, _ = _run_osascript(script)
    return ok


def _ensure_netease_activated() -> int:
    """Try to activate NetEase; on failure print install/open hint and return 1."""
    if _activate_netease():
        return 0
    if _is_netease_installed():
        print("请先打开网易云音乐。", file=sys.stderr)
    else:
        print("请先安装网易云音乐。", file=sys.stderr)
    return 1


def _frontmost_app_name() -> str:
    """当前前台应用名（调试用）."""
    ok, out = _run_osascript('tell application "System Events" to get name of first process whose frontmost is true')
    return (out or "").strip() or "?"


def play_pause() -> int:
    """一次脚本内：激活网易云 → 等待 → 发 空格（播放/暂停）."""
    if _activate_then_send_key(49):  # Space
        print("已执行：播放/暂停")
        return 0
    if _ensure_netease_activated() != 0:
        return 1
    print("发送播放/暂停按键失败，请确保已授予辅助功能权限。", file=sys.stderr)
    return 1


def next_track() -> int:
    """一次脚本内：激活网易云 → 等待 → 发 ⌘→（下一首）."""
    if _activate_then_send_key(124, command=True):  # Cmd+Right
        print("已执行：下一首")
        return 0
    if _ensure_netease_activated() != 0:
        return 1
    print("发送下一首按键失败，请确保已授予辅助功能权限。", file=sys.stderr)
    return 1


def previous_track() -> int:
    """一次脚本内：激活网易云 → 等待 → 发 ⌘←（上一首）."""
    if _activate_then_send_key(123, command=True):  # Cmd+Left
        print("已执行：上一首")
        return 0
    if _ensure_netease_activated() != 0:
        return 1
    print("发送上一首按键失败，请确保已授予辅助功能权限。", file=sys.stderr)
    return 1


def search_song(query: str) -> int:
    """激活网易云 → 打开搜索（Cmd+F）→ 输入关键词 → 回车."""
    if not (query or query.strip()):
        print("请提供搜索关键词，例如: netease_cloud_music.py search \"周杰伦\"", file=sys.stderr)
        return 1
    if _activate_then_search(query.strip()):
        print(f"已执行：搜索「{query.strip()}」")
        return 0
    if _ensure_netease_activated() != 0:
        return 1
    print("搜索操作失败，请确保已授予辅助功能权限。若网易云无 Cmd+F 搜索，可反馈。", file=sys.stderr)
    return 1


def search_play_first(query: str) -> int:
    """搜歌并播放第一首：纯 computer use（激活 → 搜索 → 切单曲 → 选第一首 → Enter）."""
    if not (query or query.strip()):
        print("请提供搜索关键词，例如: netease_cloud_music.py search_play_first \"晴天\"", file=sys.stderr)
        return 1
    q = query.strip()
    if _activate_then_search_play_first(q):
        print(f"已执行：搜索并播放第一首「{q}」")
        return 0
    if _ensure_netease_activated() != 0:
        return 1
    print("搜索并播放失败，请确保已授予辅助功能权限。", file=sys.stderr)
    return 1


def status() -> int:
    """Print whether NetEase is installed and activatable (no key sent)."""
    if _activate_netease():
        print("网易云音乐已就绪")
        return 0
    if _is_netease_installed():
        print("网易云音乐已安装，但当前无法激活（请先打开应用）", file=sys.stderr)
    else:
        print("未检测到网易云音乐，请先安装。", file=sys.stderr)
    return 1


def main() -> int:
    if sys.platform != "darwin":
        print("当前仅支持 macOS。", file=sys.stderr)
        return 1

    if len(sys.argv) < 2:
        print("用法: netease_cloud_music.py <play_pause|next|previous|search|search_play_first|status> [搜索关键词]", file=sys.stderr)
        return 1

    action = sys.argv[1]
    if action == "search":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        return search_song(query)
    if action == "search_play_first":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        return search_play_first(query)
    actions = {
        "play_pause": play_pause,
        "next": next_track,
        "previous": previous_track,
        "status": status,
    }
    if action not in actions:
        print("用法: netease_cloud_music.py <play_pause|next|previous|search|search_play_first|status> [搜索关键词]", file=sys.stderr)
        return 1
    return actions[action]()


if __name__ == "__main__":
    sys.exit(main())
