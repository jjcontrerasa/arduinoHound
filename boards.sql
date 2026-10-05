PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS boards (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mcu TEXT NOT NULL,
    fqbn TEXT NOT NULL,
    alternate_fqbn TEXT
);

INSERT OR REPLACE INTO boards (key, name, mcu, fqbn, alternate_fqbn) VALUES
('uno', 'Arduino UNO Rev3', 'ATmega328P', 'arduino:avr:uno', NULL),
('nano', 'Arduino Nano (original)', 'ATmega328P', 'arduino:avr:nano', NULL),
('nano_oldboot', 'Arduino Nano (Old Bootloader)', 'ATmega328P (bootloader antiguo)', 'arduino:avr:nano:cpu=atmega328old', NULL),
('nano_every', 'Arduino Nano Every', 'ATmega4809', 'arduino:megaavr:nona4809', NULL),
('mega2560', 'Arduino Mega 2560 Rev3', 'ATmega2560', 'arduino:avr:mega', NULL),
('uno_r4_minima', 'Arduino UNO R4 Minima', 'RA4M1', 'arduino:renesas_uno:unor4minima', NULL),
('uno_r4_wifi', 'Arduino UNO R4 WiFi', 'RA4M1 + ESP32-S3', 'arduino:renesas_uno:unor4wifi', NULL),
('leonardo', 'Arduino Leonardo', 'ATmega32u4', 'arduino:avr:leonardo', NULL),
('micro', 'Arduino Micro', 'ATmega32u4', 'arduino:avr:micro', NULL),
('esplora', 'Arduino Esplora', 'ATmega32u4', 'arduino:avr:esplora', NULL),
('yun', 'Arduino Yún', 'ATmega32u4 + SoC Linux', 'arduino:avr:yun', NULL),
('robot_control', 'Arduino Robot Control', 'ATmega32u4', 'arduino:avr:robotControl', NULL),
('robot_motor', 'Arduino Robot Motor', 'ATmega32u4', 'arduino:avr:robotMotor', NULL),
('gemma', 'Arduino Gemma', 'ATtiny85', 'arduino:avr:gemma', NULL),
('lilypad_usb', 'Arduino LilyPad USB', 'ATmega32u4', 'arduino:avr:lilypadusb', NULL),
('lilypad', 'Arduino LilyPad (ATmega328P)', 'ATmega328P', 'arduino:avr:lilypad', NULL),
('pro_mini', 'Arduino Pro Mini (ATmega328P)', 'ATmega328P', 'arduino:avr:pro', NULL),
('pro', 'Arduino Pro (ATmega328P)', 'ATmega328P', 'arduino:avr:pro', NULL),
('fio', 'Arduino Fio', 'ATmega328P', 'arduino:avr:fio', NULL),
('duemilanove', 'Arduino Duemilanove', 'ATmega328P / ATmega168', 'arduino:avr:diecimila', NULL),
('diecimila', 'Arduino Diecimila', 'ATmega168', 'arduino:avr:diecimila', NULL),
('bt', 'Arduino BT', 'ATmega328P', 'arduino:avr:bt', NULL),
('ng', 'Arduino NG or older', 'ATmega8 / ATmega168', 'arduino:avr:atmega8', 'arduino:avr:diecimila');
