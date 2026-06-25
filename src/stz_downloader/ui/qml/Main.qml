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
    title: "stz downloader"
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

    function statusLabel(s) {
        return i18n.strings["status_" + s] || s
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
    }

    Timer {
        id: topmostTimer
        interval: 400
        onTriggered: win.flags = win.flags & ~Qt.WindowStaysOnTopHint
    }

    Connections {
        target: backend
        function onNewPendingArrived() { win.bringToFront() }
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
                        Item { Layout.fillWidth: true }

                        ToolBtn {
                            text: modelData.status === "paused" ? "▶" : "⏸"
                            visible: modelData.status === "active" || modelData.status === "paused"
                            onClicked: modelData.status === "paused"
                                       ? backend.resume(modelData.gid)
                                       : backend.pause(modelData.gid)
                        }
                        ToolBtn {
                            text: "✕"
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
        Text {
            Layout.fillWidth: true
            visible: backend.status.length > 0
            text: backend.status
            color: "#ff6b6b"
            font.pixelSize: 11
        }
    }

    // ----- Settings drawer ------------------------------------------
    Drawer {
        id: settingsDrawer
        edge: Qt.RightEdge
        width: Math.min(360, win.width)
        height: win.height
        background: Rectangle { color: win.surfaceAlt }

        property var s: ({})
        onOpened: s = JSON.parse(JSON.stringify(backend.settings))

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 16

            Text {
                text: i18n.strings.settings
                color: win.textMain; font.pixelSize: 18; font.bold: true
            }

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
                checked: settingsDrawer.s.intercept_enabled || false
                onToggled: (v) => settingsDrawer.s.intercept_enabled = v
            }
            SettingToggle {
                label: i18n.strings.auto_start
                sub: i18n.strings.auto_start_sub
                checked: settingsDrawer.s.auto_start || false
                onToggled: (v) => settingsDrawer.s.auto_start = v
            }
            SettingToggle {
                label: i18n.strings.intercept_all
                sub: i18n.strings.intercept_all_sub
                checked: settingsDrawer.s.intercept_all || false
                onToggled: (v) => settingsDrawer.s.intercept_all = v
            }

            Text {
                text: i18n.strings.intercepted_ext
                color: win.textDim; font.pixelSize: 12
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 8
                color: win.surface
                border.color: "#2a2f3a"
                opacity: settingsDrawer.s.intercept_all ? 0.4 : 1.0

                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 8
                    clip: true
                    TextArea {
                        id: extArea
                        enabled: !settingsDrawer.s.intercept_all
                        color: win.textMain
                        wrapMode: TextEdit.WordWrap
                        text: (settingsDrawer.s.extensions || []).join(", ")
                        background: Item {}
                        selectByMouse: true
                    }
                }
            }
            Text {
                text: i18n.strings.ext_hint
                color: win.textDim; font.pixelSize: 10
            }

            RowLayout {
                Layout.fillWidth: true
                OutlineBtn {
                    text: i18n.strings.cancel
                    onClicked: settingsDrawer.close()
                }
                Item { Layout.fillWidth: true }
                AccentBtn {
                    text: i18n.strings.save
                    onClicked: {
                        var exts = extArea.text.split(",")
                            .map((e) => e.trim().toLowerCase())
                            .filter((e) => e.length > 0)
                            .map((e) => e[0] === "." ? e : "." + e)
                        backend.saveSettings({
                            intercept_enabled: settingsDrawer.s.intercept_enabled,
                            auto_start: settingsDrawer.s.auto_start,
                            intercept_all: settingsDrawer.s.intercept_all,
                            extensions: exts
                        })
                        settingsDrawer.close()
                    }
                }
            }
        }
    }

    // ----- Confirmation modal (one pending download at a time) ------
    Dialog {
        id: confirmDialog
        anchors.centerIn: parent
        modal: true
        width: Math.min(460, win.width - 60)
        padding: 20
        closePolicy: Popup.NoAutoClose
        property var item: backend.pending.length > 0 ? backend.pending[0] : null
        visible: item !== null
        background: Rectangle { radius: 14; color: win.surface; border.color: "#2a2f3a" }

        contentItem: ColumnLayout {
            spacing: 14
            Text {
                text: i18n.strings.new_download
                color: win.textMain; font.pixelSize: 16; font.bold: true
            }
            Text {
                Layout.fillWidth: true
                text: confirmDialog.item ? confirmDialog.item.name : ""
                color: win.textMain; font.pixelSize: 14
                elide: Text.ElideMiddle
            }
            Text {
                text: confirmDialog.item && confirmDialog.item.size > 0
                      ? i18n.strings.size + ": " + win.fmtSize(confirmDialog.item.size)
                      : i18n.strings.size_unknown
                color: win.textDim; font.pixelSize: 12
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
                    text: i18n.strings.cancel
                    onClicked: if (confirmDialog.item) backend.cancelPending(confirmDialog.item.id)
                }
                Item { Layout.fillWidth: true }
                AccentBtn {
                    text: i18n.strings.download
                    onClicked: {
                        if (autoChk.checked)
                            backend.saveSettings({ auto_start: true })
                        if (confirmDialog.item)
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
        implicitWidth: 30
        implicitHeight: 24
        HoverHandler { cursorShape: Qt.PointingHandCursor }
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
