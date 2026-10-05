# PyInstaller: pyinstaller ArduinoHound.spec
# Incluye los catalogos de data/ tal como estan (JSON y SQL). No incluye
# reportes.json, puertos.json ni los indices de arduino-cli (package_index/library_index).
a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=[
        ("data", "data"),
        ("assets", "assets"),
        ("ArduinoHound", "ArduinoHound"),
        ("arduino-cli.exe", "."),
    ],
    hiddenimports=["serial", "serial.tools.list_ports"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ArduinoHound",
    console=False,
    icon="assets/IconoAHound.ico",
)
coll = COLLECT(exe, a.binaries, a.datas, name="ArduinoHound")
