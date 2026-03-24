from qfluentwidgets import CardWidget, PrimaryPushButton, PushButton, TextEdit


APP_STYLESHEET = """
MSFluentWindow {
    background: #f5f7fb;
}

QWidget#dashboardPage,
QWidget#schedulePage,
QWidget#logPage,
QWidget#settingsPage,
QWidget[objectName^="gamePage_"] {
    background: transparent;
}

CardWidget {
    background: rgba(255, 255, 255, 0.96);
    border: 1px solid rgba(17, 24, 39, 0.08);
    border-radius: 18px;
}

SubtitleLabel {
    color: #132238;
}

BodyLabel {
    color: #23364d;
}

CaptionLabel {
    color: #6c7a89;
}

LineEdit,
ComboBox,
SpinBox,
TableView,
TextEdit {
    border-radius: 12px;
}

PushButton,
PrimaryPushButton,
ToolButton {
    min-height: 38px;
}

QTableView {
    border: 1px solid rgba(17, 24, 39, 0.08);
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.96);
    gridline-color: rgba(17, 24, 39, 0.06);
}

QHeaderView::section {
    background: rgba(244, 247, 250, 0.92);
    border: none;
    border-bottom: 1px solid rgba(17, 24, 39, 0.06);
    padding: 10px 12px;
    color: #435266;
    font-weight: 600;
}
"""


def apply_card_style(card: CardWidget, accent: bool = False) -> None:
    if accent:
        card.setStyleSheet(
            "CardWidget {"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #f2fbff, stop:1 #f3f8ff);"
            "border:1px solid rgba(16, 113, 184, 0.14);"
            "border-radius:18px;"
            "}"
        )
    else:
        card.setStyleSheet(
            "CardWidget {"
            "background: rgba(255, 255, 255, 0.96);"
            "border: 1px solid rgba(17, 24, 39, 0.08);"
            "border-radius: 18px;"
            "}"
        )


def apply_button_style(button: PushButton | PrimaryPushButton, prominent: bool = False) -> None:
    button.setMinimumHeight(40 if prominent else 38)


def apply_log_style(text_edit: TextEdit) -> None:
    text_edit.setStyleSheet(
        "background: rgba(250, 251, 253, 0.98);"
        "border: 1px solid rgba(17, 24, 39, 0.08);"
        "border-radius: 16px;"
        "font-family: 'Cascadia Code', 'Consolas', monospace;"
        "font-size: 12px;"
        "padding: 8px;"
    )
