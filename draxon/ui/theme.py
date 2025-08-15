from textual.app import App

class DraxonApp(App):
    CSS = """
    Screen {
        background: #1e1e2e;
        color: #cdd6f4;
        font: FiraCode;
        layers: base overlay;
    }

    Header {
        background: #181825;
        color: #cdd6f4;
        dock: top;
        height: 1;
        text-style: bold;
    }

    Footer {
        background: #181825;
        color: #a6adc8;
        dock: bottom;
        height: 1;
    }

    #main-container {
        layout: horizontal;
        height: 100%;
    }

    #left-panel {
        width: 1fr;
        padding: 1;
        border-right: solid #45475a;
    }

    #history-panel {
        width: 30%;
        padding: 1;
        background: #181825;
        display: block;
        transition: offset 500ms in_out_cubic;
    }

    #history-panel.-hidden {
        display: none;
    }

    #history-panel > Label {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    Input, Select {
        margin-bottom: 1;
    }

    Button {
        width: 100%;
        margin-bottom: 1;
    }

    #action-buttons {
        height: auto;
        margin-top: 1;
    }

    #action-buttons > Button {
        width: 1fr;
        margin: 0 1;
    }
    
    #action-buttons > Button:first-child {
        margin-left: 0;
    }
    
    #action-buttons > Button:last-child {
        margin-right: 0;
    }

    PathSelector {
        margin-bottom: 1;
    }
    
    DownloadProgress {
        margin-top: 1;
        height: 5;
    }

    ProgressBar {
        margin-top: 1;
        background: #313244;
        color: #89b4fa;
    }

    DirectoryTree {
        width: 100%;
        height: 100%;
        padding: 1;
    }
    """