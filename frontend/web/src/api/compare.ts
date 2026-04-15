import api from './client'
import type { CompareRequest, CompareResult } from '@/types/api'

// Mock data for dev mode — values per chip, flat lookup
const MOCK_PARAMS: Record<string, Record<string, string>> = {
  'Core': {
    'STM32F407': 'Cortex-M4',
    'STM32F103': 'Cortex-M3',
    'GD32F303': 'Cortex-M4',
    'ESP32-S3': 'Xtensa LX7',
    'TPS65217': 'N/A (PMIC)',
  },
  'Max Freq': {
    'STM32F407': '168 MHz',
    'STM32F103': '72 MHz',
    'GD32F303': '120 MHz',
    'ESP32-S3': '240 MHz',
    'TPS65217': '—',
  },
  'Flash': {
    'STM32F407': '1 MB',
    'STM32F103': '512 KB',
    'GD32F303': '512 KB',
    'ESP32-S3': '8 MB (external)',
    'TPS65217': '—',
  },
  'SRAM': {
    'STM32F407': '192 KB',
    'STM32F103': '64 KB',
    'GD32F303': '96 KB',
    'ESP32-S3': '512 KB',
    'TPS65217': '—',
  },
  'Voltage': {
    'STM32F407': '1.8-3.6V',
    'STM32F103': '2.0-3.6V',
    'GD32F303': '2.6-3.6V',
    'ESP32-S3': '3.0-3.6V',
    'TPS65217': '2.7-5.5V',
  },
  'Package': {
    'STM32F407': 'LQFP144',
    'STM32F103': 'LQFP64',
    'GD32F303': 'LQFP100',
    'ESP32-S3': 'QFN56',
    'TPS65217': 'VQFN48',
  },
}

export async function compareChips(data: CompareRequest): Promise<CompareResult> {
  if (import.meta.env.DEV) {
    // Build filtered result strictly from requested chips
    const filtered: CompareResult = {
      chips: [...data.chips],
      parameters: {},
    }
    for (const [key, values] of Object.entries(MOCK_PARAMS)) {
      filtered.parameters[key] = {}
      for (const chip of data.chips) {
        filtered.parameters[key][chip] = values[chip] ?? '—'
      }
    }
    return Promise.resolve(filtered)
  }
  const resp = await api.post<CompareResult>('/api/v1/compare', data)
  return resp.data
}
