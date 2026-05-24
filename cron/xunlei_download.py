#!/usr/bin/env python3
"""从 spider magnet_link/links/list API 拉取 thunder 链接，并吊起本机迅雷下载。"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.parsers import thunder_to_magnet  # noqa: E402
from app.settings import MIN_SIZE_GB, SPIDER_MAGNET_LINK_LIST_URL, XUNLEI_LIST_PAGE_SIZE  # noqa: E402
from app.spider_client import fetch_all_links  # noqa: E402
THUNDER_AGENT_IDS = (
    "ThunderAgent.Agent.1",
    "ThunderAgent.ThunderAgent.1",
    "ThunderAgent.Agent",
)

# Mac 静默偏好（写入 com.xunlei.Thunder，需重启迅雷后完全生效）
_MAC_SILENT_PREFS: tuple[tuple[str, str], ...] = (
    ("automaticStartTask", "true"),
    ("showNewTaskPanel", "false"),
    ("silentCreatingBTTask", "true"),
    ("enableMagnetsAtuoCompletion", "true"),
)

# 可选：UI 自动点确认（需终端「辅助功能」权限，默认不用）
_MAC_UI_CONFIRM_SCRIPT = """
on run argv
    set waitSec to (item 1 of argv) as number
    delay waitSec
    tell application "System Events"
        if not (exists process "Thunder") then return
        tell process "Thunder"
            set frontmost to true
            repeat with btnName in {"立即下载", "下载", "确定", "开始下载"}
                repeat with w in windows
                    try
                        if exists (button btnName of w) then
                            click button btnName of w
                            return
                        end if
                    end try
                end repeat
            end repeat
            try
                key code 36
            end try
        end tell
    end tell
end run
"""


def group_links_by_code(links: list[dict]) -> list[tuple[str, list[dict]]]:
    """保持 API 返回顺序，按番号分组。"""
    groups: dict[str, list[dict]] = defaultdict(list)
    order: list[str] = []
    for item in links:
        code = (item.get("code") or "").strip()
        if not code:
            continue
        if code not in groups:
            order.append(code)
        groups[code].append(item)
    return [(code, groups[code]) for code in order]


def launch_code_tasks(
    items: list[dict],
    method: str,
    *,
    save_path: str,
    auto: bool,
    confirm_delay: float,
    mac_ui_confirm: bool,
    delay: float,
) -> int:
    """吊起一个番号下的全部任务，返回成功条数。"""
    with_url = [it for it in items if (it.get("thunder_url") or "").strip()]
    if not with_url:
        return 0

    urls = [(it.get("thunder_url") or "").strip() for it in with_url]

    if method == "com":
        _launch_windows_com_batch(urls, save_path=save_path, auto=auto)
        return len(urls)

    ok = 0
    for i, it in enumerate(with_url):
        url = (it.get("thunder_url") or "").strip()
        try:
            print(f"  → {url[:72]}{'…' if len(url) > 72 else ''}")
            launch_thunder_url(
                url,
                method,
                save_path=save_path,
                auto=auto,
                confirm_delay=confirm_delay,
                mac_ui_confirm=mac_ui_confirm,
            )
            ok += 1
        except Exception as exc:
            print(f"    失败: {exc}", file=sys.stderr)
        if i < len(with_url) - 1 and delay > 0:
            time.sleep(delay)
    return ok


def task_url(thunder_url: str, prefer_magnet: bool) -> str:
    if prefer_magnet:
        magnet = thunder_to_magnet(thunder_url)
        if magnet:
            return magnet
    return thunder_url


def resolve_method(method: str, auto: bool) -> str:
    if method != "auto":
        return method
    if platform.system() == "Windows" and auto:
        return "com"
    if platform.system() == "Darwin" and auto:
        return "mac"
    return "open"


_mac_prefs_applied = False


def ensure_mac_auto_prefs() -> None:
    """写入迅雷静默/自动开始相关偏好（无需辅助功能权限）。"""
    global _mac_prefs_applied
    if _mac_prefs_applied:
        return
    for key, value in _MAC_SILENT_PREFS:
        subprocess.run(
            ["defaults", "write", "com.xunlei.Thunder", key, "-bool", value],
            check=False,
        )
    _mac_prefs_applied = True


def _mac_accessibility_ok() -> bool:
    probe = subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to return name of first application process',
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return probe.returncode == 0


def _mac_ui_confirm(confirm_delay: float) -> bool:
    if confirm_delay <= 0:
        return True
    result = subprocess.run(
        ["osascript", "-e", _MAC_UI_CONFIRM_SCRIPT, str(confirm_delay)],
        capture_output=True,
        text=True,
        timeout=confirm_delay + 15,
    )
    if result.returncode == 0:
        return True
    err = (result.stderr or result.stdout or "").strip()
    if "-25211" in err or "辅助访问" in err or "assistive access" in err.lower():
        print(
            "  辅助功能未授权，已跳过 UI 自动点击。"
            "可在「系统设置→隐私与安全性→辅助功能」勾选终端，"
            "或使用 --mac-ui-confirm 前先授权。",
            file=sys.stderr,
        )
    elif err:
        print(f"  UI 自动确认失败: {err}", file=sys.stderr)
    return False


def _print_mac_auto_hint(ui_confirm: bool) -> None:
    print(
        "Mac 静默：已写入迅雷偏好（自动开始、不弹主界面等）。"
        "任务可能在后台添加，请查看迅雷下载列表；"
        "若仍出现确认窗，请重启迅雷后再试，或加 --mac-ui-confirm；"
        "也可在迅雷「偏好设置→应用→基本设置→任务管理」"
        "取消「新建任务时显示主界面」。"
    )
    if ui_confirm:
        if _mac_accessibility_ok():
            print("Mac UI 确认：已启用（辅助功能已授权）。")
        else:
            print(
                "Mac UI 确认：未获得辅助功能权限，将仅依赖迅雷偏好静默添加。",
                file=sys.stderr,
            )


def _launch_mac_thunder(thunder_url: str) -> None:
    """Mac 迅雷注册 thunder:// 协议；先唤起客户端再投递链接。"""
    url = thunder_url.strip()
    if not url:
        raise ValueError("空的 thunder 链接")
    subprocess.run(["open", "-a", "Thunder"], check=False)
    time.sleep(0.3)
    result = subprocess.run(["open", url], capture_output=True, text=True)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"open 投递失败: {err or result.returncode}")


def _launch_mac_auto(
    thunder_url: str,
    *,
    confirm_delay: float,
    ui_confirm: bool,
) -> None:
    ensure_mac_auto_prefs()
    _launch_mac_thunder(thunder_url)
    if ui_confirm and _mac_accessibility_ok():
        _mac_ui_confirm(confirm_delay)


def _get_windows_agent():
    try:
        import win32com.client
    except ImportError as exc:
        raise SystemExit("Windows 自动下载需安装 pywin32：pip install pywin32") from exc

    last_exc: Exception | None = None
    for prog_id in THUNDER_AGENT_IDS:
        try:
            return win32com.client.Dispatch(prog_id)
        except Exception as exc:
            last_exc = exc
    raise RuntimeError(f"无法连接迅雷 COM：{last_exc}") from last_exc


def _launch_windows_com_batch(
    thunder_urls: list[str],
    *,
    save_path: str,
    auto: bool,
) -> None:
    agent = _get_windows_agent()
    start_mode = 1 if auto else 0
    for thunder_url in thunder_urls:
        url = task_url(thunder_url, prefer_magnet=True)
        agent.AddTask(url, "", save_path, "", "", start_mode, 0, 5)
    if auto and hasattr(agent, "CommitTasks2"):
        agent.CommitTasks2(1)
    else:
        agent.CommitTasks(0)


def launch_thunder_url(
    thunder_url: str,
    method: str,
    *,
    save_path: str = "",
    auto: bool = True,
    confirm_delay: float = 2.0,
    mac_ui_confirm: bool = False,
) -> None:
    if method == "com":
        _launch_windows_com_batch(
            [thunder_url], save_path=save_path, auto=auto
        )
        return
    if method == "mac":
        _launch_mac_auto(
            thunder_url,
            confirm_delay=confirm_delay,
            ui_confirm=mac_ui_confirm,
        )
        return

    url = task_url(thunder_url, prefer_magnet=auto)
    system = platform.system()
    if system == "Darwin":
        _launch_mac_thunder(thunder_url)
    elif system == "Windows":
        os.startfile(url)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", url], check=True)


def fetch_links_for_codes(
    client: httpx.Client,
    params: dict[str, Any],
    codes: list[str],
    *,
    list_url: str,
) -> list[dict]:
    """按番号逐个请求 list API 并合并结果（保持 --codes 顺序）。"""
    links: list[dict] = []
    for code in codes:
        code = code.strip()
        if not code:
            continue
        batch = fetch_all_links(
            client, {**params, "code": code}, list_url=list_url
        )
        links.extend(batch)
    return links


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="从 API 拉取 thunder 链接并吊起迅雷下载")
    p.add_argument("--min-size", type=float, default=MIN_SIZE_GB, help="最小体积 GB（含）")
    p.add_argument("--max-size", type=float, default=6.0, help="最大体积 GB（含）")
    p.add_argument("--page-size", type=int, default=XUNLEI_LIST_PAGE_SIZE, help="每页条数")
    p.add_argument("--create-start", default=None, help="入库起始时间")
    p.add_argument("--create-end", default=None, help="入库截止时间")
    p.add_argument(
        "--codes",
        nargs="*",
        metavar="CODE",
        help="仅下载指定番号（可多个，如 --codes MIDA-636 ABC-123）",
    )
    p.add_argument("--delay", type=float, default=1.5, help="同番号内多条 / 番号之间的间隔秒数")
    p.add_argument("--limit", type=int, default=0, help="最多添加条数，0 表示不限制")
    p.add_argument("--save-path", default="", help="保存目录（Windows COM）")
    p.add_argument(
        "--confirm-delay",
        type=float,
        default=2.0,
        help="配合 --mac-ui-confirm：等待新建任务窗出现后点「下载」的秒数",
    )
    p.add_argument(
        "--mac-ui-confirm",
        action="store_true",
        help="Mac 用辅助功能自动点确认（需授权；默认靠迅雷偏好静默添加）",
    )
    p.add_argument(
        "--method",
        choices=("auto", "open", "com", "mac"),
        default="auto",
        help="吊起方式：auto=按平台自动静默（默认），open=仅打开链接，com/mac=指定方式",
    )
    p.add_argument(
        "--no-auto",
        action="store_true",
        help="不自动确认/立即开始（等同手工确认）",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印链接，不实际吊起迅雷",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    auto = not args.no_auto
    method = resolve_method(args.method, auto)

    if method == "com" and platform.system() != "Windows":
        print("COM 仅 Windows，已改用 mac/open。", file=sys.stderr)
        method = "mac" if platform.system() == "Darwin" and auto else "open"
    if method == "mac" and platform.system() != "Darwin":
        method = "com" if platform.system() == "Windows" and auto else "open"

    params: dict[str, Any] = {
        "min_size": args.min_size,
        "max_size": args.max_size,
        "page_size": args.page_size,
    }
    if args.create_start:
        params["create_start"] = args.create_start
    if args.create_end:
        params["create_end"] = args.create_end

    codes = [c.strip() for c in (args.codes or []) if c.strip()]

    print(f"API: {SPIDER_MAGNET_LINK_LIST_URL}")
    code_hint = ", ".join(codes) if codes else "全部"
    print(
        f"筛选: 番号={code_hint} min_size={args.min_size} max_size={args.max_size} "
        f"方式={method} 自动确认={'是' if auto else '否'}"
    )

    if method == "mac" and not args.dry_run:
        ensure_mac_auto_prefs()
        _print_mac_auto_hint(args.mac_ui_confirm)

    with httpx.Client(timeout=30.0) as client:
        try:
            if codes:
                links = fetch_links_for_codes(
                    client, params, codes, list_url=SPIDER_MAGNET_LINK_LIST_URL
                )
            else:
                links = fetch_all_links(
                    client, params, list_url=SPIDER_MAGNET_LINK_LIST_URL
                )
        except httpx.HTTPError as exc:
            print(f"请求失败: {exc}", file=sys.stderr)
            return 1

        if not links:
            print("没有符合条件的链接。")
            return 0

        if args.limit > 0:
            links = links[: args.limit]

        groups = group_links_by_code(links)
        print(
            f"共 {len(links)} 条 / {len(groups)} 个番号，"
            f"{'预览' if args.dry_run else '按番号添加'}…"
        )

        if args.dry_run:
            for gi, (code, items) in enumerate(groups, 1):
                print(f"[{gi}] {code}（{len(items)} 条）")
                for item in items:
                    url = (item.get("thunder_url") or "").strip()
                    size = item.get("total_size_text") or item.get("size_gb")
                    print(f"  {size} {task_url(url, prefer_magnet=auto) if url else ''}")
            print(f"完成：{len(links)} 条 / {len(groups)} 个番号")
            return 0

        ok = 0
        total = len(links)
        for gi, (code, items) in enumerate(groups, 1):
            n_task = sum(
                1 for it in items if (it.get("thunder_url") or "").strip()
            )
            print(f"[{gi}/{len(groups)}] {code}（{n_task} 条）")
            try:
                ok += launch_code_tasks(
                    items,
                    method,
                    save_path=args.save_path,
                    auto=auto,
                    confirm_delay=args.confirm_delay,
                    mac_ui_confirm=args.mac_ui_confirm,
                    delay=args.delay,
                )
            except Exception as exc:
                print(f"  番号失败: {exc}", file=sys.stderr)
            if gi < len(groups) and args.delay > 0:
                time.sleep(args.delay)

    print(f"完成：成功 {ok}/{total}")
    return 0 if ok == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
