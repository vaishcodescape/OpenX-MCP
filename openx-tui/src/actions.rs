//! User and system actions.

#[derive(Clone, Debug)]
pub enum Action {
    Quit,
    Char(char),
    Backspace,
    ClearInput,
    Submit,
    CancelStreaming,
    UnfocusInput,

    ChatScrollPageUp,
    ChatScrollPageDown,
    ChatScrollTop,
    ChatScrollBottom,

    HistoryUp,
    HistoryDown,

    PaletteShow,
    PaletteHide,
    PaletteUp,
    PaletteDown,
    PaletteSelect,
}

