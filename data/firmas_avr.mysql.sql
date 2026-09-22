CREATE TABLE IF NOT EXISTS avr_signatures (
    id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    firma CHAR(8) NOT NULL,
    placa VARCHAR(80) NOT NULL,
    microcontrolador VARCHAR(80) NOT NULL,
    fqbn VARCHAR(100) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_avr_signature_board (firma, placa, fqbn),
    KEY idx_avr_signature (firma)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO avr_signatures (firma, placa, microcontrolador, fqbn) VALUES
('0x1E950F', 'Arduino UNO Rev3', 'ATmega328P', 'arduino:avr:uno'),
('0x1E950F', 'Arduino Nano (ATmega328P)', 'ATmega328P', 'arduino:avr:nano'),
('0x1E950F', 'Arduino Nano (Old Bootloader)', 'ATmega328P', 'arduino:avr:nano:cpu=atmega328old'),
('0x1E9801', 'Arduino Mega 2560 Rev3', 'ATmega2560', 'arduino:avr:mega'),
('0x1E9587', 'Arduino Leonardo', 'ATmega32u4', 'arduino:avr:leonardo'),
('0x1E9587', 'Arduino Micro', 'ATmega32u4', 'arduino:avr:micro'),
('0x1E9587', 'Arduino Esplora', 'ATmega32u4', 'arduino:avr:esplora'),
('0x1E9587', 'Arduino Yun', 'ATmega32u4 + SoC Linux', 'arduino:avr:yun'),
('0x1E9587', 'Arduino Robot Control', 'ATmega32u4', 'arduino:avr:robotControl'),
('0x1E9587', 'Arduino Robot Motor', 'ATmega32u4', 'arduino:avr:robotMotor'),
('0x1E9587', 'Arduino LilyPad USB', 'ATmega32u4', 'arduino:avr:lilypadusb'),
('0x1E950F', 'Arduino LilyPad (ATmega328P)', 'ATmega328P', 'arduino:avr:lilypad'),
('0x1E950F', 'Arduino Pro Mini (ATmega328P)', 'ATmega328P', 'arduino:avr:pro'),
('0x1E950F', 'Arduino Pro (ATmega328P)', 'ATmega328P', 'arduino:avr:pro'),
('0x1E950F', 'Arduino Fio', 'ATmega328P', 'arduino:avr:fio'),
('0x1E9406', 'Arduino Duemilanove', 'ATmega168', 'arduino:avr:diecimila'),
('0x1E9406', 'Arduino Diecimila', 'ATmega168', 'arduino:avr:diecimila'),
('0x1E9307', 'Arduino NG or older', 'ATmega8', 'arduino:avr:atmega8'),
('0x1E9406', 'Arduino NG or older', 'ATmega168', 'arduino:avr:diecimila'),
('0x1E950F', 'Arduino BT', 'ATmega328P', 'arduino:avr:bt'),
('0x1E930B', 'Arduino Gemma', 'ATtiny85', 'arduino:avr:gemma')
ON DUPLICATE KEY UPDATE
    microcontrolador = VALUES(microcontrolador);