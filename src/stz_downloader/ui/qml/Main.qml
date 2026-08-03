import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import QtQuick.Layouts

ApplicationWindow {
    id: win
    visible: true
    width: 860
    height: 560
    minimumWidth: 680
    minimumHeight: 400
    title: "STZ Downloader"
    color: "#0f1115"

    readonly property color accent: "#4c8dff"
    readonly property color accentHover: Qt.lighter("#4c8dff", 1.15)
    readonly property color accentDown: Qt.darker("#4c8dff", 1.2)
    readonly property color surface: "#181b22"
    readonly property color surfaceAlt: "#1f232c"
    readonly property color textMain: "#e7e9ee"
    readonly property color textDim: "#8b919e"

    function fmtSize(bytes) {
        if (bytes <= 0) return "0 B"
        var u = ["B", "KB", "MB", "GB", "TB"]
        var i = Math.floor(Math.log(bytes) / Math.log(1024))
        return (bytes / Math.pow(1024, i)).toFixed(1) + " " + u[i]
    }

    function fmtDuration(seconds) {
        seconds = Math.max(0, Math.floor(seconds))
        var h = Math.floor(seconds / 3600)
        var m = Math.floor((seconds % 3600) / 60)
        var s = seconds % 60
        if (h > 0) return h + "h " + m + "m"
        if (m > 0) return m + "m " + s + "s"
        return s + "s"
    }

    function statusLabel(s) {
        return i18n.strings["status_" + s] || s
    }

    // Minimal %1/%2 placeholder substitution for translated strings.
    function fmt(template, a, b) {
        return (template || "").replace("%1", a === undefined ? "" : a)
                               .replace("%2", b === undefined ? "" : b)
    }

    function submit() {
        var u = urlField.text.trim()
        if (u.length > 0) {
            backend.addUrl(u, connSpin.value)
            urlField.text = ""
        }
    }

    // Bring the window to the foreground (IDM-style) when a confirmation
    // arrives. Skip if already focused to avoid the native-window flicker
    // that toggling window flags causes on Windows.
    function bringToFront() {
        if (win.active)
            return
        if (win.visibility === Window.Minimized)
            win.visibility = Window.Windowed
        win.show()
        win.raise()
        win.requestActivate()
        win.flags = win.flags | Qt.WindowStaysOnTopHint
        topmostTimer.restart()
        backend.flashTaskbar()
    }

    Timer {
        id: topmostTimer
        interval: 400
        onTriggered: win.flags = win.flags & ~Qt.WindowStaysOnTopHint
    }

    Connections {
        target: backend
        function onNewPendingArrived() { win.bringToFront() }
        function onPendingChanged() { confirmDialog.syncSelection() }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 14

        // --- Top bar: add a URL + connection count -------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Rectangle {
                Layout.fillWidth: true
                height: 44
                radius: 10
                color: win.surface
                border.color: urlField.activeFocus ? win.accent : "#2a2f3a"

                TextField {
                    id: urlField
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    verticalAlignment: TextInput.AlignVCenter
                    placeholderText: i18n.strings.url_placeholder
                    placeholderTextColor: win.textDim
                    color: win.textMain
                    background: Item {}
                    selectByMouse: true
                    onAccepted: win.submit()
                }
            }

            // connection count (segments). IDM default = 8.
            // Width follows its content so longer translated labels
            // (e.g. "Verbindungen") don't squeeze the steppers.
            Rectangle {
                id: connSpin
                height: 44
                implicitWidth: connRow.implicitWidth + 24
                radius: 10
                color: win.surface
                border.color: "#2a2f3a"

                property int value: 8  // clamped 1..16, read by submit()

                RowLayout {
                    id: connRow
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    spacing: 8

                    Text {
                        text: i18n.strings.connections
                        color: win.textDim
                        font.pixelSize: 12
                    }
                    StepBtn {
                        text: "−"
                        onClicked: connSpin.value = Math.max(1, connSpin.value - 1)
                    }
                    Text {
                        text: connSpin.value
                        color: win.textMain
                        font.pixelSize: 14
                        horizontalAlignment: Text.AlignHCenter
                        Layout.preferredWidth: 22
                    }
                    StepBtn {
                        text: "+"
                        onClicked: connSpin.value = Math.min(16, connSpin.value + 1)
                    }
                }
            }

            AccentBtn {
                text: i18n.strings.add
                implicitWidth: Math.max(110, implicitContentWidth)
                onClicked: win.submit()
            }

            // gear -> settings drawer
            Button {
                implicitHeight: 44
                implicitWidth: 44
                HoverHandler { cursorShape: Qt.PointingHandCursor }
                background: Rectangle {
                    radius: 10
                    color: parent.hovered ? win.surfaceAlt : win.surface
                    border.color: "#2a2f3a"
                }
                contentItem: Text {
                    text: "⚙"; color: win.textMain; font.pixelSize: 20
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                }
                onClicked: settingsDrawer.open()
            }
        }

        // --- Disk warning banner -------------------------------------
        // Advisory, never blocking: Content-Length lies, and the user may be
        // about to free space. Amber for "you will run short", red once the
        // guard has actually paused things.
        Rectangle {
            id: diskBanner
            readonly property var d: backend.disk
            readonly property bool tripped: d.available === true && d.guardTripped === true
            readonly property bool short_: d.available === true && (d.shortfall || 0) > 0

            Layout.fillWidth: true
            visible: tripped || short_
            implicitHeight: diskText.implicitHeight + 20
            radius: 10
            color: tripped ? "#3a1c1c" : "#3a331c"
            border.color: tripped ? "#ff6b6b" : "#e0b341"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 10

                Text {
                    text: diskBanner.tripped ? "⛔" : "⚠"
                    font.pixelSize: 15
                    color: diskBanner.tripped ? "#ff6b6b" : "#e0b341"
                }
                Text {
                    id: diskText
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    font.pixelSize: 12
                    color: diskBanner.tripped ? "#ffb4b4" : "#e8d7a0"
                    text: diskBanner.tripped
                          ? win.fmt(i18n.strings.disk_paused, diskBanner.d.path)
                          : win.fmt(i18n.strings.disk_short,
                                    win.fmtSize(diskBanner.d.shortfall || 0),
                                    diskBanner.d.path)
                }
            }
        }

        // --- List header: count + clear ------------------------------
        RowLayout {
            Layout.fillWidth: true
            visible: list.count > 0
            Text {
                text: list.count + " " + (list.count === 1 ? i18n.strings.item_one : i18n.strings.item_other)
                color: win.textDim
                font.pixelSize: 12
            }
            Item { Layout.fillWidth: true }
            OutlineBtn {
                text: i18n.strings.clear_finished
                onClicked: backend.clearFinished()
            }
        }

        // --- Download list -------------------------------------------
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            model: backend.downloads

            delegate: Rectangle {
                required property var modelData
                width: list.width
                height: 76
                radius: 12
                color: win.surface

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: modelData.name && modelData.name.length ? modelData.name : i18n.strings.getting_name
                            color: win.textMain
                            font.pixelSize: 14
                            elide: Text.ElideMiddle
                        }
                        Text {
                            text: win.statusLabel(modelData.status)
                            color: modelData.status === "active" ? win.accent
                                 : modelData.status === "error" ? "#ff6b6b" : win.textDim
                            font.pixelSize: 12
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 6
                        radius: 3
                        color: win.surfaceAlt
                        Rectangle {
                            height: parent.height
                            radius: 3
                            width: parent.width * Math.max(0, Math.min(1, modelData.progress))
                            color: modelData.status === "error" ? "#ff6b6b" : win.accent
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Text {
                            text: modelData.status === "error"
                                  ? modelData.error
                                  : win.fmtSize(modelData.completed) + " / " + win.fmtSize(modelData.total)
                            color: modelData.status === "error" ? "#ff6b6b" : win.textDim
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            Layout.maximumWidth: 360
                        }
                        Text {
                            visible: modelData.status === "active"
                            text: win.fmtSize(modelData.speed) + "/s"
                            color: win.textDim; font.pixelSize: 11
                        }
                        Text {
                            visible: modelData.status === "active" && modelData.speed > 0
                                     && modelData.total > modelData.completed
                            text: i18n.strings.eta + " "
                                  + win.fmtDuration((modelData.total - modelData.completed) / modelData.speed)
                            color: win.textDim; font.pixelSize: 11
                        }
                        Item { Layout.fillWidth: true }

                        ToolBtn {
                            text: "↗"
                            tip: i18n.strings.open_file
                            visible: modelData.status === "complete" && modelData.path && modelData.path.length > 0
                            onClicked: backend.openDownload(modelData.gid)
                        }
                        ToolBtn {
                            text: "📂"
                            tip: i18n.strings.reveal_file
                            visible: modelData.status === "complete" && modelData.path && modelData.path.length > 0
                            onClicked: backend.revealDownload(modelData.gid)
                        }
                        ToolBtn {
                            text: modelData.status === "paused" ? "▶" : "⏸"
                            visible: modelData.status === "active" || modelData.status === "paused"
                            tip: win.statusLabel(modelData.status === "paused" ? "active" : "paused")
                            onClicked: modelData.status === "paused"
                                       ? backend.resume(modelData.gid)
                                       : backend.pause(modelData.gid)
                        }
                        ToolBtn {
                            text: "✕"
                            tip: i18n.strings.cancel
                            onClicked: backend.cancel(modelData.gid)
                        }
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: list.count === 0
                text: i18n.strings.empty
                horizontalAlignment: Text.AlignHCenter
                color: win.textDim
                font.pixelSize: 14
            }
        }

        // --- Status bar ----------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Text {
                Layout.fillWidth: true
                visible: backend.status.length > 0
                text: backend.status
                color: "#ff6b6b"
                font.pixelSize: 11
                elide: Text.ElideRight
            }
            Item { Layout.fillWidth: backend.status.length === 0 }
            Text {
                visible: (backend.globalStats.numActive || 0) > 0
                         || (backend.globalStats.downloadSpeed || 0) > 0
                text: (backend.globalStats.numActive || 0) + " " + i18n.strings.active_downloads
                      + " · " + win.fmtSize(backend.globalStats.downloadSpeed || 0) + "/s"
                color: win.textDim
                font.pixelSize: 11
            }
        }
    }

    // ----- Settings drawer ------------------------------------------
    Drawer {
        id: settingsDrawer
        objectName: "settingsDrawer"
        edge: Qt.RightEdge
        width: Math.min(360, win.width)
        height: win.height
        background: Rectangle { color: win.surfaceAlt }

        property var s: ({})
        // Bumped on every edit to `s`. QML can't observe mutations of a plain
        // JS object, so bindings that read `s` reference this to re-evaluate.
        property int sVersion: 0
        // False until the bridge has actually delivered settings; gates Save.
        property bool settingsReady: false

        function loadFrom(source) {
            s = JSON.parse(JSON.stringify(source))
            sVersion++
            extList = (s.extensions || []).slice()
            extVersion++
            extWarning = ""
            settingsReady = Object.keys(s).length > 0
        }

        onOpened: loadFrom(backend.settings)

        // If settings arrive while the drawer is already open (slow bridge on
        // startup), adopt them instead of leaving the user with a dead Save.
        Connections {
            target: backend
            enabled: settingsDrawer.opened && !settingsDrawer.settingsReady
            function onSettingsChanged() { settingsDrawer.loadFrom(backend.settings) }
        }

        function setS(key, value) {
            s[key] = value
            sVersion++
        }

        function getS(key, fallback) {
            sVersion
            return s[key] === undefined ? fallback : s[key]
        }

        // --- extension list, edited as pills -------------------------
        property var extList: []
        property int extVersion: 0
        property string extWarning: ""
        // Index of the pill Backspace has *selected* but not yet deleted.
        // A tag field that deletes on the first Backspace loses entries before
        // the user realises what happened, so removal takes two presses.
        property int extArmed: -1

        function disarmExt() {
            if (extArmed !== -1) {
                extArmed = -1
                extVersion++
            }
        }

        function normalizeExt(raw) {
            var e = raw.trim().toLowerCase()
            if (e.length === 0) return ""
            if (e[0] !== ".") e = "." + e
            return e
        }

        // Returns true when it actually added something. Duplicates are
        // rejected with a message rather than silently swallowed -- otherwise
        // typing an extension that is already there looks like a broken field.
        function addExt(raw) {
            var e = normalizeExt(raw)
            if (e.length <= 1) return false
            if (extList.indexOf(e) !== -1) {
                extWarning = win.fmt(i18n.strings.ext_duplicate, e)
                dupTimer.restart()
                return false
            }
            extList.push(e)
            extVersion++
            extWarning = ""
            return true
        }

        function removeExtAt(i) {
            extList.splice(i, 1)
            extArmed = -1
            extVersion++
            extWarning = ""
        }

        // Backspace on an empty field: first press selects the last pill,
        // second press removes it. Returns true when the key was consumed.
        function backspaceExt() {
            if (extList.length === 0)
                return false
            var last = extList.length - 1
            if (extArmed === last) {
                removeExtAt(last)
            } else {
                extArmed = last
                extVersion++
            }
            return true
        }

        // Commits everything before the last comma, leaving any trailing
        // partial token in the field so typing flows uninterrupted.
        function commitTokens(text, keepTail) {
            var parts = text.split(",")
            var tail = keepTail ? parts.pop() : ""
            for (var i = 0; i < parts.length; i++)
                addExt(parts[i])
            return tail
        }

        Timer { id: dupTimer; interval: 2600; onTriggered: settingsDrawer.extWarning = "" }

        // Outer layout: a scrollable body plus a button row pinned to the
        // bottom. Without this the ColumnLayout squashed its children on a
        // short window and pushed Save outside the drawer, where it silently
        // could not be clicked -- settings looked toggled but never saved.
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            Text {
                text: i18n.strings.settings
                color: win.textMain; font.pixelSize: 18; font.bold: true
            }

            ScrollView {
                id: drawerScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth
                clip: true
                ScrollBar.vertical.policy: ScrollBar.AsNeeded
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: drawerScroll.availableWidth
            spacing: 16

            // language dropdown
            Text { text: i18n.strings.language; color: win.textDim; font.pixelSize: 12 }
            ComboBox {
                id: langCombo
                Layout.fillWidth: true
                implicitHeight: 38
                model: i18n.availableLanguages
                textRole: "name"
                valueRole: "code"

                function langIndex() {
                    for (var i = 0; i < i18n.availableLanguages.length; i++)
                        if (i18n.availableLanguages[i].code === i18n.language) return i
                    return 0
                }
                currentIndex: langIndex()
                onActivated: (index) => i18n.setLanguage(i18n.availableLanguages[index].code)

                HoverHandler { cursorShape: Qt.PointingHandCursor }

                background: Rectangle {
                    radius: 8
                    color: langCombo.hovered ? win.surface : "#15181f"
                    border.color: langCombo.activeFocus ? win.accent : "#2a2f3a"
                    Behavior on color { ColorAnimation { duration: 90 } }
                }
                contentItem: Text {
                    text: langCombo.displayText
                    color: win.textMain
                    leftPadding: 12
                    verticalAlignment: Text.AlignVCenter
                }
                indicator: Text {
                    x: langCombo.width - width - 12
                    y: (langCombo.height - height) / 2
                    text: "▾"; color: win.textDim; font.pixelSize: 12
                }
                popup: Popup {
                    y: langCombo.height + 4
                    width: langCombo.width
                    padding: 4
                    background: Rectangle { radius: 8; color: win.surface; border.color: "#2a2f3a" }
                    contentItem: ListView {
                        implicitHeight: contentHeight
                        model: langCombo.popup.visible ? langCombo.delegateModel : null
                        clip: true
                    }
                }
                delegate: ItemDelegate {
                    required property var modelData
                    required property int index
                    width: langCombo.width - 8
                    implicitHeight: 32
                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                    background: Rectangle {
                        radius: 6
                        color: langCombo.currentIndex === index ? win.accent
                             : (hovered ? win.surfaceAlt : "transparent")
                    }
                    contentItem: Text {
                        text: modelData.name
                        color: langCombo.currentIndex === index ? "white" : win.textMain
                        leftPadding: 8
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: "#2a2f3a" }

            SettingToggle {
                label: i18n.strings.intercept_enabled
                checked: settingsDrawer.getS("intercept_enabled", true)
                onToggled: (v) => settingsDrawer.setS("intercept_enabled", v)
            }
            SettingToggle {
                label: i18n.strings.auto_start
                sub: i18n.strings.auto_start_sub
                checked: settingsDrawer.getS("auto_start", false)
                onToggled: (v) => settingsDrawer.setS("auto_start", v)
            }
            SettingToggle {
                label: i18n.strings.intercept_all
                sub: i18n.strings.intercept_all_sub
                checked: settingsDrawer.getS("intercept_all", false)
                onToggled: (v) => settingsDrawer.setS("intercept_all", v)
            }
            SettingToggle {
                label: i18n.strings.clipboard_enabled
                sub: i18n.strings.clipboard_sub
                checked: settingsDrawer.getS("clipboard_enabled", false)
                onToggled: (v) => settingsDrawer.setS("clipboard_enabled", v)
            }
            SettingToggle {
                label: i18n.strings.disk_guard
                sub: i18n.strings.disk_guard_sub
                checked: settingsDrawer.getS("disk_guard_enabled", true)
                onToggled: (v) => settingsDrawer.setS("disk_guard_enabled", v)
            }
            RowLayout {
                Layout.fillWidth: true
                enabled: settingsDrawer.getS("disk_guard_enabled", true)
                opacity: enabled ? 1.0 : 0.4
                Text {
                    text: i18n.strings.disk_reserve
                    color: win.textDim; font.pixelSize: 12
                }
                Item { Layout.fillWidth: true }
                StepBtn {
                    text: "−"
                    onClicked: settingsDrawer.setS("disk_reserve_mb",
                        Math.max(0, settingsDrawer.getS("disk_reserve_mb", 2048) - 512))
                }
                Text {
                    text: settingsDrawer.getS("disk_reserve_mb", 2048)
                    color: win.textMain; font.pixelSize: 13
                    horizontalAlignment: Text.AlignHCenter
                    Layout.preferredWidth: 46
                }
                StepBtn {
                    text: "+"
                    onClicked: settingsDrawer.setS("disk_reserve_mb",
                        Math.min(51200, settingsDrawer.getS("disk_reserve_mb", 2048) + 512))
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: i18n.strings.intercepted_ext
                    color: win.textDim; font.pixelSize: 12
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: settingsDrawer.extVersion, settingsDrawer.extList.length
                    color: win.textDim; font.pixelSize: 11
                }
            }

            // Extensions as removable pills. Typing a comma (or Enter) commits
            // the token, mirroring how tag inputs behave on the web.
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: extFlow.implicitHeight + 16
                radius: 8
                color: win.surface
                border.color: extInput.activeFocus ? win.accent : "#2a2f3a"
                enabled: !settingsDrawer.getS("intercept_all", false)
                opacity: enabled ? 1.0 : 0.4

                MouseArea {
                    anchors.fill: parent
                    onClicked: extInput.forceActiveFocus()
                }

                Flow {
                    id: extFlow
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 8
                    spacing: 6

                    Repeater {
                        model: settingsDrawer.extVersion, settingsDrawer.extList

                        delegate: Rectangle {
                            required property string modelData
                            required property int index
                            readonly property bool armed: settingsDrawer.extArmed === index
                            height: 24
                            width: pillRow.implicitWidth + 16
                            radius: 12
                            color: armed ? "#4a2226" : win.surfaceAlt
                            border.color: armed ? "#ff6b6b" : "#3a4050"
                            Behavior on color { ColorAnimation { duration: 90 } }

                            RowLayout {
                                id: pillRow
                                anchors.centerIn: parent
                                spacing: 6
                                Text {
                                    text: modelData
                                    color: armed ? "#ffb4b4" : win.textMain
                                    font.pixelSize: 11
                                }
                                Text {
                                    text: "✕"
                                    color: removeHover.hovered ? "#ff6b6b" : win.textDim
                                    font.pixelSize: 11
                                    HoverHandler { id: removeHover; cursorShape: Qt.PointingHandCursor }
                                    TapHandler {
                                        onTapped: settingsDrawer.removeExtAt(index)
                                    }
                                }
                            }
                        }
                    }

                    TextField {
                        id: extInput
                        width: Math.max(90, extFlow.width - 8)
                        height: 24
                        verticalAlignment: TextInput.AlignVCenter
                        placeholderText: i18n.strings.ext_add_placeholder
                        placeholderTextColor: win.textDim
                        color: win.textMain
                        font.pixelSize: 11
                        background: Item {}
                        selectByMouse: true

                        // Comma commits; this also handles a pasted list.
                        onTextChanged: {
                            settingsDrawer.disarmExt()
                            if (text.indexOf(",") !== -1)
                                text = settingsDrawer.commitTokens(text, true)
                        }
                        onAccepted: {
                            if (settingsDrawer.addExt(text))
                                text = ""
                        }
                        onActiveFocusChanged: if (!activeFocus) settingsDrawer.disarmExt()

                        Keys.onPressed: (event) => {
                            if (event.key === Qt.Key_Backspace && text.length === 0) {
                                event.accepted = settingsDrawer.backspaceExt()
                                return
                            }
                            // Escape cancels a pending deletion rather than
                            // leaving a pill sitting there looking doomed.
                            if (event.key === Qt.Key_Escape
                                    && settingsDrawer.extArmed !== -1) {
                                settingsDrawer.disarmExt()
                                event.accepted = true
                                return
                            }
                            settingsDrawer.disarmExt()
                        }
                    }
                }
            }
            Text {
                readonly property bool armed: (settingsDrawer.extVersion,
                                               settingsDrawer.extArmed) !== -1
                text: armed
                      ? win.fmt(i18n.strings.ext_confirm_remove,
                                settingsDrawer.extList[settingsDrawer.extArmed])
                      : settingsDrawer.extWarning.length > 0
                        ? settingsDrawer.extWarning : i18n.strings.ext_hint
                color: armed ? "#ff6b6b"
                     : settingsDrawer.extWarning.length > 0 ? "#e0b341" : win.textDim
                font.pixelSize: 10
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: "#2a2f3a" }

            // Voluntary support. Deliberately unlocks nothing: the moment a
            // donation grants a feature it becomes a digital purchase, which
            // the Microsoft Store requires to go through its own commerce.
            Button {
                Layout.fillWidth: true
                implicitHeight: 38
                HoverHandler { cursorShape: Qt.PointingHandCursor }
                background: Rectangle {
                    radius: 8
                    color: parent.hovered ? win.surface : "transparent"
                    border.color: parent.hovered ? "#ff6b6b" : "#2a2f3a"
                    Behavior on color { ColorAnimation { duration: 90 } }
                }
                contentItem: RowLayout {
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    Text { text: "♥"; color: "#ff6b6b"; font.pixelSize: 13 }
                    Text {
                        text: i18n.strings.support
                        color: win.textMain
                        font.pixelSize: 12
                        verticalAlignment: Text.AlignVCenter
                    }
                    Item { Layout.fillWidth: true }
                }
                onClicked: Qt.openUrlExternally("https://stzlabs.com/pt/support")
            }
        }
            }

            // Pinned to the bottom: always reachable no matter how short the
            // window is, and no longer part of the scrolling content.
            RowLayout {
                Layout.fillWidth: true
                OutlineBtn {
                    text: i18n.strings.cancel
                    onClicked: settingsDrawer.close()
                }
                Item { Layout.fillWidth: true }
                AccentBtn {
                    text: i18n.strings.save
                    // Opening the drawer before the bridge has answered would
                    // leave `s` empty, and saving then would write defaults
                    // over the user's real settings -- wiping the filter list.
                    enabled: settingsDrawer.settingsReady
                    opacity: enabled ? 1.0 : 0.5
                    onClicked: {
                        // Commit whatever is still sitting in the input.
                        settingsDrawer.addExt(extInput.text)
                        extInput.text = ""
                        backend.saveSettings({
                            intercept_enabled: settingsDrawer.getS("intercept_enabled", true),
                            auto_start: settingsDrawer.getS("auto_start", false),
                            intercept_all: settingsDrawer.getS("intercept_all", false),
                            clipboard_enabled: settingsDrawer.getS("clipboard_enabled", false),
                            disk_guard_enabled: settingsDrawer.getS("disk_guard_enabled", true),
                            disk_reserve_mb: settingsDrawer.getS("disk_reserve_mb", 2048),
                            extensions: settingsDrawer.extList.slice()
                        })
                        settingsDrawer.close()
                    }
                }
            }
        }
    }

    // ----- Confirmation modal ---------------------------------------
    Dialog {
        id: confirmDialog
        anchors.centerIn: parent
        modal: true
        width: Math.min(520, win.width - 60)
        padding: 20
        closePolicy: Popup.NoAutoClose
        property var item: backend.pending.length > 0 ? backend.pending[0] : null
        property var selected: ({})
        property int selectionVersion: 0
        readonly property bool batchMode: backend.pending.length > 1
        visible: backend.pending.length > 0
        background: Rectangle { radius: 14; color: win.surface; border.color: "#2a2f3a" }

        function syncSelection() {
            var next = {}
            for (var i = 0; i < backend.pending.length; i++) {
                var id = backend.pending[i].id
                next[id] = selected[id] === undefined ? true : selected[id]
            }
            selected = next
            selectionVersion++
        }

        function isSelected(id) {
            selectionVersion
            return selected[id] !== false
        }

        function setSelected(id, value) {
            selected[id] = value
            selectionVersion++
        }

        function selectedIds() {
            var ids = []
            for (var i = 0; i < backend.pending.length; i++) {
                var id = backend.pending[i].id
                if (isSelected(id))
                    ids.push(id)
            }
            return ids
        }

        function selectedCount() {
            return selectedIds().length
        }

        function confirmSelected() {
            var ids = selectedIds()
            for (var i = 0; i < ids.length; i++)
                backend.confirmPending(ids[i], dlgConn.value)
        }

        function cancelSelected() {
            var ids = selectedIds()
            for (var i = 0; i < ids.length; i++)
                backend.cancelPending(ids[i])
        }

        onVisibleChanged: if (visible) syncSelection()

        contentItem: ColumnLayout {
            spacing: 14
            Text {
                text: confirmDialog.batchMode
                      ? i18n.strings.new_downloads + " (" + backend.pending.length + ")"
                      : i18n.strings.new_download
                color: win.textMain; font.pixelSize: 16; font.bold: true
            }
            Text {
                visible: !confirmDialog.batchMode
                Layout.fillWidth: true
                text: confirmDialog.item ? confirmDialog.item.name : ""
                color: win.textMain; font.pixelSize: 14
                elide: Text.ElideMiddle
            }
            Text {
                visible: !confirmDialog.batchMode
                text: confirmDialog.item && confirmDialog.item.size > 0
                      ? i18n.strings.size + ": " + win.fmtSize(confirmDialog.item.size)
                      : i18n.strings.size_unknown
                color: win.textDim; font.pixelSize: 12
            }

            Rectangle {
                visible: confirmDialog.batchMode
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(220, pendingList.contentHeight + 2)
                radius: 8
                color: "#15181f"
                border.color: "#2a2f3a"

                ListView {
                    id: pendingList
                    anchors.fill: parent
                    anchors.margins: 1
                    clip: true
                    model: backend.pending

                    delegate: ItemDelegate {
                        required property var modelData
                        width: pendingList.width
                        implicitHeight: 44
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                        background: Rectangle {
                            color: hovered ? win.surfaceAlt : "transparent"
                            radius: 6
                        }

                        contentItem: RowLayout {
                            spacing: 10
                            CheckBox {
                                id: pendingCheck
                                checked: confirmDialog.isSelected(modelData.id)
                                onToggled: confirmDialog.setSelected(modelData.id, checked)
                                indicator: Rectangle {
                                    implicitWidth: 18; implicitHeight: 18; radius: 4
                                    color: pendingCheck.checked ? win.accent : "transparent"
                                    border.color: pendingCheck.checked ? win.accent : "#3a4050"
                                    Text {
                                        anchors.centerIn: parent
                                        text: "✓"
                                        visible: pendingCheck.checked
                                        color: "white"
                                        font.pixelSize: 13
                                    }
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.name
                                    color: win.textMain
                                    font.pixelSize: 13
                                    elide: Text.ElideMiddle
                                }
                                Text {
                                    text: modelData.size > 0 ? win.fmtSize(modelData.size) : i18n.strings.size_unknown
                                    color: win.textDim
                                    font.pixelSize: 10
                                }
                            }
                        }
                        onClicked: confirmDialog.setSelected(
                            modelData.id,
                            !confirmDialog.isSelected(modelData.id)
                        )
                    }
                }
            }

            RowLayout {
                spacing: 8
                Text { text: i18n.strings.connections; color: win.textDim; font.pixelSize: 12 }
                Item { Layout.fillWidth: true }
                StepBtn { text: "−"; onClicked: dlgConn.value = Math.max(1, dlgConn.value - 1) }
                Text {
                    id: dlgConn; property int value: backend.settings.connections || 8
                    text: value; color: win.textMain; font.pixelSize: 14
                    horizontalAlignment: Text.AlignHCenter; Layout.preferredWidth: 22
                }
                StepBtn { text: "+"; onClicked: dlgConn.value = Math.min(16, dlgConn.value + 1) }
            }

            SettingToggle {
                id: autoChk
                label: i18n.strings.auto_next
                checked: false
            }

            RowLayout {
                Layout.fillWidth: true
                OutlineBtn {
                    enabled: confirmDialog.selectedCount() > 0
                    text: confirmDialog.batchMode ? i18n.strings.cancel_selected : i18n.strings.cancel
                    onClicked: {
                        if (confirmDialog.batchMode)
                            confirmDialog.cancelSelected()
                        else if (confirmDialog.item)
                            backend.cancelPending(confirmDialog.item.id)
                    }
                }
                Item { Layout.fillWidth: true }
                AccentBtn {
                    enabled: confirmDialog.selectedCount() > 0
                    text: confirmDialog.batchMode ? i18n.strings.download_selected : i18n.strings.download
                    onClicked: {
                        if (autoChk.checked)
                            backend.saveSettings({ auto_start: true })
                        if (confirmDialog.batchMode)
                            confirmDialog.confirmSelected()
                        else if (confirmDialog.item)
                            backend.confirmPending(confirmDialog.item.id, dlgConn.value)
                    }
                }
            }
        }
    }

    // ===== reusable components =======================================

    // primary (accent) button with hover + pressed states
    component AccentBtn: Button {
        implicitHeight: 44
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        background: Rectangle {
            radius: 10
            color: parent.down ? win.accentDown : (parent.hovered ? win.accentHover : win.accent)
            Behavior on color { ColorAnimation { duration: 90 } }
        }
        contentItem: Text {
            text: parent.text; color: "white"; font.bold: true
            leftPadding: 16; rightPadding: 16
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        }
    }

    // secondary outlined button with hover
    component OutlineBtn: Button {
        implicitHeight: 32
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        background: Rectangle {
            radius: 8
            color: parent.hovered ? win.surfaceAlt : "transparent"
            border.color: "#2a2f3a"
            Behavior on color { ColorAnimation { duration: 90 } }
        }
        contentItem: Text {
            text: parent.text; color: win.textDim; font.pixelSize: 12
            leftPadding: 12; rightPadding: 12
            verticalAlignment: Text.AlignVCenter
        }
    }

    component SettingToggle: RowLayout {
        property string label: ""
        property string sub: ""
        property bool checked: false
        signal toggled(bool value)
        Layout.fillWidth: true
        spacing: 10
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Text { text: label; color: win.textMain; font.pixelSize: 13 }
            Text {
                text: sub; color: win.textDim; font.pixelSize: 10
                visible: sub.length > 0; Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
        }
        Switch {
            checked: parent.checked
            HoverHandler { cursorShape: Qt.PointingHandCursor }
            onToggled: { parent.checked = checked; parent.toggled(checked) }
            indicator: Rectangle {
                implicitWidth: 40; implicitHeight: 22; radius: 11
                color: parent.checked ? win.accent : "#2a2f3a"
                Rectangle {
                    x: parent.parent.checked ? parent.width - width - 3 : 3
                    y: 3; width: 16; height: 16; radius: 8; color: "white"
                    Behavior on x { NumberAnimation { duration: 120 } }
                }
            }
        }
    }

    component StepBtn: Button {
        implicitWidth: 26
        implicitHeight: 26
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        background: Rectangle {
            radius: 6
            color: parent.down ? win.accent : (parent.hovered ? win.surfaceAlt : "#2a2f3a")
            Behavior on color { ColorAnimation { duration: 90 } }
        }
        contentItem: Text {
            text: parent.text; color: win.textMain; font.pixelSize: 16; font.bold: true
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        }
    }

    component ToolBtn: Button {
        property string tip: ""
        implicitWidth: 30
        implicitHeight: 24
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        ToolTip.visible: hovered && tip.length > 0
        ToolTip.text: tip
        background: Rectangle {
            radius: 6
            color: parent.hovered ? win.surfaceAlt : "transparent"
            Behavior on color { ColorAnimation { duration: 90 } }
        }
        contentItem: Text {
            text: parent.text; color: win.textMain
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        }
    }
}
