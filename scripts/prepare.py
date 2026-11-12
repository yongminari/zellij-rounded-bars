"""Overlay our two plugins and ribbon renderer onto the pinned upstream workspace."""
from pathlib import Path
import shutil
import sys

project, upstream = map(Path, sys.argv[1:])
for name in ("tab-bar", "status-bar"):
    target = upstream / "default-plugins" / name
    shutil.rmtree(target)
    shutil.copytree(project / "default-plugins" / name, target)
components = upstream / "zellij-tile/src/ui_components"
for name in ("rounded_text", "rounded_context"):
    shutil.copyfile(project / "support" / f"{name}.rs", components / f"{name}.rs")
text = components / "text.rs"
text.write_text(text.read_text() + '\ninclude!("rounded_text.rs");\n')
ribbon = components / "ribbon.rs"
s = ribbon.read_text()
needle = 'pub fn serialize_ribbon(text: &Text) -> String {\n'
assert s.count(needle) == 1, "Upstream ribbon API changed; review the renderer."
s = s.replace(needle, needle + '''    if let Some((colors, caps)) = ROUNDED_STYLE.with(|style| *style.borrow()) {
        return text.rounded_ribbon(colors, caps);
    }
''')
ribbon.write_text(s + '\ninclude!("rounded_context.rs");\n')
