thread_local! {
    static ROUNDED_STYLE: std::cell::RefCell<Option<(zellij_utils::data::Styling, bool)>> = const { std::cell::RefCell::new(None) };
}

pub fn configure_rounded_ribbons(colors: zellij_utils::data::Styling, caps: bool) {
    ROUNDED_STYLE.with(|style| *style.borrow_mut() = Some((colors, caps)));
}
