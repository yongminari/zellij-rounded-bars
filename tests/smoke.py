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
if "--custom-bindings" in sys.argv[3:]:
    with testconfig.open("a") as config:
        config.write('''keybinds {
    unbind "Ctrl g"
    shared_except "locked" {
        bind "Ctrl Shift h" { SwitchToMode "Locked"; }
        bind "Alt n" { NewPane "Right"; }
        bind "Alt h" { MoveFocusOrTab "Left"; }
        bind "Alt l" { MoveFocusOrTab "Right"; }
        bind "Alt j" { MoveFocus "Down"; }
        bind "Alt k" { MoveFocus "Up"; }
    }
    locked {
        bind "Ctrl Shift h" { SwitchToMode "Normal"; }
    }
}
''')
master, slave = pty.openpty()
fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 180, 0, 0))
env = {
    k: v for k, v in os.environ.items() if k not in ["ZELLIJ", "ZELLIJ_SESSION_NAME"]
}
env["TERM"] = "xterm-256color"
# Exercise first-launch permissions independently of the developer's cache.
for kind in ("CONFIG", "CACHE", "DATA"):
    env[f"XDG_{kind}_HOME"] = str(Path(workspace.name) / kind.lower())


def setup_tty():
    os.setsid()
    fcntl.ioctl(slave, termios.TIOCSCTTY, 0)


p = subprocess.Popen(
    ["zellij", "--config-dir", workspace.name, "--config", str(testconfig), "--session", name],
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


def dump(label):
    for row in (screen.display[0], screen.display[-1]):
        assert row.startswith("") and row.endswith(""), (label, row)
        assert "" not in row[1:], (label, "internal left-facing cap", row)
        assert not any(ch in row for ch in ""), (label, row)
    print(
        label, repr(screen.display[0]), repr(screen.display[-1]), sep="\n", flush=True
    )


def wait_for_tab(title, timeout=15):
    deadline = time.monotonic() + timeout
    while title not in screen.display[0] and time.monotonic() < deadline:
        pump(0.1)
    assert title in screen.display[0], ("Tab did not appear", title, screen.display)


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
    # The first tab's left edge is a right-facing cutout: outer foreground,
    # inner background. Checking colors prevents an outward cap on both sides.
    edge_col = screen.display[0].index("")
    assert screen.buffer[0][edge_col].fg == screen.buffer[0][0].fg
    assert screen.buffer[0][edge_col].bg == screen.buffer[0][edge_col + 1].bg
    os.write(master, b"\x10")
    pump(2)
    dump("PANE")
    assert "Rename" in screen.display[-1]
    os.write(master, b"\x1b")
    pump(1)
    os.write(master, b"\x14")
    pump(0.3)
    os.write(master, b"n")
    pump(3)
    dump("SECOND TAB")
    assert "Tab #2" in screen.display[0]
    # Exercise the shifted new-tab button with an actual mouse event.
    pump(3)
    col = screen.display[0].index("+") + 1
    os.write(master, f"\x1b[<35;{col};1M".encode())
    pump(0.5)
    dump("HOVER NEW TAB")
    os.write(master, f"\x1b[<0;{col};1M".encode())
    pump(0.2)
    os.write(master, f"\x1b[<0;{col};1m".encode())
    wait_for_tab("Tab #3")
    dump("MOUSE NEW TAB")
    lock_key = b"\x1b[104;6u" if "--custom-bindings" in sys.argv[3:] else b"\x07"
    os.write(master, lock_key)
    pump(2)
    dump("LOCKED")
    assert "LOCK" in screen.display[-1] and "PANE" not in screen.display[-1]
    assert screen.display[-1].startswith("") and screen.display[-1].endswith("")
    assert not any(ch in screen.display[0] + screen.display[-1] for ch in "<>")
    os.write(master, lock_key)
    pump(1)
    for width in (100, 80, 60, 40, 20, 10, 6, 180):
        screen.resize(lines=30, columns=width)
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 30, width, 0, 0))
        pump(1)
        row = screen.display[-1]
        assert row.startswith("") and row.endswith(""), (width, row)
        assert any(ch.isalnum() for ch in row), ("Empty narrow status bar", width, row)
        if width == 40:
            assert "Pa" in row, ("Missing pane shortcut", width, row)
        print("RESIZE", width, repr(row), flush=True)
    assert "PANE" in screen.display[-1] and "RESIZE" in screen.display[-1]
    for mode, label in (("pane", "PANE"), ("locked", "LOCK")):
        subprocess.run(
            ["zellij", "--session", name, "action", "switch-mode", mode],
            env=env, check=True,
        )
        pump(0.5)
        for width in (40, 10, 180):
            screen.resize(lines=30, columns=width)
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 30, width, 0, 0))
            pump(1)
            row = screen.display[-1]
            assert row.startswith("") and row.endswith(""), (label, width, row)
            assert label in row, (label, width, row)

    print("PASS", flush=True)
finally:
    subprocess.run(
        ["zellij", "kill-session", name],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    p.wait(timeout=5)
    os.close(master)
    subprocess.run(
        ["zellij", "delete-session", name],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    workspace.cleanup()
