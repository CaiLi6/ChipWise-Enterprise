import api from './client'
import type { CompareRequest, CompareResult } from '@/types/api'

// Mock data for dev mode
const MOCK_COMPARE: CompareResult = {
  chips: ['STM32F407', 'STM32F103', 'GD32F303'],
  parameters: {
    'Core': { 'STM32F407': 'Cortex-M4', 'STM32F103': 'Cortex-M3', 'GD32F303': 'Cortex-M4' },
    'Max Freq': { 'STM32F407': '168 MHz', 'STM32F103': '72 MHz', 'GD32F303': '120 MHz' },
    'Flash': { 'STM32F407': '1 MB', 'STM32F103': '512 KB', 'GD32F303': '512 KB' },
    'SRAM': { 'STM32F407': '192 KB', 'STM32F103': '64 KB', 'GD32F303': '96 KB' },
    'Voltage': { 'STM32F407': '1.8-3.6V', 'STM32F103': '2.0-3.6V', 'GD32F303': '2.6-3.6V' },
    'Package': { 'STM32F407': 'LQFP144', 'STM32F103': 'LQFP64', 'GD32F303': 'LQFP100' },
  },
}

export async function compareChips(data: CompareRequest): Promise<CompareResult> {
  if (import.meta.env.DEV) {
    return Promise.resolve(MOCK_COMPARE)
  }
  const resp = await api.post<CompareResult>('/api/v1/compare', data)
  return resp.data
}
