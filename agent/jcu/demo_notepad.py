"""M2 演示：启动记事本 → 找到真正的窗口进程 → 跑 dry-run 主循环 → 清理。

Win11 的 notepad.exe 是跳板：真正持有窗口的是另一个 Store 版 Notepad.exe 进程，
且窗口标题可能是英文（如 '无标题 - Notepad'），按标题匹配不可靠，按进程直连最稳。

用法：cd agent && python -m jcu.demo_notepad
"""

import subprocess
import time


def _find_real_notepad_pid(stub_pid: int, wait_s: int = 20) -> int:
    """轮询 tasklist，找到非跳板的 Notepad.exe 进程。"""
    deadline = time.time() + wait_s
    while time.time() < deadline:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Notepad.exe", "/FO", "CSV"],
            capture_output=True, text=True, errors="ignore",
        ).stdout
        pids = []
        for line in out.splitlines()[1:]:
            if "Notepad.exe" in line:
                fields = line.strip('"').split('","')
                if len(fields) >= 2 and fields[1].isdigit():
                    pids.append(int(fields[1]))
        real = [p for p in pids if p != stub_pid]
        if real:
            return real[0]
        time.sleep(1)
    raise RuntimeError("20 秒内未发现真正的 Notepad 窗口进程")


def main() -> None:
    stub = subprocess.Popen(["notepad.exe"])
    print(f"notepad 跳板进程 pid={stub.pid}，等待真正的窗口进程...")
    real_pid = _find_real_notepad_pid(stub.pid)
    print(f"真正的记事本进程 pid={real_pid}")

    from pywinauto import Application

    title = Application(backend="uia").connect(process=real_pid, timeout=15).top_window().window_text()
    print(f"窗口标题: {title!r}")

    from .loop import run_task

    try:
        ok = run_task("在记事本里输入 hello world", process=real_pid)
        print("任务结果:", "完成" if ok else "未完成")
    finally:
        subprocess.run(["taskkill", "/PID", str(real_pid), "/F"], capture_output=True)
        print("演示结束，记事本已关闭")


if __name__ == "__main__":
    main()
