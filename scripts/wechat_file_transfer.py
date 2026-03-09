#!/usr/bin/env python3
"""
WeChat File Transfer verification script.

Uses the search box to find "File Transfer" and sends "Hello". For Chinese WeChat locale, set FILE_TRANSFER to the contact name used in your locale.

Flow:
  1. Connect to WeChat window
  2. Click/focus the left-side search box (at your marked position)
  3. Type "File Transfer" (or the contact name for your locale)
  4. Select the search result
  5. Send the message

- Windows: Uses pywinauto (pip install pywinauto)
- macOS:   Uses atomacos + pyperclip; requires Accessibility permission in System Settings > Privacy & Security > Accessibility

Prerequisites: WeChat is logged in and the main window is open (not minimized)

Run:
  python scripts/wechat_file_transfer.py
  python scripts/wechat_file_transfer.py --dump   # Mac: export a11y tree for debugging
"""

import sys

# Contact name: "File Transfer" in English WeChat; for other locales, use the contact name shown in WeChat
FILE_TRANSFER = "File Transfer"


def _dump_a11y(elem, depth=0, max_depth=5, max_items=80):
    """Recursively export a11y tree (for debugging)."""
    if depth > max_depth or max_items <= 0:
        return 0
    count = 0
    try:
        role = getattr(elem, "AXRole", "?")
        title = getattr(elem, "AXTitle", "") or ""
        desc = getattr(elem, "AXDescription", "") or ""
        val = getattr(elem, "AXValue", "") or ""
        label = title or desc or val
        key = " ***" if not label or "file" in (label or "").lower() or "transfer" in (label or "").lower() else ""
        if label or depth == 0:
            count += 1
            ident = "  " * depth
            print(f"{ident}{role}: {repr(label or role)[:70]}{key}")
            max_items -= 1
        for child in getattr(elem, "AXChildren", []) or []:
            c = _dump_a11y(child, depth + 1, max_depth, max_items)
            count += c
            max_items -= c
            if max_items <= 0:
                break
    except Exception:
        pass
    return count


def main_win():
    try:
        from pywinauto.application import Application
        from pywinauto.keyboard import send_keys
    except ImportError as e:
        print("Please install: pip install pywinauto")
        print(f"Error: {e}")
        sys.exit(1)

    WECHAT_PATHS = [
        r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
        r"C:\Program Files\Tencent\WeChat\WeChat.exe",
        r"D:\Program Files\Tencent\WeChat\WeChat.exe",
    ]
    WECHAT_TITLE = "WeChat"
    WECHAT_CLASS = "WeChatMainWndForPC"

    print("1. Connecting to WeChat...")
    app = None
    for path in WECHAT_PATHS:
        try:
            app = Application(backend="uia").connect(path=path)
            print(f"   Connected via path: {path}")
            break
        except Exception:
            continue

    if app is None:
        try:
            app = Application(backend="uia").connect(title_re=f".*{WECHAT_TITLE}.*")
            print("   Connected via window title")
        except Exception as e:
            print(f"   Connection failed: {e}")
            print("   Ensure WeChat is logged in and the window is open (not minimized)")
            sys.exit(1)

    win = app.window(title_re=f".*{WECHAT_TITLE}.*", class_name=WECHAT_CLASS)
    win.wait("ready", timeout=5)

    handle = win.handle
    print(f"2. WeChat window handle: {handle} (0x{handle:x})")

    print("3. Looking for 'File Transfer'...")
    file_transfer = None

    # First try to find it directly (may already be in the list)
    try:
        file_transfer = win.child_window(title=FILE_TRANSFER, control_type="ListItem")
        file_transfer.wait("ready", timeout=2)
        file_transfer.click_input()
        print(f"   Found and clicked '{FILE_TRANSFER}'")
    except Exception:
        print("   Not found in visible list, trying search...")
        file_transfer = None

    # If not found, use the search box
    if file_transfer is None:
        try:
            # WeChat search box is usually at the top of the left chat list
            print("   Locating search box...")

            # Method 1: Find by Edit control type (search box is usually Edit)
            search_edit = None
            try:
                search_edit = win.child_window(control_type="Edit", found_index=0)
                search_edit.wait("ready", timeout=2)
            except Exception:
                pass

            # Method 2: If method 1 fails, try by name
            if search_edit is None:
                try:
                    search_edit = win.child_window(title="Search", control_type="Edit")
                    search_edit.wait("ready", timeout=2)
                except Exception:
                    pass

            # Method 3: Use Ctrl+F to activate search
            if search_edit is None:
                print("   Using Ctrl+F to activate search...")
                win.set_focus()
                send_keys("^f")
                import time
                time.sleep(0.5)
                try:
                    search_edit = win.child_window(control_type="Edit", found_index=0)
                    search_edit.wait("ready", timeout=2)
                except Exception:
                    pass

            if search_edit is None:
                raise Exception("Could not locate search box")

            # Click search box and type
            search_edit.click_input()
            search_edit.set_edit_text("")
            search_edit.type_keys(FILE_TRANSFER, with_spaces=False)
            print(f"   Typed in search box: {FILE_TRANSFER}")

            # Wait for search results
            import time
            time.sleep(1)

            # Find "File Transfer" in search results
            try:
                result_item = win.child_window(title=FILE_TRANSFER, control_type="ListItem")
                result_item.wait("ready", timeout=3)
                result_item.click_input()
                print(f"   Clicked search result '{FILE_TRANSFER}'")
            except Exception:
                # If no exact match, try Enter to select first result
                print("   No exact match, sending Enter to select first result...")
                send_keys("{ENTER}")

            # Wait to enter chat window
            print("   Waiting to enter chat window...")
            import time
            time.sleep(2)

        except Exception as e:
            print(f"   Search failed: {e}")
            print("   Ensure WeChat is logged in and you can manually find 'File Transfer'")
            sys.exit(1)

    print("5. Typing and sending 'Hello' in chat...")
    try:
        edit_msg = win.child_window(title=FILE_TRANSFER, control_type="Edit")
        edit_msg.wait("ready", timeout=3)
        edit_msg.click_input()
        edit_msg.set_edit_text("")
        edit_msg.type_keys("Hello", with_spaces=False)
        send_keys("{ENTER}")
        print("   Sent: Hello")
    except Exception as e:
        print(f"   Send failed: {e}")
        sys.exit(1)

    print("Done.")


def _osx_keystroke(keys: str, *, cmd: bool = False, shift: bool = False, alt: bool = False):
    """Send keystrokes to foreground app via AppleScript; more reliable than pyautogui."""
    import subprocess

    if keys in ("\r", "\n", "enter"):
        script = 'tell application "System Events" to key code 36'
    else:
        mods = []
        if cmd:
            mods.append("command down")
        if shift:
            mods.append("shift down")
        if alt:
            mods.append("option down")
        mod_str = " using {" + ", ".join(mods) + "}" if mods else ""
        esc = keys.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{esc}"{mod_str}'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        err = ((e.stderr or b"") + (e.stdout or b"")).decode(errors="ignore")
        if "not allowed to send keystrokes" in err or "1002" in err:
            print("\n[Permission error] macOS does not allow sending keystrokes. Do the following:")
            print("  1. Open System Settings > Privacy & Security > Accessibility")
            print("  2. Click + to add and enable: Terminal / Cursor (the app running this script)")
            print("  3. If already added, remove and re-add, then ensure it is enabled")
            print("  4. Run this script again")
            sys.exit(1)
        raise


def main_darwin():
    import time

    try:
        import atomacos
        import pyperclip
    except ImportError:
        print("Please install: pip install atomacos pyperclip")
        sys.exit(1)

    WECHAT_BUNDLE_ID = "com.tencent.xinWeChat"

    print("1. Activating WeChat...")
    try:
        wechat = atomacos.getAppRefByBundleId(WECHAT_BUNDLE_ID)
        wechat.activate()
        print("   Brought WeChat to front")
    except Exception as e:
        print(f"   Connection failed: {e}")
        print("   Ensure WeChat is open.")
        sys.exit(1)

    time.sleep(1.5)  # Ensure WeChat has focus before sending keys

    # WeChat left chat list search: Cmd+F = focus list search box (not global search Cmd+Shift+F)
    print("2. Focusing left search box (Cmd+F)...")
    _osx_keystroke("f", cmd=True)
    time.sleep(1.5)

    print("3. Pasting 'File Transfer' into search box...")
    pyperclip.copy(FILE_TRANSFER)
    _osx_keystroke("v", cmd=True)
    time.sleep(1.5)

    print("4. Pressing Enter to enter chat window...")
    _osx_keystroke("enter")
    time.sleep(2.5)  # Wait for chat window to load

    print("5. Sending 'Hello'...")
    pyperclip.copy("Hello")
    _osx_keystroke("v", cmd=True)
    time.sleep(0.5)
    _osx_keystroke("enter")

    print("Done.")


def main_darwin_dump():
    """Export WeChat a11y tree to find actual attributes of 'File Transfer' and other elements."""
    try:
        import atomacos
    except ImportError:
        print("Please install: pip install atomacos")
        sys.exit(1)

    WECHAT_BUNDLE_ID = "com.tencent.xinWeChat"
    print("Connecting to WeChat and exporting a11y structure...\n")
    try:
        wechat = atomacos.getAppRefByBundleId(WECHAT_BUNDLE_ID)
        wechat.activate()
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    print("--- First 80 elements (prioritizing those with 'file' or 'transfer') ---\n")
    n = _dump_a11y(wechat, max_depth=6, max_items=80)
    print(f"\nExported {n} elements. Look for role/title containing 'File Transfer' and adjust script lookup.")


def main():
    dump_mode = "--dump" in sys.argv or "-d" in sys.argv
    if sys.platform == "win32":
        if dump_mode:
            print("--dump is macOS only")
            sys.exit(1)
        main_win()
    elif sys.platform == "darwin":
        if dump_mode:
            main_darwin_dump()
        else:
            main_darwin()
    else:
        print(f"Unsupported platform: {sys.platform}")
        sys.exit(1)


if __name__ == "__main__":
    main()
