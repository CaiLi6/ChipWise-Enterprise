-- Seed data for integration tests (integration_nollm)
-- Provides realistic chip records for testing queries, compare, and graph operations.

-- Chips table
INSERT INTO chips (part_number, manufacturer, category, description, created_at)
VALUES
    ('STM32F407VGT6', 'STMicroelectronics', 'MCU', 'ARM Cortex-M4 with FPU, 168 MHz, 1 MB Flash, 192 KB RAM', NOW()),
    ('STM32F103C8T6', 'STMicroelectronics', 'MCU', 'ARM Cortex-M3, 72 MHz, 64 KB Flash, 20 KB RAM', NOW()),
    ('GD32F303CCT6', 'GigaDevice', 'MCU', 'ARM Cortex-M4, 120 MHz, 256 KB Flash, 48 KB RAM', NOW()),
    ('ESP32-WROOM-32', 'Espressif', 'SoC', 'Dual-core Xtensa LX6, 240 MHz, WiFi + BT, 4 MB Flash', NOW()),
    ('RP2040', 'Raspberry Pi', 'MCU', 'Dual-core ARM Cortex-M0+, 133 MHz, 264 KB SRAM', NOW())
ON CONFLICT (part_number) DO NOTHING;

-- Parameters table
INSERT INTO chip_parameters (chip_part_number, param_name, param_value, unit, source_doc_id)
VALUES
    ('STM32F407VGT6', 'max_frequency', '168', 'MHz', NULL),
    ('STM32F407VGT6', 'flash_size', '1024', 'KB', NULL),
    ('STM32F407VGT6', 'ram_size', '192', 'KB', NULL),
    ('STM32F407VGT6', 'gpio_count', '140', '', NULL),
    ('STM32F407VGT6', 'supply_voltage_min', '1.8', 'V', NULL),
    ('STM32F407VGT6', 'supply_voltage_max', '3.6', 'V', NULL),
    ('STM32F103C8T6', 'max_frequency', '72', 'MHz', NULL),
    ('STM32F103C8T6', 'flash_size', '64', 'KB', NULL),
    ('STM32F103C8T6', 'ram_size', '20', 'KB', NULL),
    ('STM32F103C8T6', 'gpio_count', '37', '', NULL),
    ('GD32F303CCT6', 'max_frequency', '120', 'MHz', NULL),
    ('GD32F303CCT6', 'flash_size', '256', 'KB', NULL),
    ('GD32F303CCT6', 'ram_size', '48', 'KB', NULL),
    ('ESP32-WROOM-32', 'max_frequency', '240', 'MHz', NULL),
    ('ESP32-WROOM-32', 'flash_size', '4096', 'KB', NULL),
    ('ESP32-WROOM-32', 'wifi', '802.11 b/g/n', '', NULL),
    ('ESP32-WROOM-32', 'bluetooth', '4.2 + BLE', '', NULL),
    ('RP2040', 'max_frequency', '133', 'MHz', NULL),
    ('RP2040', 'ram_size', '264', 'KB', NULL),
    ('RP2040', 'gpio_count', '30', '', NULL)
ON CONFLICT DO NOTHING;

-- Errata table
INSERT INTO errata (chip_part_number, errata_id, title, description, severity, workaround)
VALUES
    ('STM32F407VGT6', 'ES0182-2.1.1', 'ADC1 channel 0 may return wrong data', 'Under certain conditions, ADC1 regular channel 0 conversion may return incorrect data when preceded by an injected conversion.', 'medium', 'Insert a dummy conversion on channel 0 before the actual measurement.'),
    ('STM32F103C8T6', 'ES0298-1.3', 'I2C analog filter may cause wrong detection', 'The I2C analog noise filter may detect false start conditions.', 'low', 'Disable analog filter via I2C_CR1 ANFOFF bit or use digital filter.')
ON CONFLICT DO NOTHING;
