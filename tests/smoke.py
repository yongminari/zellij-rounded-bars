import os, pty, fcntl, termios, struct, subprocess, select, time, re, sys
from pathlib import Path
import pyte
import tempfile

package = Path(sys.argv[1]).resolve()
theme = sys.argv[2] if len(sys.argv) > 2 else "everforest-dark"
workspace = tempfile.TemporaryDirectory(prefix="zrb-test-")
name = "zrb-test-" + str(os.getpid())
testconfig = Path(workspace.name) / "config.kdl"
testconfig.write_text(f'''theme "{theme}"
default_shell "sh"
show_startup_tips false
plugins {{
    tab-bar location="file:{package}/rounded-tab-bar.wasm"
    status-bar location="file:{package}/rounded-status-bar.wasm"
}}
''')
master, slave = pty.openpty()
fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 180, 0, 0))
env = {
    k: v for k, v in os.environ.items() if k not in ["ZELLIJ", "ZELLIJ_SESSION_NAME"]
}
env["TERM"] = "xterm-256color"


def setup_tty():
    os.setsid()
    fcntl.ioctl(slave, termios.TIOCSCTTY, 0)


p = subprocess.Popen(
    ["zellij", "--config", str(testconfig), "--session", name],
    stdin=slave,
    stdout=slave,
    stderr=slave,
    env=env,
    preexec_fn=setup_tty,
)
os.close(slave)


class Screen(pyte.Screen):
    def report_device_status(self, *args, **kwargs):
        pass

    def report_device_attributes(self, *args, **kwargs):
        pass


screen = Screen(180, 30)
stream = pyte.Stream(screen)


def pump(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if select.select([master], [], [], 0.1)[0]:
            try:
                data = os.read(master, 1048576).decode("utf-8", "replace")
            except OSError:
                break
            data = re.sub(r"\x1bP.*?\x1b\\", "", data, flags=re.S)
            stream.feed(data)


def action(*args):
    subprocess.run(
        ["zellij", "--session", name, "action", *args],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    pump(2)


def dump(label):
    print(
        label, repr(screen.display[0]), repr(screen.display[-1]), sep="\n", flush=True
    )


try:
    for _ in range(25):
        pump(1)
        if screen.display[0].startswith("") and screen.display[-1].startswith(""):
            break
        for row, line in enumerate(screen.display):
            if "Allow?" in line:
                col = line.index("(y/n)") + 2
                os.write(
                    master, f"\x1b[<0;{col};{row + 1}M\x1b[<0;{col};{row + 1}m".encode()
                )
                pump(0.2)
                os.write(master, b"y")
                pump(0.2)
    pump(3)
    dump("NORMAL")
    assert not any(ch in screen.display[0] + screen.display[-1] for ch in "<>")
    assert screen.display[0].startswith("") and screen.display[0].endswith("")
    assert screen.display[-1].startswith("") and screen.display[-1].endswith("")
    assert "PANE" in screen.display[-1] and "RESIZE" in screen.display[-1]
    os.write(master, b"\x10")
    pump(2)
    dump("PANE")
    assert "Rename" in screen.display[-1]
    os.write(master, b"\x1b")
    pump(1)
    action("new-tab", "--name", "second")
    dump("SECOND TAB")
    assert "second" in screen.display[0]
    # Exercise the shifted new-tab button with an actual mouse event.
    col = screen.display[0].index("+") + 1
    pump(3)
    os.write(master, f"\x1b[<0;{col};1M".encode())
    pump(0.2)
    os.write(master, f"\x1b[<0;{col};1m".encode())
    pump(3)
    dump("MOUSE NEW TAB")
    assert "Tab #3" in screen.display[0]
    os.write(master, b"\x07")
    pump(2)
    dump("LOCKED")
    assert "LOCK" in screen.display[-1] and "PANE" not in screen.display[-1]
    assert screen.display[-1].startswith("") and screen.display[-1].endswith("")
    assert not any(ch in screen.display[0] + screen.display[-1] for ch in "<>")
    print("PASS", flush=True)
finally:
    subprocess.run(
        ["zellij", "kill-session", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    p.wait(timeout=5)
    os.close(master)
    subprocess.run(
        ["zellij", "delete-session", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    workspace.cleanup()
