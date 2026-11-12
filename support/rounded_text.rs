// Rounded rendering of the upstream Text component, preserving its styling indices.
impl Text {
    pub(super) fn rounded_ribbon(
        &self,
        colors: zellij_utils::data::Styling,
        caps: bool,
    ) -> String {
        use zellij_utils::data::PaletteColor;
        fn color(value: PaletteColor, background: bool) -> String {
            let prefix = if background { 48 } else { 38 };
            match value {
                PaletteColor::Rgb((r, g, b)) => format!("\x1b[{prefix};2;{r};{g};{b}m"),
                PaletteColor::EightBit(index) => format!("\x1b[{prefix};5;{index}m"),
            }
        }
        let declaration = if self.selected && !self.disabled {
            colors.ribbon_selected
        } else {
            colors.ribbon_unselected
        };
        let edge = format!("\x1b[0m{}{}", color(declaration.background, false), color(colors.text_unselected.background, true));
        let body = format!("\x1b[0m{}{}{}", color(declaration.base, false), color(declaration.background, true), if self.disabled { "\x1b[3m" } else { "\x1b[1m" });
        let mut output = format!("{}{}{} ", edge, if caps { "" } else { "" }, body);
        let emphasis = [declaration.emphasis_0, declaration.emphasis_1, declaration.emphasis_2, declaration.emphasis_3];
        for (index, ch) in self.text.chars().enumerate() {
            output.push_str(&body);
            if !self.disabled {
                for (level, fg) in emphasis.iter().enumerate() {
                    if self.indices.get(level).is_some_and(|indices| indices.contains(&index)) {
                        output.push_str(&color(*fg, false));
                        break;
                    }
                }
                if self.indices.get(4).is_some_and(|indices| indices.contains(&index)) { output.push_str("\x1b[2m"); }
                if self.indices.get(5).is_some_and(|indices| indices.contains(&index)) { output.push_str("\x1b[22m"); }
            }
            output.push(ch);
        }
        output.push_str(&format!("{} {}{}\x1b[0m", body, edge, if caps { "" } else { "" }));
        output
    }
}
